#pragma once

#include <variant>

#include "../util/problem.hpp"
#include "scheduleResult.hpp"

class ScheduleResultValidator {
 public:
  struct ValidationFlags {
    const bool require_logical_topology;
    const bool require_msf;
    const bool require_msf_topology;
    const bool require_kink_parity;

    constexpr ValidationFlags(bool logical_topology = true, bool msf = true,
                              bool msf_topology = true, bool kink_parity = true)
        : require_logical_topology(logical_topology),
          require_msf(msf),
          require_msf_topology(msf_topology),
          require_kink_parity(kink_parity) {
      // Checking the MSF connection requires a placed factory and a checked
      // logical route. Kink parity requires the full topology.
      if (require_msf_topology) {
        assert(require_msf && require_logical_topology);
      }
      if (require_kink_parity) assert(require_msf_topology);
    }
  };

  static ValidationFlags get_validation_flags(RoutingAlgorithm algo) {
    if (algo == IgnoreTopologyInfiniteMagic) {
      return {false, false, false, false};
    }
    if (algo == IgnoreTopology) {
      return {false, true, false, false};
    }
    if (algo == IgnoreMagicTopology) {
      return {true, false, false, false};
    }
    if (algo == IgnoreKinkParity) {
      return {true, true, true, false};
    }
    if (algo == CareKinkParity) {
      return {true, true, true, true};
    }

    return {true, true, true, true};
  }

  ScheduleResultValidator(const SingleTimeSliceScheduleResult& result,
                          ValidationFlags flags)
      : prob(result.prob),
        result(MultiTimeSliceScheduleResult(result)),
        validation_flags(flags) {}
  ScheduleResultValidator(const MultiTimeSliceScheduleResult& result,
                          ValidationFlags flags)
      : prob(result.prob), result(result), validation_flags(flags) {}
  ScheduleResultValidator(const MultiTimeSliceMultiBodyScheduleResult& result,
                          ValidationFlags flags)
      : prob(result.prob), result(result), validation_flags(flags) {}

  template <typename Result>
  ScheduleResultValidator(const Result& result, RoutingAlgorithm algo)
      : ScheduleResultValidator(result, get_validation_flags(algo)) {}

  void validate_all() {
    if (const auto* path_schedule =
            std::get_if<MultiTimeSliceScheduleResult>(&result)) {
      validate_routes(path_schedule->surgery_paths);
    } else {
      const auto& multibody_schedule =
          std::get<MultiTimeSliceMultiBodyScheduleResult>(result);
      validate_routes(multibody_schedule.surgery_routes);
    }
    packing_is_valid();
  }

  void packing_is_valid() {
    std::visit([this](const auto& schedule) { validate_packing(schedule); },
               result);
  }

  void operands_are_correct(const Instruction& inst,
                            const MultiTimeSliceSurgeryPath& path) const {
    assert(inst.targetIds.size() == 2);
    if (inst.targetIds[0] == -1 && path.timing_positions.size() == 1) {
      assert(!validation_flags.require_msf);
    } else {
      operand_matches_target(path.timing_positions.front().second,
                             inst.targetIds[0]);
    }
    operand_matches_target(path.timing_positions.back().second,
                           inst.targetIds[1]);
  }

  void operand_matches_target(int operand, int target_id) const {
    if (target_id == -1) {
      assert(prob.is_magic_factory(operand));
    } else {
      const int target_pos = prob.data_qubits[target_id];
      assert(operand == target_pos);
    }
  }

  void path_is_connected(const MultiTimeSliceSurgeryPath& path) const {
    for (int pos_index = 0; pos_index < int(path.timing_positions.size()) - 1;
         pos_index++) {
      assert(voxels_are_adjacent(path.timing_positions[pos_index],
                                 path.timing_positions[pos_index + 1]));
    }
  }

  void validate_path_boundaries(const Instruction& inst,
                                const MultiTimeSliceSurgeryPath& path) const {
    const auto& voxels = path.timing_positions;
    if (is_transversal_cx(inst, voxels.front(), voxels.back(), voxels.size())) {
      return;
    }
    validate_boundary_condition(voxels.front(), voxels[1], inst.directions[0]);
    validate_boundary_condition(voxels.back(), voxels[voxels.size() - 2],
                                inst.directions[1]);
  }

