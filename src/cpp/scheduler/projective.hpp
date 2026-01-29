#pragma once

#include <exception>
#include <functional>
#include <iomanip>
#include <map>
#include <queue>
#include <set>
#include <sstream>
#include <stack>
#include <tuple>

#include "../util/constants.hpp"
#include "../util/instruction.hpp"
#include "../util/problem.hpp"
#include "routingError.hpp"
#include "scheduleResult.hpp"

enum class PositionWeighting { Constant, PowerOfTwo };

class ProjectiveScheduler {
 public:
  Problem prob;
  std::vector<std::vector<int>> adj_ancillary;

  int elapsed_code_beat;
  std::vector<int> heights;

  ProjectiveScheduler(const Problem& prob)
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

  template <PositionWeighting weighting>
  int64_t weight_position(int pos) const {
    if constexpr (weighting == PositionWeighting::Constant) {
      return 1LL;
    } else if constexpr (weighting == PositionWeighting::PowerOfTwo) {
      return 1LL << std::max(0, 32 - (elapsed_code_beat - heights[pos]));
    } else {
      assert(false);
    }
  };

  void initialize() {
    heights.assign(prob.chip_size, 0);
    for (auto&& magic_pos : prob.ms_factories) {
      heights[magic_pos] = prob.magic_prep_time;
    }
    elapsed_code_beat = prob.magic_prep_time;
  }

  std::vector<int> get_target_positions(int target_id) const {
    if (target_id == -1) {
      return prob.ms_factories;
    } else {
      return {prob.data_qubits[target_id]};
    }
  }

  std::vector<std::pair<int, int>> find_3d_path_ignore_topology_infinite_magic(
      const Instruction& inst) const {
    std::vector<std::pair<int, int>> path;
    for (int target_id : inst.targetIds) {
      int pos, t;
      if (target_id != -1) {
        pos = prob.data_qubits[target_id];
        t = heights[pos];
        path.emplace_back(t, pos);
      }
    }
    return path;
  }

  std::vector<std::pair<int, int>> find_3d_path_ignore_topology(
      const Instruction& inst) const {
    std::vector<std::pair<int, int>> path;
    for (int target_id : inst.targetIds) {
      int pos, t;
      if (target_id == -1) {
        t = INF;
        for (auto&& pos_tmp : prob.ms_factories) {
          int t_tmp = heights[pos_tmp];
          if (t > t_tmp) {
            t = t_tmp;
            pos = pos_tmp;
          }
        }
        assert(t < INF);
      } else {
        pos = prob.data_qubits[target_id];
        t = heights[pos];
      }
      path.emplace_back(t, pos);
    }

    return path;
  }

  template <PositionWeighting weighting = PositionWeighting::PowerOfTwo>
  std::vector<int> find_2d_minimum_weight_path(const Instruction& inst) const {
    assert(inst.targetIds.size() == 2);

    // A dirty hack to avoid searching for a path with a kink
    // when the gate is MAGIC_MZZ.
    auto start_directions = inst.directions[0];
    if (inst.gate == "MAGIC_MZZ") {
      start_directions = {Direction::H};
    }

    const std::vector<int> start_positions =
        get_target_positions(inst.targetIds[0]);
    const int goal_pos = prob.data_qubits[inst.targetIds[1]];

    struct Q {
      int64_t key;
      int pos;
      bool operator<(Q r) const { return key > r.key; }
    };
    std::priority_queue<Q> pq;
    std::vector<int64_t> dist(prob.chip_size, INFLL);
    std::vector<int> parent(prob.chip_size, -1);
    for (auto&& start_pos : start_positions) {
      for (auto&& start_dir : start_directions) {
        for (auto&& init_pos : next_ancillary_qubits(start_pos, start_dir)) {
          dist[init_pos] = weight_position<weighting>(init_pos);
          parent[init_pos] = start_pos;
          pq.push({dist[init_pos], init_pos});
        }
      }
    }

    std::set<int> goal_next_positions;
    for (auto&& goal_dir : inst.directions[1]) {
      for (auto&& goal_next : next_ancillary_qubits(goal_pos, goal_dir)) {
        goal_next_positions.insert(goal_next);
      }
    }

    while (!pq.empty()) {
      auto [key, p] = pq.top();
      pq.pop();
      if (dist[p] < key) {
        continue;
      }
      if (goal_next_positions.count(p)) {
        break;
      }
      for (auto&& np : next_ancillary_qubits(p)) {
        auto new_weight = dist[p] + weight_position<weighting>(np);
        if (dist[np] > new_weight) {
          dist[np] = new_weight;
          parent[np] = p;
          pq.push({new_weight, np});
        }
      }
    }

    int64_t path_minimum_weight = INFLL;
    int minimum_weight_path_adj = -1;

    auto goal_weight = weight_position<weighting>(goal_pos);
    for (auto&& end_pos : goal_next_positions) {
      int64_t path_weight = dist[end_pos] + goal_weight;
      if (path_minimum_weight > path_weight) {
        path_minimum_weight = path_weight;
        minimum_weight_path_adj = end_pos;
      }
    }

    assert(path_minimum_weight < INFLL);

    std::vector<int> path = {goal_pos, minimum_weight_path_adj};
    while (!prob.is_data_qubit(path.back())) {
      path.push_back(parent[path.back()]);
    }
    std::reverse(path.begin(), path.end());

    return path;
  }

