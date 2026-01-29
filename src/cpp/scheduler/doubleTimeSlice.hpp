#pragma once

#include <exception>
#include <functional>
#include <iomanip>
#include <map>
#include <queue>
#include <set>
#include <sstream>
#include <tuple>

#include "../util/LifetimeArray.hpp"
#include "../util/constants.hpp"
#include "../util/instruction.hpp"
#include "../util/instructionDependencyManager.hpp"
#include "../util/problem.hpp"
#include "routingError.hpp"
#include "scheduleResult.hpp"

class DoubleTimeSliceScheduler {
 public:
  Problem prob;
  std::vector<std::vector<int>> adj_ancillary;

  int elapsed_code_beat;

  // - code_beat_xor := (elapsed_code_beat - 1) ^ elapsed_code_beat;
  // - The operation (time ^ code_beat_xor) will give
  //   the adjacent time in the newest two times.
  int code_beat_xor;

  // These are for path search.
  // When we visit a cell, the lifetime of the cell is set to 1.
  // We reset `visited` before each path search by using `elapse_time` function.
  std::array<LifetimeArray, 2> visited;
  std::vector<std::vector<std::pair<int, int>>> parent;

  // - This is used to check how the two newest layers are occupied.
  std::array<LifetimeArray, 2> occupied;

  DoubleTimeSliceScheduler(const Problem& prob)
      : prob(prob), adj_ancillary(prob.make_adj_ancillary()) {}

  const std::vector<int>& next_ancillary_qubits(int position) const {
    assert(0 <= position && position < prob.chip_size);
    return adj_ancillary[position];
  }

  std::vector<int> next_ancillary_qubits(int position,
                                         Direction direction) const {
    assert(0 <= position && position < prob.chip_size);

    std::vector<int> ret;
    for (auto&& next_position : adj_ancillary[position]) {
      if (prob.adjacent_direction(position, next_position) == direction) {
        ret.push_back(next_position);
      }
    }

    return ret;
  }

  void initialize() {
    elapsed_code_beat = 1;
    for (auto&& oc : occupied) {
      oc.initialize(prob.chip_size);
    }
    for (auto&& vs : visited) {
      vs.initialize(prob.chip_size);
    }
    parent.assign(2, std::vector<std::pair<int, int>>(prob.chip_size));
    code_beat_xor = (elapsed_code_beat - 1) ^ elapsed_code_beat;
    for (auto&& magic_pos : prob.ms_factories) {
      occupy(magic_pos, prob.magic_prep_time);
    }
  }

  void wait_code_beat() {
    elapsed_code_beat++;
    code_beat_xor = (elapsed_code_beat - 1) ^ elapsed_code_beat;
    occupied[elapsed_code_beat & 1].elapse_time();
  }

  inline void visit(int t, int position) {
    visited[t & 1].set_lifetime(position);
  }

  inline bool is_visited(int t, int position) const {
    return visited[t & 1].unavailable(position);
  }

  inline void reset_visit() {
    for (auto&& vs : visited) {
      vs.elapse_time();
    }
  }

  inline void single_occupy(int t, int position) {
    assert(elapsed_code_beat - 1 <= t && t <= elapsed_code_beat);
    occupied[t & 1].set_lifetime(position);
  }

  inline void occupy(int position, int lifetime) {
    const bool next_clear_parity = (~elapsed_code_beat) & 1;
    occupied[next_clear_parity].set_lifetime(position, (lifetime + 1) / 2);
    occupied[!next_clear_parity].set_lifetime(position, lifetime / 2);
  }

  inline bool is_occupied(int t, int position) const {
    return occupied[t & 1].unavailable(position);
  }

  std::vector<int> available_magic_positions(int t) const {
    std::vector<int> magic_positions;
    for (auto&& magic_pos : prob.ms_factories) {
      if (!is_occupied(t, magic_pos)) {
        magic_positions.push_back(magic_pos);
      }
    }
    return magic_positions;
  }

  std::vector<int> get_available_target_positions(int t, int target_id) const {
    if (target_id == -1) {
      return available_magic_positions(t);
    } else {
      int target_pos = prob.data_qubits[target_id];
      return is_occupied(t, target_pos) ? std::vector<int>{}
                                        : std::vector<int>{target_pos};
    }
  }