  void kink_parity_is_valid(const Instruction& inst,
                            const MultiTimeSliceSurgeryPath& path) const {
    const auto& voxels = path.timing_positions;
    if (is_transversal_cx(inst, voxels.front(), voxels.back(), voxels.size())) {
      return;
    }

    assert(inst.kink_parity_allowed[prob.count_kink(voxels) % 2]);
  }

 private:
  template <typename Route>
  void validate_routes(const std::vector<Route>& routes) const {
    assert(routes.size() == prob.instructions.size());
    for (int index = 0; index < int(prob.instructions.size()); index++) {
      validate_surgery(prob.instructions[index], routes[index]);
    }
  }

  void validate_surgery(const Instruction& inst,
                        const MultiTimeSliceSurgeryRoute& route) const {
    std::visit(
        [this, &inst](const auto& surgery) { validate_surgery(inst, surgery); },
        route);
  }

  void validate_surgery(const Instruction& inst,
                        const MultiTimeSliceSurgeryPath& path) const {
    assert(!path.timing_positions.empty());
    operands_are_correct(inst, path);

    const bool check_topology = inst.targetIds[0] == -1
                                    ? validation_flags.require_msf_topology
                                    : validation_flags.require_logical_topology;
    if (check_topology) {
      assert(path.timing_positions.size() >= 2);
      path_is_connected(path);
      validate_path_boundaries(inst, path);
    }

    if (validation_flags.require_kink_parity) {
      kink_parity_is_valid(inst, path);
    }
  }

  void validate_surgery(const Instruction& inst,
                        const MultiTimeSliceSurgeryTree& tree) const {
    assert(inst.targetIds.size() > 2);
    assert(!tree.voxels.empty());
    for (const auto& voxel : tree.voxels) {
      assert(0 <= voxel.first);
      assert(0 <= voxel.second && voxel.second < prob.chip_size);
    }

    const auto neighbors = tree.make_adjacency();
    const std::set<std::pair<int, int>> leaves(tree.leaves.begin(),
                                               tree.leaves.end());
    assert(leaves.size() == tree.leaves.size());
    const int operand_offset = validate_tree_operands(inst, tree, neighbors);

    // An operand can be isolated when its topology is relaxed.
    size_t isolated_operands = 0;
    for (const auto& [voxel, adjacent] : neighbors) {
      if (leaves.count(voxel)) {
        assert(prob.is_data_qubit(voxel.second));
        assert(adjacent.size() <= 1);
        if (adjacent.empty()) isolated_operands++;
      } else {
        assert(!prob.is_data_qubit(voxel.second));
        assert(adjacent.size() >= 2);
      }
    }

    validate_tree_topology(inst, tree, neighbors, operand_offset,
                           isolated_operands);

    if (validation_flags.require_kink_parity) {
      assert(prob.has_valid_multibody_segments(neighbors, tree.leaves.front()));
    }
  }

  int validate_tree_operands(
      const Instruction& inst, const MultiTimeSliceSurgeryTree& tree,
      const std::map<std::pair<int, int>, std::vector<std::pair<int, int>>>&
          neighbors) const {
    // An unplaced magic-state factory omits the first operand's leaf.
    const bool unplaced_magic = inst.targetIds.front() == -1 &&
                                tree.leaves.size() + 1 == inst.targetIds.size();
    if (validation_flags.require_msf) assert(!unplaced_magic);
    const int operand_offset = unplaced_magic ? 1 : 0;
    assert(int(tree.leaves.size()) + operand_offset ==
           int(inst.targetIds.size()));
    for (int index = 0; index < int(tree.leaves.size()); index++) {
      const auto& leaf = tree.leaves[index];
      assert(neighbors.count(leaf));
      operand_matches_target(leaf.second,
                             inst.targetIds[index + operand_offset]);
    }
    return operand_offset;
  }