  std::vector<int> lifted_path_top_heights(const std::vector<int>& path) const {
    std::vector<int> path_heights;
    path_heights.reserve(path.size());
    for (auto&& pos : path) {
      path_heights.push_back(heights[pos]);
    }

    std::vector<int> top_heights = path_heights;
    for (int index = 1; index < int(path.size()); index++) {
      top_heights[index - 1] =
          std::max(top_heights[index - 1], path_heights[index]);
    }
    for (int index = 0; index < int(path.size()) - 1; index++) {
      top_heights[index + 1] =
          std::max(top_heights[index + 1], path_heights[index]);
    }

    return top_heights;
  }

  std::vector<std::pair<int, int>> interpolate_3d_path(
      const std::vector<int>& path, const std::vector<int>& top_heights) const {
    std::vector<std::pair<int, int>> lifted_3d_path;
    for (int index = 0; index < int(path.size()); index++) {
      auto pos = path[index];
      int top_height = top_heights[index];

      int left_height = (index == 0) ? top_height : top_heights[index - 1];
      int right_height = (index == int(top_heights.size()) - 1)
                             ? top_height
                             : top_heights[index + 1];
      int bottom_height =
          std::min(std::min(left_height, right_height), top_height);

      std::vector<int> segment_heights(std::max(0, top_height - bottom_height) +
                                       1);
      iota(segment_heights.begin(), segment_heights.end(), bottom_height);
      // left is top   -> downward
      // middle is top -> one cell
      // right is top  -> upward
      if (left_height > right_height) {
        std::reverse(segment_heights.begin(), segment_heights.end());
      }

      for (auto&& timing : segment_heights) {
        lifted_3d_path.emplace_back(timing, pos);
      }
    }

    return lifted_3d_path;
  }

  int count_kink(const std::vector<int>& path,
                 const std::vector<int>& top_heights) const {
    // We can regard time axis and Z axis as the same direction
    // when counting kinks.
    std::vector<Direction> run_compressed_directions;
    auto push = [&](Direction dir) -> void {
      if (run_compressed_directions.empty() ||
          run_compressed_directions.back() != dir) {
        run_compressed_directions.push_back(dir);
      }
    };

    for (int index = 0; index < int(path.size()) - 1; index++) {
      if (top_heights[index] > top_heights[index + 1]) {
        // The path goes down in the time axis.
        push(Direction::Z);
      }
      push(prob.adjacent_direction(path[index], path[index + 1]));
      if (top_heights[index] < top_heights[index + 1]) {
        // The path goes up in the time axis.
        push(Direction::Z);
      }
    }

    return prob.count_kink(run_compressed_directions);
  }