  template <RoutingAlgorithm routing_algo>
  std::vector<std::pair<int, int>> find_path_ignore_topology(
      const Instruction& inst) const {
    assert(routing_algo == IgnoreTopologyInfiniteMagic ||
           routing_algo == IgnoreTopology);

    std::vector<std::pair<int, int>> path;

    auto least_push = [&](int pos) -> bool {
      for (int t = elapsed_code_beat - 1; t <= elapsed_code_beat; t++) {
        if (!is_occupied(t, pos)) {
          path.emplace_back(t, pos);
          return true;
        }
      }
      return false;
    };

    auto magic_push = [&]() -> bool {
      for (auto&& magic_pos : prob.ms_factories) {
        if (least_push(magic_pos)) {
          return true;
        }
      }
      return false;
    };

    for (int target_id : inst.targetIds) {
      bool push_succeed;
      if (target_id == -1) {
        if constexpr (routing_algo == IgnoreTopology) {
          push_succeed = magic_push();
        } else {
          push_succeed = true;
        }
      } else {
        push_succeed = least_push(prob.data_qubits[target_id]);
      }
      if (!push_succeed) {
        return {};
      }
    }

    if constexpr (routing_algo == IgnoreTopology) {
      assert(path.size() == inst.targetIds.size());
    }

    return path;
  }

  std::vector<std::pair<int, int>> find_path_ignore_kink_parity(
      const Instruction& inst) {
    assert(inst.targetIds.size() == 2);

    reset_visit();

    std::vector<std::vector<std::tuple<int, int, int>>> target_next_tps(2);
    for (int target_index = 0; target_index < 2; target_index++) {
      const auto& target_directions = inst.directions[target_index];

      for (int init_timing = elapsed_code_beat - 1;
           init_timing <= elapsed_code_beat; init_timing++) {
        const auto target_positions = get_available_target_positions(
            init_timing, inst.targetIds[target_index]);
        for (int target_pos : target_positions) {
          if (is_occupied(init_timing, target_pos)) continue;
          for (Direction target_dir : target_directions) {
            for (int init_pos : next_ancillary_qubits(target_pos, target_dir)) {
              if (is_occupied(init_timing, init_pos)) continue;
              target_next_tps[target_index].push_back(
                  {init_timing, init_pos, target_pos});
            }
          }
        }
        // Use the lowest unoccupied neighbors.
        if (!target_next_tps[target_index].empty()) break;
      }

      // If all the neighbors are occupied, there is no path.
      if (target_next_tps[target_index].empty()) {
        return {};
      }
    }
    const auto start_next_tps = target_next_tps[0];
    const auto goal_next_tps = target_next_tps[1];

    const int goal_pos = std::get<2>(goal_next_tps[0]);
    std::set<std::pair<int, int>> goal_next_set;
    for (auto&& [time, next, tmp] : goal_next_tps) {
      goal_next_set.insert({time, next});
      assert(tmp == goal_pos);
    }

    std::queue<std::pair<int, int>> q;
    for (auto&& [start_adj_timing, start_adj_pos, start_pos] : start_next_tps) {
      if (is_visited(start_adj_timing, start_adj_pos)) continue;
      parent[start_adj_timing & 1][start_adj_pos] = {start_adj_timing,
                                                     start_pos};
      visit(start_adj_timing, start_adj_pos);
      q.push({start_adj_timing, start_adj_pos});
    }

    std::pair<int, int> found_goal_next_tp = {-1, -1};
    while (!q.empty()) {
      auto tp = q.front();
      q.pop();
      if (goal_next_set.count(tp)) {
        found_goal_next_tp = tp;
        break;
      }
      auto [t, p] = tp;
      // time axis
      int nt = t ^ code_beat_xor;
      if (!is_occupied(nt, p) && !is_visited(nt, p)) {
        parent[nt & 1][p] = {t, p};
        visit(nt, p);
        q.push({nt, p});
      }
      // other axes
      for (int np : next_ancillary_qubits(p)) {
        if (!is_occupied(t, np) && !is_visited(t, np)) {
          parent[t & 1][np] = {t, p};
          visit(t, np);
          q.push({t, np});
        }
      }
    }

    if (found_goal_next_tp.first == -1) {
      return {};
    }

    std::vector<std::pair<int, int>> path = {
        {found_goal_next_tp.first, goal_pos}, found_goal_next_tp};
    while (!prob.is_data_qubit(path.back().second)) {
      path.push_back(parent[path.back().first & 1][path.back().second]);
    }
    std::reverse(path.begin(), path.end());

    return path;
  }