  void validate_tree_topology(
      const Instruction& inst, const MultiTimeSliceSurgeryTree& tree,
      const std::map<std::pair<int, int>, std::vector<std::pair<int, int>>>&
          neighbors,
      int operand_offset, size_t isolated_operands) const {
    if (!tree.edges.empty()) {
      const auto& first_voxel = tree.edges[0].first;
      std::vector<std::pair<int, int>> dfs_stack{first_voxel};
      std::set<std::pair<int, int>> visited{first_voxel};
      while (!dfs_stack.empty()) {
        const auto voxel = dfs_stack.back();
        dfs_stack.pop_back();
        for (const auto& neighbor : neighbors.at(voxel)) {
          if (!visited.count(neighbor)) {
            visited.insert(neighbor);
            if (validation_flags.require_logical_topology) {
              assert(voxels_are_adjacent(voxel, neighbor));
            }
            dfs_stack.push_back(neighbor);
          }
        }
      }
      // Every edge must belong to the DFS tree.
      // Isolated vertices are allowed here (MSF).
      assert(tree.edges.size() + 1 == visited.size());
      assert(visited.size() + isolated_operands == tree.voxels.size());
    }

    const bool skip_msf = inst.targetIds[operand_offset] == -1 &&
                          !validation_flags.require_msf_topology;
    if (skip_msf) assert(neighbors.at(tree.leaves[0]).empty());
    if (!validation_flags.require_logical_topology) return;

    for (int index = int(skip_msf); index < int(tree.leaves.size()); index++) {
      const auto& leaf = tree.leaves[index];
      const auto& adjacent = neighbors.at(leaf);
      assert(adjacent.size() == 1);
      validate_boundary_condition(leaf, adjacent.front(),
                                  inst.directions[index + operand_offset]);
    }
  }

  bool voxels_are_adjacent(const std::pair<int, int>& first,
                           const std::pair<int, int>& second) const {
    const auto [first_beat, first_pos] = first;
    const auto [second_beat, second_pos] = second;
    const bool spatially_adjacent =
        first_beat == second_beat && prob.is_adjacent(first_pos, second_pos);
    const bool temporally_adjacent =
        std::abs(first_beat - second_beat) == 1 && first_pos == second_pos;
    return spatially_adjacent || temporally_adjacent;
  }

  bool is_transversal_cx(const Instruction& inst,
                         const std::pair<int, int>& first,
                         const std::pair<int, int>& last,
                         size_t voxel_count) const {
    return inst.gate == "CX" && voxel_count == 2 && first.first == last.first &&
           prob.adjacent_direction(first.second, last.second) == Direction::Z;
  }

  void validate_boundary_condition(
      const std::pair<int, int>& endpoint, const std::pair<int, int>& neighbor,
      const std::vector<Direction>& allowed_directions) const {
    assert(endpoint.first == neighbor.first);
    assert(
        std::count(allowed_directions.begin(), allowed_directions.end(),
                   prob.adjacent_direction(endpoint.second, neighbor.second)));
  }

  template <typename Schedule>
  void validate_packing(const Schedule& schedule) {
    std::vector<std::vector<int>> path_indices(
        schedule.total_time, std::vector<int>(prob.chip_size));

    for (int index = 0; index < int(prob.instructions.size()); index++) {
      for (const auto& [timing, pos] : schedule.voxels_at(index)) {
        assert(0 <= timing && timing < schedule.total_time);
        assert(0 <= pos && pos < prob.chip_size);
        // Verify that no two instructions occupy the same voxel.
        assert(path_indices[timing][pos] == 0);
        path_indices[timing][pos] = index + 1;
      }
    }

    // For each data qubit, check the order of the path.
    for (auto&& pos : prob.data_qubits) {
      int last_inst_index = 0;
      for (int timing = 0; timing < schedule.total_time; timing++) {
        if (path_indices[timing][pos]) {
          assert(path_indices[timing][pos] >= last_inst_index);
          last_inst_index = path_indices[timing][pos];
        }
      }
    }

    // Check the generation time of the magic state factory.
    for (auto&& pos : prob.ms_factories) {
      int last_free_timing = 0;
      for (int timing = 0; timing < schedule.total_time; timing++) {
        if (path_indices[timing][pos]) {
          assert(timing - last_free_timing >= prob.magic_prep_time);
          last_free_timing = timing + 1;
        }
      }
    }
  }

  Problem prob;
  std::variant<MultiTimeSliceScheduleResult,
               MultiTimeSliceMultiBodyScheduleResult>
      result;
  ValidationFlags validation_flags;
};