  bool modify_heights_to_flip_kink_parity(const std::vector<int>& path,
                                          std::vector<int>& top_heights) const {
    // We only care a kink generated by time axis moves (e.g. X (*T) Y)
    // and ignore a kink generated by Z moves (e.g. X (*T) Z (*T) Y),
    // because the latter case cannot be eliminated by modifying heights.

    std::vector<bool> is_bending_point(path.size());
    for (int i = 1; i < int(path.size()) - 1; i++) {
      const int prev_pos = path[i - 1];
      const int pos = path[i];
      const int next_pos = path[i + 1];
      const Direction prev_dir = prob.adjacent_direction(prev_pos, pos);
      const Direction next_dir = prob.adjacent_direction(pos, next_pos);
      if (prev_dir != Direction::Z && next_dir != Direction::Z &&
          prev_dir != next_dir) {
        // X Y or Y X
        is_bending_point[i] = true;
      }
    }

    std::vector<bool> is_time_kink(path.size());
    for (int i = 1; i < int(path.size()) - 1; i++) {
      if (is_bending_point[i]) {
        if (top_heights[i] > top_heights[i - 1] ||
            top_heights[i] > top_heights[i + 1]) {
          is_time_kink[i] = 1;
        }
      }
    }

    // Referring to the modified `top_heights` and the recomputation range,
    // it recomputes if the kink parity flips.
    // The recomputation range means the range in which kinks may appear or
    // disappear.
    auto check_current_flip = [&](int recompute_first,
                                  int recompute_last) -> bool {
      recompute_first = std::max(recompute_first, 1);
      recompute_last = std::min(recompute_last, int(path.size()) - 2);

      bool flipped = false;
      for (int i = recompute_first; i < recompute_last + 1; i++) {
        if (is_bending_point[i]) {
          flipped ^= is_time_kink[i];
          bool new_kink = (top_heights[i] > top_heights[i - 1] ||
                           top_heights[i] > top_heights[i + 1]);
          flipped ^= new_kink;
        }
      }

      return flipped;
    };

    {
      for (int i = 1; i < int(path.size()) - 1; i++) {
        for (int j = i; j < int(path.size()) - 1; j++) {
          assert(check_current_flip(i, j) == false);
        }
      }
    }

    std::stack<std::pair<int, int>> rollback_stack;
    auto lift_top_heights = [&](int index, int new_height) -> void {
      rollback_stack.push({index, top_heights[index]});
      top_heights[index] = std::max(top_heights[index], new_height);
    };
    auto rollback_top_heights = [&]() -> void {
      auto [index, old_height] = rollback_stack.top();
      rollback_stack.pop();
      top_heights[index] = old_height;
    };

    // Lifting a single cell to remove a kink.
    for (int i = 1; i < int(path.size()) - 1; i++) {
      if (is_time_kink[i]) {
        int modify_index =
            (top_heights[i - 1] < top_heights[i]) ? i - 1 : i + 1;

        lift_top_heights(modify_index, top_heights[i]);
        if (check_current_flip(modify_index - 1, modify_index + 1)) {
          return true;
        }
        rollback_top_heights();
      }
    }

    // Lifting two cells to add a kink.
    // Among the bending points which have the same heights,
    // lifting the first one always create a kink.
    for (int i = 1; i < int(path.size()) - 1; i++) {
      if (is_bending_point[i] && !is_time_kink[i]) {
        for (auto&& diff : {-1, +1}) {
          auto [modify_index_min, modify_index_max] =
              std::minmax({i - diff, i});
          std::set<int> new_heights;
          int orig_height = std::max(top_heights[i - diff], top_heights[i]);
          new_heights.insert(std::max(top_heights[i + diff], orig_height));
          new_heights.insert(std::max(top_heights[i + diff] + 1, orig_height));
          for (auto&& new_height : new_heights) {
            lift_top_heights(modify_index_min, new_height);
            lift_top_heights(modify_index_max, new_height);
            if (check_current_flip(modify_index_min - 1,
                                   modify_index_max + 1)) {
              return true;
            }
            rollback_top_heights();
            rollback_top_heights();
          }
        }
      }
    }

    // If it still fails to modify the kink parity,
    // there are three bending points in a row such that
    // only the middle one has the lower height.
    // Then, it aligns the middle point to remove two kinks
    // and lifts two cells to create a kink.
    for (int i = 2; i < int(path.size()) - 2; i++) {
      if (is_bending_point[i - 1] && is_bending_point[i] &&
          is_bending_point[i + 1] && top_heights[i - 1] > top_heights[i] &&
          top_heights[i - 1] == top_heights[i + 1]) {
        int new_kink_base = top_heights[i - 1];
        lift_top_heights(i, new_kink_base);
        lift_top_heights(i - 1, new_kink_base + 1);
        lift_top_heights(i - 2, new_kink_base + 1);
        if (check_current_flip(i - 3, i + 1)) {
          return true;
        }
        rollback_top_heights();
        rollback_top_heights();
        rollback_top_heights();
      }
    }

    return false;
  }