  std::vector<std::pair<int, int>> invert_path_to_create_kink(
      const std::vector<std::pair<int, int>>& path) const {
    int path_len = int(path.size());
    if (path_len <= 2) return {};

    std::vector<std::pair<int, int>> inverted_path;
    inverted_path.reserve(path_len);
    for (auto&& [t, pos] : path) {
      inverted_path.emplace_back(t ^ code_beat_xor, pos);
    }

    std::vector<bool> invertible(path_len);
    for (int i = 0; i < path_len; i++) {
      auto [inv_t, inv_pos] = inverted_path[i];
      if (!is_occupied(inv_t, inv_pos)) {
        invertible[i] = true;
      }
    }

    // If `pos` appears twice in the path,
    // we cannot invert a path segment that has either of the two elements
    // because the resulting path will self-intersect.
    std::map<int, std::vector<int>> pos_to_indices;
    for (int i = 0; i < path_len; i++) {
      pos_to_indices[path[i].second].push_back(i);
    }
    // For each `pos_to_indices` values that has two elements (i, j),
    // we want to mark the closed interval [i, j] as banned interval.
    // To achieve this goal in O(path_len) time, we use a prefix sum trick.
    std::vector<int> banned_interval_count(path_len + 1);
    for (auto&& [pos, path_indices] : pos_to_indices) {
      if (path_indices.size() == 2) {
        banned_interval_count[path_indices[0]]++;
        banned_interval_count[path_indices[1] + 1]--;
      }
    }
    for (int i = 0; i < path_len; i++) {
      banned_interval_count[i + 1] += banned_interval_count[i];
    }
    // Thus, a path inverted at i-th position will not self-intersect
    // iff `banned_interval_count[i] == 0`.

    std::vector<bool> can_generate_kink(path_len);
    for (int i = 1; i < path_len - 1; i++) {
      auto [t0, pos0] = path[i - 1];
      auto [t1, pos1] = path[i];
      auto [t2, pos2] = path[i + 1];
      if (t0 == t1 && t1 == t2) {
        auto dir01 = prob.adjacent_direction(pos0, pos1);
        auto dir12 = prob.adjacent_direction(pos1, pos2);
        can_generate_kink[i] =
            (dir01 != Direction::Z && dir12 != Direction::Z && dir01 != dir12);
      }
    }

    // inverted_path[..., i] + path[i, ...]
    for (int i = 0; i < path_len; i++) {
      if (!invertible[i]) break;
      if (banned_interval_count[i] == 0 && can_generate_kink[i]) {
        std::vector<std::pair<int, int>> concat_path = std::move(inverted_path);
        concat_path.resize(i + 1);
        concat_path.insert(concat_path.end(), path.begin() + i, path.end());
        return concat_path;
      }
    }

    // path[..., i] + inverted_path[i, ...]
    for (int i = path_len - 1; i >= 0; i--) {
      if (!invertible[i]) break;
      if (banned_interval_count[i] == 0 && can_generate_kink[i]) {
        std::vector<std::pair<int, int>> concat_path = path;
        concat_path.resize(i + 1);
        concat_path.insert(concat_path.end(), inverted_path.begin() + i,
                           inverted_path.end());
        return concat_path;
      }
    }

    return {};
  }

