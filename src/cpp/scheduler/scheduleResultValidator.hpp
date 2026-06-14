#pragma once

#include "../util/problem.hpp"
#include "scheduleResult.hpp"

class ScheduleResultValidator {
 public:
  struct ValidationFlags {
    bool check_cx_topology = true;
    bool check_magic_operand = true;
    bool check_magic_topology = true;
    bool check_kink = true;
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

  ScheduleResultValidator(SingleTimeSliceScheduleResult result,
                          ValidationFlags flags)
      : prob(result.prob), result(result), validation_flags(flags) {}
  ScheduleResultValidator(MultiTimeSliceScheduleResult result,
                          ValidationFlags flags)
      : prob(result.prob), result(result), validation_flags(flags) {}

  ScheduleResultValidator(SingleTimeSliceScheduleResult result,
                          RoutingAlgorithm algo)
      : ScheduleResultValidator(result, get_validation_flags(algo)) {}
  ScheduleResultValidator(MultiTimeSliceScheduleResult result,
                          RoutingAlgorithm algo)
      : ScheduleResultValidator(result, get_validation_flags(algo)) {}

  void operand_matches_target(int operand, int target_id) const {
    if (target_id == -1) {
      if (validation_flags.check_magic_operand) {
        assert(prob.is_magic_factory(operand));
      }
    } else {
      const int target_pos = prob.data_qubits[target_id];
      assert(operand == target_pos);
    }
  }

  void operands_are_correct(const Instruction& inst,
                            const MultiTimeSliceSurgeryPath& path) const {
    assert(inst.targetIds.size() == 2);
    operand_matches_target(path.timing_positions.front().second,
                           inst.targetIds[0]);
    operand_matches_target(path.timing_positions.back().second,
                           inst.targetIds[1]);
  }

  void path_is_connected(const MultiTimeSliceSurgeryPath& path) {
    for (int pos_index = 0; pos_index < int(path.timing_positions.size()) - 1;
         pos_index++) {
      const auto [t1, pos1] = path.timing_positions[pos_index];
      const auto [t2, pos2] = path.timing_positions[pos_index + 1];
      bool spatially_adjacent = (t1 == t2 && prob.is_adjacent(pos1, pos2));
      bool temporally_adjacent = (std::abs(t1 - t2) == 1 && pos1 == pos2);
      assert(spatially_adjacent || temporally_adjacent);
    }
  }

  void directions_are_correct(const Instruction& inst,
                              const MultiTimeSliceSurgeryPath& path) const {
    const int path_length = path.timing_positions.size();

    const auto [t0, pos0] = path.timing_positions[0];
    const auto [t1, pos1] = path.timing_positions[1];
    assert(t0 == t1);
    const Direction first_direction = prob.adjacent_direction(pos0, pos1);

    // Transversal CNOT is okay.
    if (inst.gate == "CX" && path_length == 2 &&
        first_direction == Direction::Z) {
      return;
    }

    auto [t2, pos2] = path.timing_positions[path_length - 2];
    auto [t3, pos3] = path.timing_positions[path_length - 1];
    assert(t2 == t3);
    const Direction last_direction = prob.adjacent_direction(pos2, pos3);

    assert(std::count(inst.directions[0].begin(), inst.directions[0].end(),
                      first_direction));
    assert(std::count(inst.directions[1].begin(), inst.directions[1].end(),
                      last_direction));
  }

  void packing_is_valid() {
    std::vector<std::vector<int>> path_indices(
        result.total_time, std::vector<int>(prob.chip_size));

    for (int index = 0; index < int(prob.instructions.size()); index++) {
      const auto& path = result.surgery_paths[index];
      for (auto&& [timing, pos] : path.timing_positions) {
        // Verify that the paths do not intersect.
        assert(path_indices[timing][pos] == 0);
        path_indices[timing][pos] = index + 1;
      }
    }

    // For each data qubit, check the order of the path.
    for (auto&& pos : prob.data_qubits) {
      int last_inst_index = 0;
      for (int timing = 0; timing < result.total_time; timing++) {
        if (path_indices[timing][pos]) {
          assert(path_indices[timing][pos] >= last_inst_index);
          last_inst_index = path_indices[timing][pos];
        }
      }
    }

    // Check the generation time of the magic state factory.
    for (auto&& pos : prob.ms_factories) {
      int last_free_timing = 0;
      for (int timing = 0; timing < result.total_time; timing++) {
        if (path_indices[timing][pos]) {
          assert(timing - last_free_timing >= prob.magic_prep_time);
          last_free_timing = timing + 1;
        }
      }
    }
  }

  void kink_parity_is_valid(const Instruction& inst,
                            const MultiTimeSliceSurgeryPath& path) {
    // Skip the transversal CX.
    if (inst.gate == "CX" && path.timing_positions.size() == 2) {
      auto [t0, pos0] = path.timing_positions[0];
      auto [t1, pos1] = path.timing_positions[1];
      if (t0 == t1 && prob.adjacent_direction(pos0, pos1) == Direction::Z) {
        return;
      }
    }

    const int parity = prob.count_kink(path.timing_positions) % 2;
    assert(inst.kink_parity_allowed[parity]);
  }

  void validate_all() {
    packing_is_valid();

    for (int index = 0; index < int(prob.instructions.size()); index++) {
      const auto& inst = prob.instructions[index];
      const auto& path = result.surgery_paths[index];

      operands_are_correct(inst, path);

      bool check_topology = inst.gate == "CX"
                                ? validation_flags.check_cx_topology
                                : validation_flags.check_magic_topology;
      if (check_topology) {
        path_is_connected(path);
        directions_are_correct(inst, path);
      }

      if (validation_flags.check_kink) {
        kink_parity_is_valid(inst, path);
      }
    }
  }

 private:
  Problem prob;
  MultiTimeSliceScheduleResult result;
  ValidationFlags validation_flags;
};