  std::vector<std::pair<int, int>> find_3d_path_ignore_kink(
      const Instruction& inst) const {
    const auto path = find_2d_minimum_weight_path(inst);
    const auto top_heights = lifted_path_top_heights(path);
    return interpolate_3d_path(path, top_heights);
  }

  std::vector<std::pair<int, int>> find_3d_path_modify_kink(
      const Instruction& inst) const {
    const auto path = find_2d_minimum_weight_path(inst);
    auto top_heights = lifted_path_top_heights(path);
    const int parity = count_kink(path, top_heights) % 2;
    if (inst.kink_parity_allowed[parity]) {
      return interpolate_3d_path(path, top_heights);
    } else {
      assert(modify_heights_to_flip_kink_parity(path, top_heights));
      auto path_3d = interpolate_3d_path(path, top_heights);
      assert(prob.count_kink(path_3d) % 2 != parity);
      return path_3d;
    }
  }

  template <RoutingAlgorithm routing_algo>
  std::vector<std::pair<int, int>> find_path(const Instruction& inst) const {
    if constexpr (routing_algo == IgnoreTopologyInfiniteMagic) {
      return find_3d_path_ignore_topology_infinite_magic(inst);
    } else if constexpr (routing_algo == IgnoreTopology) {
      return find_3d_path_ignore_topology(inst);
    } else if constexpr (routing_algo == IgnoreKinkParity) {
      return find_3d_path_ignore_kink(inst);
    } else if constexpr (routing_algo == CareKinkParity ||
                         routing_algo == ModifyHeights) {
      return find_3d_path_modify_kink(inst);
    } else {
      assert(false);
    }
  }

  template <RoutingAlgorithm routing_algo = CareKinkParity>
  MultiTimeSliceScheduleResult schedule() {
    initialize();

    std::vector<MultiTimeSliceSurgeryPath> surgery_paths;
    surgery_paths.reserve(prob.instructions.size());

    for (auto&& inst : prob.instructions) {
      std::vector<std::pair<int, int>> encoded_path;

      encoded_path = find_path<routing_algo>(inst);
      if (encoded_path.empty()) {
        std::stringstream ss;
        ss << "Routing Failed\n"
           << "Inst: " << inst << '\n';
        MultiTimeSliceScheduleResult(prob, surgery_paths).output_index(ss);
        throw RoutingError(ss.str());
      }

      for (auto&& [t, pos] : encoded_path) {
        assert(heights[pos] <= t);
      }
      for (auto&& [t, pos] : encoded_path) {
        heights[pos] = std::max(heights[pos], t + 1);
        elapsed_code_beat = std::max(elapsed_code_beat, t + 1);
      }
      // Cool time for magic state preparation
      if constexpr (routing_algo != IgnoreTopologyInfiniteMagic) {
        if (inst.targetIds[0] == -1) {
          const auto [t, pos] = encoded_path[0];
          assert(prob.is_magic_factory(pos));
          heights[pos] += prob.magic_prep_time;
          elapsed_code_beat = std::max(elapsed_code_beat, heights[pos]);
        }
      }

      surgery_paths.emplace_back(encoded_path);
    }
    return MultiTimeSliceScheduleResult(prob, surgery_paths);
  }
};
