#pragma once

#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <exception>
#include <functional>
#include <initializer_list>
#include <iomanip>
#include <limits>
#include <map>
#include <queue>
#include <set>
#include <sstream>
#include <tuple>
#include <type_traits>
#include <utility>
#include <vector>

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

  struct TerminalCandidate {
    std::pair<int, int> bus_voxel;
    int patch;
  };

  // Return the attachments at the first code beat when both cells are free.
  std::vector<TerminalCandidate> find_terminal_candidates(
      const Instruction& inst, int operand) const {
    std::vector<TerminalCandidate> candidates;
    for (int code_beat = elapsed_code_beat - 1; code_beat <= elapsed_code_beat;
         code_beat++) {
      auto patches =
          get_available_target_positions(code_beat, inst.targetIds[operand]);
      // The path and tree searches use different factory orders for ties.
      if (inst.targetIds.size() > 2) std::sort(patches.begin(), patches.end());
      for (int patch : patches) {
        for (Direction direction : inst.directions[operand]) {
          for (int bus : next_ancillary_qubits(patch)) {
            if (prob.adjacent_direction(patch, bus) == direction &&
                !is_occupied(code_beat, bus)) {
              candidates.push_back({{code_beat, bus}, patch});
            }
          }
        }
      }
      if (!candidates.empty()) break;
    }
    return candidates;
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

    const auto start_candidates = find_terminal_candidates(inst, 0);
    if (start_candidates.empty()) return {};
    const auto goal_candidates = find_terminal_candidates(inst, 1);
    if (goal_candidates.empty()) return {};

    const int goal_pos = goal_candidates[0].patch;
    std::set<std::pair<int, int>> goal_next_set;
    for (const auto& candidate : goal_candidates) {
      goal_next_set.insert(candidate.bus_voxel);
      assert(candidate.patch == goal_pos);
    }

    std::queue<std::pair<int, int>> q;
    for (const auto& candidate : start_candidates) {
      const auto [start_adj_timing, start_adj_pos] = candidate.bus_voxel;
      if (is_visited(start_adj_timing, start_adj_pos)) continue;
      parent[start_adj_timing & 1][start_adj_pos] = {start_adj_timing,
                                                     candidate.patch};
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
    } else if constexpr (routing_algo == IgnoreMagicTopology) {
      if (inst.targetIds[0] == -1) {
        return find_path_ignore_topology<IgnoreTopologyInfiniteMagic>(inst);
      } else {
        return find_path_ignore_kink_parity(inst);
      }
    } else if constexpr (routing_algo == CareKinkParity ||
                         routing_algo == InvertPath ||
                         routing_algo == InvertTwoCells) {
      return find_and_invert_path<routing_algo>(inst);
    } else {
      assert(false);
    }
  }

  // Type for masking bits that represent terminals.
  using mask_t = std::uint64_t;

  static mask_t all_groups_mask(int group_count) {
    constexpr int mask_bits = std::numeric_limits<mask_t>::digits;
    assert(0 < group_count && group_count <= mask_bits);
    return std::numeric_limits<mask_t>::max() >> (mask_bits - group_count);
  }

  struct TerminalTree {
    std::vector<int> vertices;  // Bus vertex IDs. Empty on failure.
    std::vector<std::pair<int, int>> edges;
    std::vector<int> selected_terminals;  // In operand order.
    mask_t remaining = 0;  // Bit mask of uncovered operand groups.

    TerminalTree() = default;
    explicit TerminalTree(int group_count)
        : selected_terminals(group_count, -1),
          remaining(all_groups_mask(group_count)) {}

    // Record this vertex as the terminal for each newly reached group.
    void append(int vertex, mask_t terminal_mask) {
      vertices.push_back(vertex);
      const mask_t found = terminal_mask & remaining;
      for (int group = 0; group < int(selected_terminals.size()); group++) {
        if (found & (mask_t(1) << group)) selected_terminals[group] = vertex;
      }
      remaining &= ~found;
    }
  };

  // Keep the terminal masks in the first component covering every group.
  static std::vector<mask_t> find_terminal_component(
      const std::vector<std::vector<int>>& adjacency,
      const std::vector<std::vector<int>>& terminal_groups) {
    const int vertex_count = int(adjacency.size());
    const int group_count = int(terminal_groups.size());
    const mask_t all_terminals = all_groups_mask(group_count);

    std::vector<mask_t> terminal_masks(vertex_count);
    for (int group = 0; group < group_count; group++) {
      for (int vertex : terminal_groups[group])
        terminal_masks[vertex] |= mask_t(1) << group;
    }

    std::vector<int> component_at(vertex_count, -1);
    for (int start = 0; start < vertex_count; start++) {
      if (component_at[start] >= 0) continue;
      std::vector<int> dfs_stack{start};
      component_at[start] = start;
      mask_t terminals = 0;
      while (!dfs_stack.empty()) {
        const int vertex = dfs_stack.back();
        dfs_stack.pop_back();
        terminals |= terminal_masks[vertex];
        for (int neighbor : adjacency[vertex]) {
          if (component_at[neighbor] >= 0) continue;
          component_at[neighbor] = start;
          dfs_stack.push_back(neighbor);
        }
      }
      if (terminals == all_terminals) {
        for (int vertex = 0; vertex < vertex_count; vertex++) {
          if (component_at[vertex] != start) terminal_masks[vertex] = 0;
        }
        return terminal_masks;
      }
    }
    return {};
  }

  struct BusSearch {
    std::vector<int> predecessor;
    std::vector<int> distance;
    std::vector<int> bfs_order;

    explicit BusSearch(int vertex_count, bool track_distance = false)
        : predecessor(vertex_count),
          distance(track_distance ? vertex_count : 0) {}

    // Run a multi-source BFS, stopping at the first matching vertex.
    template <typename IsTarget>
    int find(const std::vector<std::vector<int>>& adjacency,
             const std::vector<int>& sources, IsTarget is_target,
             const std::vector<bool>* blocked = nullptr) {
      constexpr int unvisited = -2;
      std::fill(predecessor.begin(), predecessor.end(), unvisited);
      std::fill(distance.begin(), distance.end(), INF);
      bfs_order.clear();
      for (int vertex : sources) {
        if (predecessor[vertex] != unvisited ||
            (blocked && (*blocked)[vertex])) {
          continue;
        }
        predecessor[vertex] = -1;
        if (!distance.empty()) distance[vertex] = 0;
        bfs_order.push_back(vertex);
      }
      for (int index = 0; index < int(bfs_order.size()); index++) {
        const int vertex = bfs_order[index];
        if (is_target(vertex)) return vertex;
        for (int neighbor : adjacency[vertex]) {
          if (predecessor[neighbor] != unvisited ||
              (blocked && (*blocked)[neighbor])) {
            continue;
          }
          predecessor[neighbor] = vertex;
          if (!distance.empty()) distance[neighbor] = distance[vertex] + 1;
          bfs_order.push_back(neighbor);
        }
      }
      return -1;
    }
  };

  // Keep planar edges and, when requested, collect potential relay centers.
  std::vector<std::vector<int>> make_planar_adjacency(
      const std::vector<std::pair<int, int>>& bus_voxels,
      const std::vector<std::vector<int>>& adjacency,
      std::vector<std::pair<int, int>>* transitions = nullptr) const {
    std::vector<std::vector<int>> planar(adjacency.size());
    for (int vertex = 0; vertex < int(adjacency.size()); vertex++) {
      const auto& voxel = bus_voxels[vertex];
      for (int neighbor : adjacency[vertex]) {
        if (prob.voxel_edge_direction(voxel, bus_voxels[neighbor]) !=
            Direction::Z) {
          planar[vertex].push_back(neighbor);
        } else if (transitions && vertex < neighbor) {
          transitions->emplace_back(vertex, neighbor);
        }
      }
    }
    return planar;
  }

  // Attach shortest branches to uncovered groups, trying planar paths first.
  static TerminalTree grow_tree(
      const std::vector<std::vector<int>>& adjacency,
      const std::vector<std::vector<int>>& terminal_groups,
      const std::vector<std::vector<int>>* planar = nullptr) {
    const auto terminal_masks =
        find_terminal_component(adjacency, terminal_groups);
    if (terminal_masks.empty()) return {};

    // Start with the first candidate in the group with the fewest candidates.
    const auto find_tree_seed = [&terminal_groups, &terminal_masks]() {
      int seed = -1;
      int fewest_candidates = INF;
      for (const auto& group : terminal_groups) {
        int count = 0;
        int first = -1;
        for (int vertex : group) {
          if (terminal_masks[vertex] == 0) continue;
          if (first < 0) first = vertex;
          count++;
        }
        if (count < fewest_candidates) {
          seed = first;
          fewest_candidates = count;
        }
      }
      assert(seed >= 0);
      return seed;
    };
    const int seed = find_tree_seed();
    TerminalTree tree(int(terminal_groups.size()));
    tree.append(seed, terminal_masks[seed]);
    BusSearch search(int(adjacency.size()));
    const auto is_target = [&](int vertex) {
      return (terminal_masks[vertex] & tree.remaining) != 0;
    };

    std::vector<int> branch;
    while (tree.remaining != 0) {
      int target = planar ? search.find(*planar, tree.vertices, is_target) : -1;
      if (target < 0) target = search.find(adjacency, tree.vertices, is_target);
      assert(target >= 0);

      // Walk back to the tree, then append from the attachment to the terminal.
      branch.clear();
      int current = target;
      while (search.predecessor[current] >= 0) {
        branch.push_back(current);
        current = search.predecessor[current];
      }
      for (auto vertex = branch.rbegin(); vertex != branch.rend(); vertex++) {
        tree.edges.emplace_back(
            std::minmax(*vertex, search.predecessor[*vertex]));
        tree.append(*vertex, terminal_masks[*vertex]);
      }
    }
    assert(tree.edges.size() + 1 == tree.vertices.size());
    return tree;
  }

  // Attach the nearest two components, using planar paths first.
  TerminalTree find_tree_without_kinks(
      const std::vector<std::pair<int, int>>& bus_voxels,
      const std::vector<std::vector<int>>& adjacency,
      std::vector<std::vector<int>> terminal_groups) const {
    const auto terminal_masks =
        find_terminal_component(adjacency, terminal_groups);
    if (terminal_masks.empty()) return {};
    const int vertex_count = int(bus_voxels.size());
    const int group_count = int(terminal_groups.size());
    const auto outside_component = [&](int vertex) {
      return terminal_masks[vertex] == 0;
    };
    for (auto& group : terminal_groups) {
      group.erase(std::remove_if(group.begin(), group.end(), outside_component),
                  group.end());
    }
    std::vector<std::pair<int, int>> transitions;
    const auto planar =
        make_planar_adjacency(bus_voxels, adjacency, &transitions);
    TerminalTree tree;
    tree.selected_terminals.assign(group_count, -1);
    std::vector<bool> in_tree(vertex_count);
    std::vector<std::vector<int>> forest(group_count);
    int component_count = group_count;

    BusSearch search(vertex_count, true);
    std::vector<bool> reserved(vertex_count);
    std::vector<int> sources;
    std::vector<int> component_at(vertex_count);

    // Find the shortest planar connection between distinct forest components.
    const auto find_planar_connection = [&]() {
      std::pair<int, int> connection{-1, -1};
      int best_distance = INF;
      for (int a : search.bfs_order) {
        for (int b : planar[a]) {
          if (a >= b || component_at[b] < 0 ||
              component_at[a] == component_at[b]) {
            continue;
          }
          const int distance = search.distance[a] + 1 + search.distance[b];
          if (distance >= best_distance) continue;
          best_distance = distance;
          connection = {a, b};
        }
      }
      return connection;
    };

    // Find the shortest non-kink transition between distinct forest components.
    const auto find_non_kink_transition = [&]() {
      std::array<int, 4> non_kink_transition{-1, -1, -1, -1};
      int best_distance = INF;
      for (const auto& [u, v] : transitions) {
        if (in_tree[u] || in_tree[v]) continue;
        for (int a : planar[u]) {
          // A shortest path through an adjacent center enters the leg from it.
          if (component_at[a] < 0 || search.predecessor[a] == u) continue;
          const auto axis =
              prob.voxel_edge_direction(bus_voxels[a], bus_voxels[u]);
          for (int b : planar[v]) {
            if (component_at[b] < 0 || component_at[b] == component_at[a] ||
                search.predecessor[b] == v ||
                prob.voxel_edge_direction(bus_voxels[v], bus_voxels[b]) != axis) {
              continue;
            }
            const int distance = search.distance[a] + 3 + search.distance[b];
            if (distance >= best_distance) continue;
            best_distance = distance;
            non_kink_transition = {a, u, v, b};
          }
        }
      }
      return non_kink_transition;
    };

    // Join two predecessor paths, with transition between them if present.
    const auto restore_connecting_path =
        [&search](int first, int second,
                  std::initializer_list<int> transition = {}) {
          std::vector<int> path;
          int vertex = first;
          while (vertex >= 0) {
            path.push_back(vertex);
            vertex = search.predecessor[vertex];
          }
          std::reverse(path.begin(), path.end());
          path.insert(path.end(), transition);
          vertex = second;
          while (vertex >= 0) {
            path.push_back(vertex);
            vertex = search.predecessor[vertex];
          }
          return path;
        };

    // Returns two component IDs to be connected and the connecting path.
    const auto find_connecting_path =
        [&]() -> std::tuple<int, int, std::vector<int>> {
      std::fill(component_at.begin(), component_at.end(), -1);
      sources.clear();

      // A single bus vertex connects two data operands.
      for (int group = 0; group < group_count; group++) {
        if (forest[group].empty() && tree.selected_terminals[group] >= 0) {
          continue;
        }
        const auto& vertices =
            forest[group].empty() ? terminal_groups[group] : forest[group];
        for (int vertex : vertices) {
          if (reserved[vertex] || component_at[vertex] == group) continue;
          // A shared source joins two components without a bus edge.
          if (component_at[vertex] >= 0) {
            return {component_at[vertex], group, std::vector<int>{vertex}};
          }
          component_at[vertex] = group;
          sources.push_back(vertex);
        }
      }

      // A planar path (of length >= 2) connects two data operands.
      search.find(planar, sources, [](int) { return false; }, &reserved);
      for (int vertex : search.bfs_order) {
        const int previous = search.predecessor[vertex];
        if (previous >= 0) component_at[vertex] = component_at[previous];
      }
      const auto [left, right] = find_planar_connection();
      if (left >= 0) {
        return {component_at[left], component_at[right],
                restore_connecting_path(left, right)};
      }

      // A non-kink transition is required to connect two data operands.
      const auto [a, u, v, b] = find_non_kink_transition();
      if (a < 0) return {};
      auto path = restore_connecting_path(a, b, {u, v});
      reserved[u] = reserved[v] = true;
      return {component_at[a], component_at[b], std::move(path)};
    };

    while (component_count > 1) {
      const auto [first, second, path] = find_connecting_path();
      if (path.empty()) return {};
      if (forest[first].empty()) tree.selected_terminals[first] = path.front();
      if (forest[second].empty()) tree.selected_terminals[second] = path.back();
      for (int vertex : path) {
        if (in_tree[vertex]) continue;
        in_tree[vertex] = true;
        forest[first].push_back(vertex);
      }
      for (int index = 1; index < int(path.size()); index++) {
        tree.edges.emplace_back(std::minmax(path[index - 1], path[index]));
      }
      forest[first].insert(forest[first].end(), forest[second].begin(),
                           forest[second].end());
      forest[second].clear();
      component_count--;
    }
    const auto connected =
        std::find_if(forest.begin(), forest.end(),
                     [](const auto& vertices) { return !vertices.empty(); });
    assert(connected != forest.end());
    tree.vertices = std::move(*connected);
    assert(tree.edges.size() + 1 == tree.vertices.size());
    return tree;
  }

  // Build the free bus graph and attach the earliest terminal candidates.
  template <RoutingAlgorithm routing_algo, bool prefer_planar = true>
  MultiTimeSliceSurgeryTree find_tree(const Instruction& inst,
                                      int operand_offset) const {
    static_assert(routing_algo == IgnoreKinkParity ||
                  routing_algo == CareKinkParity);
    assert(0 <= operand_offset);
    assert(operand_offset <= int(inst.targetIds.size()) - 2);

    const int first_code_beat = elapsed_code_beat - 1;
    std::vector<std::vector<TerminalCandidate>> operand_terminals;
    for (int index = operand_offset; index < int(inst.targetIds.size());
         index++) {
      auto candidates = find_terminal_candidates(inst, index);
      if (candidates.empty()) return {};
      operand_terminals.push_back(std::move(candidates));
    }

    // Give the free bus voxels consecutive IDs in (code_beat, position) order.
    std::vector<std::pair<int, int>> bus_voxels;
    std::array<std::vector<int>, 2> vertex_at;
    for (int slice = 0; slice < 2; slice++) {
      const int code_beat = first_code_beat + slice;
      vertex_at[slice].assign(prob.chip_size, -1);
      for (int pos = 0; pos < prob.chip_size; pos++) {
        if (prob.is_data_qubit(pos) || is_occupied(code_beat, pos)) continue;
        vertex_at[slice][pos] = int(bus_voxels.size());
        bus_voxels.emplace_back(code_beat, pos);
      }
    }

    std::vector<std::vector<int>> adjacency(bus_voxels.size());
    for (int vertex = 0; vertex < int(bus_voxels.size()); vertex++) {
      const auto [code_beat, pos] = bus_voxels[vertex];
      const int slice = code_beat - first_code_beat;
      auto& neighbors = adjacency[vertex];
      for (int neighbor_pos : adj_ancillary[pos]) {
        const int neighbor = vertex_at[slice][neighbor_pos];
        if (neighbor >= 0) neighbors.push_back(neighbor);
      }
      const int time_neighbor = vertex_at[1 - slice][pos];
      if (time_neighbor >= 0) neighbors.push_back(time_neighbor);
    }

    // Encode the attachment candidates as bus vertex IDs for the solver.
    std::vector<std::vector<int>> terminal_groups;
    for (const auto& candidates : operand_terminals) {
      auto& group = terminal_groups.emplace_back();
      for (const auto& candidate : candidates) {
        const auto [code_beat, bus] = candidate.bus_voxel;
        const int vertex = vertex_at[code_beat - first_code_beat][bus];
        assert(vertex >= 0);
        group.push_back(vertex);
      }
    }

    TerminalTree bus_tree;
    if constexpr (routing_algo == CareKinkParity) {
      bus_tree = find_tree_without_kinks(bus_voxels, adjacency,
                                         std::move(terminal_groups));
    } else if constexpr (prefer_planar) {
      const auto planar = make_planar_adjacency(bus_voxels, adjacency);
      bus_tree = grow_tree(adjacency, terminal_groups, &planar);
    } else {
      bus_tree = grow_tree(adjacency, terminal_groups);
    }
    if (bus_tree.vertices.empty()) return {};

    // Attach the operand leaves to the selected bus vertices.
    assert(bus_tree.selected_terminals.size() == operand_terminals.size());

    MultiTimeSliceSurgeryTree tree;
    tree.voxels.reserve(bus_tree.vertices.size() + operand_terminals.size());
    tree.edges.reserve(bus_tree.edges.size() + operand_terminals.size());
    for (int vertex : bus_tree.vertices) {
      tree.voxels.push_back(bus_voxels[vertex]);
    }
    for (const auto& [first, second] : bus_tree.edges) {
      tree.edges.emplace_back(bus_voxels[first], bus_voxels[second]);
    }
    for (int index = 0; index < int(operand_terminals.size()); index++) {
      const auto& candidates = operand_terminals[index];
      const auto& terminal = bus_voxels[bus_tree.selected_terminals[index]];
      const auto selected =
          std::find_if(candidates.begin(), candidates.end(),
                       [&terminal](const auto& candidate) {
                         return candidate.bus_voxel == terminal;
                       });
      assert(selected != candidates.end());
      const auto& leaf =
          tree.leaves.emplace_back(terminal.first, selected->patch);
      tree.voxels.push_back(leaf);
      tree.edges.emplace_back(std::minmax(leaf, terminal));
    }
    return tree;
  }

  template <RoutingAlgorithm routing_algo, bool prefer_planar = true>
  MultiTimeSliceSurgeryTree find_tree(const Instruction& inst) const {
    assert(inst.targetIds.size() > 2);
    if constexpr (routing_algo == IgnoreKinkParity) {
      return find_tree<IgnoreKinkParity, prefer_planar>(inst, 0);
    } else if constexpr (routing_algo == CareKinkParity) {
      return find_tree<CareKinkParity>(inst, 0);
    } else if constexpr (routing_algo == IgnoreMagicTopology) {
      assert(inst.targetIds[0] == -1);
      return find_tree<IgnoreKinkParity, prefer_planar>(inst, 1);
    } else {
      static_assert(routing_algo == IgnoreTopology ||
                        routing_algo == IgnoreTopologyInfiniteMagic,
                    "Unsupported multibody routing algorithm");
      // Multibody instructions currently all use magic states.
      assert(inst.targetIds[0] == -1);
      MultiTimeSliceSurgeryTree tree;
      tree.voxels = find_path_ignore_topology<routing_algo>(inst);
      tree.leaves = tree.voxels;
      return tree;
    }
  }

  template <typename Operands>
  void commit_route(const std::vector<std::pair<int, int>>& voxels,
                    const Operands& operands, bool uses_magic) {
    for (const auto& [code_beat, pos] : voxels) {
      assert(!is_occupied(code_beat, pos));
      single_occupy(code_beat, pos);
    }
    // Reserve the older slice of every late operand to preserve dependencies.
    const int older_code_beat = elapsed_code_beat - 1;
    for (const auto& [code_beat, pos] : operands) {
      if (code_beat == elapsed_code_beat &&
          !is_occupied(older_code_beat, pos)) {
        single_occupy(older_code_beat, pos);
      }
    }
    if (uses_magic) {
      const auto [code_beat, pos] = operands[0];
      assert(prob.is_magic_factory(pos));
      // Include the surgery code beat and any reservation of the older slice.
      const int cool_time =
          1 + prob.magic_prep_time + (code_beat + 1 - elapsed_code_beat);
      occupy(pos, cool_time);
    }
  }

  template <RoutingAlgorithm routing_algo, bool prefer_planar = true,
            typename Route>
  bool find_and_commit_route(const Instruction& inst, Route& route) {
    const bool uses_magic = inst.targetIds[0] == -1 &&
                            routing_algo != IgnoreMagicTopology &&
                            routing_algo != IgnoreTopologyInfiniteMagic;
    if constexpr (std::is_same_v<Route, MultiTimeSliceSurgeryRoute>) {
      if (inst.targetIds.size() > 2) {
        auto tree = find_tree<routing_algo, prefer_planar>(inst);
        if (tree.voxels.empty()) return false;
        commit_route(tree.voxels, tree.leaves, uses_magic);
        route = std::move(tree);
        return true;
      }
    }

    auto encoded_path = find_path<routing_algo>(inst);
    if (encoded_path.empty()) return false;
    const std::array operands{encoded_path[0], encoded_path.back()};
    commit_route(encoded_path, operands, uses_magic);
    route = MultiTimeSliceSurgeryPath(std::move(encoded_path));
    return true;
  }

  template <typename Route>
  [[noreturn]] void throw_routing_error(
      const Instruction& inst, const std::vector<Route>& routes) const {
    std::stringstream ss;
    ss << "Routing Failed\n"
       << "Inst: " << inst << '\n';
    if constexpr (std::is_same_v<Route, MultiTimeSliceSurgeryPath>) {
      MultiTimeSliceScheduleResult(prob, routes).output_index(ss);
    }
    throw RoutingError(ss.str());
  }

  template <typename Result>
  using RouteFor = std::conditional_t<
      std::is_same_v<Result, MultiTimeSliceMultiBodyScheduleResult>,
      MultiTimeSliceSurgeryRoute, MultiTimeSliceSurgeryPath>;

  template <RoutingAlgorithm routing_algo = CareKinkParity,
            typename Result = MultiTimeSliceScheduleResult,
            bool prefer_planar = true>
  Result naive_schedule() {
    initialize();
    std::vector<RouteFor<Result>> routes(prob.instructions.size());

    for (auto&& inst : prob.instructions) {
      auto& route = routes[inst.instId];
      while (!find_and_commit_route<routing_algo, prefer_planar>(inst, route)) {
        if (occupied[0].all_available() && occupied[1].all_available()) {
          throw_routing_error(inst, routes);
        }
        wait_code_beat();
      }
    }

    return Result(prob, std::move(routes));
  }

  template <RoutingAlgorithm routing_algo = CareKinkParity,
            typename Result = MultiTimeSliceScheduleResult,
            bool prefer_planar = true>
  Result look_ahead_schedule() {
    initialize();
    std::vector<RouteFor<Result>> routes(prob.instructions.size());
    auto reordered_instructions = reorder_instructions(prob);
    InstructionDependencyManager manager(prob.data_qubits.size(),
                                         reordered_instructions);

    while (!manager.all_finished()) {
      for (auto it = manager.begin(); it != manager.end();) {
        int inst_index = *it;
        const Instruction& inst = reordered_instructions[inst_index];

        if (find_and_commit_route<routing_algo, prefer_planar>(
                inst, routes[inst.instId])) {
          it = manager.process_instruction(inst_index);
        } else {
          it++;
          if (occupied[0].all_available() && occupied[1].all_available()) {
            throw_routing_error(inst, routes);
          }
        }
      }

      wait_code_beat();
    }

    return Result(prob, std::move(routes));
  }
};