  std::vector<std::pair<int, int>> invert_two_cells_to_flip_kink_parity(
      const std::vector<std::pair<int, int>>& path) const {
    int path_len = int(path.size());
    if (path_len <= 2) return {};

    std::vector<bool> invertible(path_len);
    for (int i = 0; i < path_len; i++) {
      auto [t, pos] = path[i];
      int inv_t = t ^ code_beat_xor;
      if (!is_occupied(inv_t, pos)) {
        invertible[i] = true;
      }
    }

    // Suppose `pos` appears twice in the path.
    // If they are adjacent and invert one of them,
    // the resulting path will not self-intersect.
    // Otherwise, the path will self-intersect.
    // So, we regard the latter case as not invertible.
    std::map<int, int> pos_to_last_index;
    for (int i = 0; i < path_len; i++) {
      auto pos = path[i].second;
      if (pos_to_last_index.count(pos)) {
        if (pos_to_last_index[pos] != i - 1) {
          invertible[pos_to_last_index[pos]] = false;
          invertible[i] = false;
        }
      } else {
        pos_to_last_index[pos] = i;
      }
    }

    std::vector<bool> change_kink_parity(path_len);
    for (int i = 1; i < path_len - 1; i++) {
      auto [t0, pos0] = path[i - 1];
      auto [t1, pos1] = path[i];
      auto [t2, pos2] = path[i + 1];
      // generate kink (X Y or Y X)
      if (t0 == t1 && t1 == t2) {
        auto dir01 = prob.adjacent_direction(pos0, pos1);
        auto dir12 = prob.adjacent_direction(pos1, pos2);
        change_kink_parity[i] =
            (dir01 != Direction::Z && dir12 != Direction::Z && dir01 != dir12);
      }
      // delete kink (X T Y or Y T X)
      if (i + 2 < path_len) {
        auto [t3, pos3] = path[i + 2];
        if (t0 == t1 && t1 != t2 && t2 == t3) {
          auto dir01 = prob.adjacent_direction(pos0, pos1);
          auto dir23 = prob.adjacent_direction(pos2, pos3);
          bool delete_kink = (dir01 != Direction::Z && dir23 != Direction::Z &&
                              dir01 != dir23);
          if (delete_kink) {
            change_kink_parity[i] = true;
            change_kink_parity[i + 1] = true;
          }
        }
      }
    }

    for (int i = 0; i < path_len - 1; i++) {
      if (invertible[i] && invertible[i + 1] &&
          change_kink_parity[i] != change_kink_parity[i + 1]) {
        std::vector<std::pair<int, int>> former(path.begin(),
                                                path.begin() + i + 1),
            latter(path.begin() + i + 1, path.end());

        auto modify_last =
            [&](std::vector<std::pair<int, int>>& half_path) -> void {
          int len = half_path.size();
          if (len == 1) {
            half_path.back().first ^= code_beat_xor;
          } else if (len >= 2 &&
                     half_path[len - 2].first != half_path[len - 1].first) {
            half_path.pop_back();
          } else {
            auto [t, pos] = half_path.back();
            half_path.push_back({t ^ code_beat_xor, pos});
          }
        };

        modify_last(former);
        std::reverse(latter.begin(), latter.end());
        modify_last(latter);
        std::reverse(latter.begin(), latter.end());

        former.insert(former.end(), latter.begin(), latter.end());
        return former;
      }
    }

    return {};
  }

  template <RoutingAlgorithm routing_algo>
  std::vector<std::pair<int, int>> find_and_invert_path(
      const Instruction& inst) {
    assert(inst.targetIds.size() == 2);

    auto path = find_path_ignore_kink_parity(inst);

    int kink_count = prob.count_kink(path);
    if (inst.kink_parity_allowed[kink_count % 2]) {
      return path;
    } else {
      if constexpr (routing_algo == InvertPath) {
        return invert_path_to_create_kink(path);
      } else if constexpr (routing_algo == InvertTwoCells ||
                           routing_algo == CareKinkParity) {
        return invert_two_cells_to_flip_kink_parity(path);
      } else {
        assert(false);
      }
    }
  }

  template <RoutingAlgorithm routing_algo>
  std::vector<std::pair<int, int>> find_path(const Instruction& inst) {
    if constexpr (routing_algo == IgnoreTopologyInfiniteMagic ||
                  routing_algo == IgnoreTopology) {
      return find_path_ignore_topology<routing_algo>(inst);
    } else if constexpr (routing_algo == IgnoreKinkParity) {
      return find_path_ignore_kink_parity(inst);
    } else if constexpr (routing_algo == CareKinkParity ||
                         routing_algo == InvertPath ||
                         routing_algo == InvertTwoCells) {
      return find_and_invert_path<routing_algo>(inst);
    } else {
      assert(false);
    }
  }

  template <RoutingAlgorithm routing_algo = CareKinkParity>
  MultiTimeSliceScheduleResult naive_schedule() {
    initialize();

    std::vector<MultiTimeSliceSurgeryPath> surgery_paths;
    surgery_paths.reserve(prob.instructions.size());

    std::vector<std::pair<int, int>> encoded_path;

    for (auto&& inst : prob.instructions) {
      while (true) {
        encoded_path = find_path<routing_algo>(inst);
        if (!encoded_path.empty()) {
          break;
        } else if (occupied[0].all_available() && occupied[1].all_available()) {
          std::stringstream ss;
          ss << "Routing Failed\n"
             << "Inst: " << inst << '\n';
          MultiTimeSliceScheduleResult(prob, surgery_paths).output_index(ss);
          throw RoutingError(ss.str());
        }
        wait_code_beat();
      }

      for (auto&& [t, pos] : encoded_path) {
        assert(!is_occupied(t, pos));
        single_occupy(t, pos);
      }
      // Occupy past target qubits to comply with instruction dependencies.
      for (auto&& [t, pos] : {encoded_path[0], encoded_path.back()}) {
        if (t == elapsed_code_beat) {
          single_occupy(elapsed_code_beat - 1, pos);
        }
      }

      // Cool time for magic state preparation
      if constexpr (routing_algo != IgnoreTopologyInfiniteMagic) {
        if (inst.targetIds[0] == -1) {
          const auto [t, pos] = encoded_path[0];
          // Routing cost: 1
          // Preparation cost: prob.magic_prep_time
          // Extra cost: 1 (if t = elapsed_code_beat;
          //  because t = elapsed_code_beat - 1 needs to be unavailable.)
          const int cool_time =
              1 + prob.magic_prep_time + (t + 1 - elapsed_code_beat);
          assert(prob.is_magic_factory(pos));
          occupy(pos, cool_time);
        }
      }

      surgery_paths.emplace_back(std::move(encoded_path));
    }

    return MultiTimeSliceScheduleResult(prob, surgery_paths);
  }

  template <RoutingAlgorithm routing_algo = CareKinkParity>
  MultiTimeSliceScheduleResult look_ahead_schedule() {
    initialize();

    std::vector<MultiTimeSliceSurgeryPath> surgery_paths(
        prob.instructions.size());

    InstructionDependencyManager manager(prob.data_qubits.size(),
                                         prob.instructions);

    std::vector<std::pair<int, int>> encoded_path;

    while (!manager.all_finished()) {
      for (auto it = manager.begin(); it != manager.end();) {
        int inst_index = *it;
        const Instruction& inst = prob.instructions[inst_index];

        encoded_path = find_path<routing_algo>(inst);

        if (!encoded_path.empty()) {
          it = manager.process_instruction(inst_index);
          for (auto&& [t, pos] : encoded_path) {
            assert(!is_occupied(t, pos));
            single_occupy(t, pos);
          }
          // Occupy past target qubits to comply with instruction dependencies.
          for (auto&& [t, pos] : {encoded_path[0], encoded_path.back()}) {
            if (t == elapsed_code_beat) {
              single_occupy(elapsed_code_beat - 1, pos);
            }
          }
          // Cool time for magic state preparation
          if constexpr (routing_algo != IgnoreTopologyInfiniteMagic) {
            if (inst.targetIds[0] == -1) {
              const auto [t, pos] = encoded_path[0];
              // Routing cost: 1
              // Preparation cost: prob.magic_prep_time
              // Extra cost: 1 (if t = elapsed_code_beat;
              //  because t = elapsed_code_beat - 1 needs to be unavailable.)
              const int cool_time =
                  1 + prob.magic_prep_time + (t + 1 - elapsed_code_beat);
              assert(prob.is_magic_factory(pos));
              occupy(pos, cool_time);
            }
          }
          surgery_paths[inst_index] = std::move(encoded_path);
        } else {
          it++;
          if (occupied[0].all_available() && occupied[1].all_available()) {
            std::stringstream ss;
            ss << "Routing Failed\n"
               << "Inst: " << inst << '\n';
            MultiTimeSliceScheduleResult(prob, surgery_paths).output_index(ss);
            throw RoutingError(ss.str());
          }
        }
      }

      wait_code_beat();
    }

    return MultiTimeSliceScheduleResult(prob, surgery_paths);
  }
};
