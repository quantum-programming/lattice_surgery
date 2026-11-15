// Fixed planar comparison: call the paper allocator, scheduler, and validator.
#include <iostream>
#include "../../src/cpp/allocator/allocator.hpp"
#include "../../src/cpp/scheduler/doubleTimeSlice.hpp"
#include "../../src/cpp/scheduler/scheduleResultValidator.hpp"

static void print_xyz(const Problem& problem, int position, int time) {
  auto [x, y, z] = problem.position_to_xyz(position);
  std::cout << "[" << x << "," << y << "," << time << "]";
}

int main(int argc, char** argv) {
  if (argc != 2) return 2;
  Problem problem(argv[1], 2);
  for (const auto& instruction : problem.instructions)
    if (instruction.gate != "CX") return 2;

  Allocator().allocate(problem, "outer", "SA", 1, 0.1, 1000000);
  // CNOT-only benchmark: remove the outer ring containing all MSF sites.
  // Allocator::_base_for_allocation puts data candidates at 2,4,...;
  // translating by (-1,-1) leaves a one-site routing margin in the new grid.
  std::vector<std::tuple<int, int, int>> data_positions;
  for (int position : problem.data_qubits) {
    auto [x, y, z] = problem.position_to_xyz(position);
    assert(x > 0 && x < problem.width - 1);
    assert(y > 0 && y < problem.height - 1);
    data_positions.emplace_back(x - 1, y - 1, z);
  }
  problem.width -= 2;
  problem.height -= 2;
  problem.chip_size = problem.width * problem.height * problem.layer_count;
  problem.ms_factories.clear();
  problem.position2qubit_index.clear();
  for (size_t i = 0; i < data_positions.size(); ++i) {
    int position = problem.xyz_to_position(data_positions[i]);
    problem.data_qubits[i] = position;
    problem.position2qubit_index[position] = i;
  }
  auto result = DoubleTimeSliceScheduler(problem).look_ahead_schedule<CareKinkParity>();
  ScheduleResultValidator(result, CareKinkParity).validate_all();

  const int side = (problem.width - 1) / 2;
  std::cout << "{\"total_execution_time\":" << result.total_time
            << ",\"width\":" << problem.width
            << ",\"height\":" << problem.height
            << ",\"allocated_sites\":" << problem.chip_size
            << ",\"data_slots\":" << side * side
            << ",\"active_data\":" << problem.data_qubits.size()
            << ",\"factory_sites\":" << problem.ms_factories.size()
            << ",\"occupied_volume\":" << result.compute_circuit_volume()
            << ",\"geometry\":{\"data\":[";
  for (size_t i = 0; i < problem.data_qubits.size(); ++i) {
    if (i) std::cout << ",";
    print_xyz(problem, problem.data_qubits[i], 0);
  }
  std::cout << "],\"factories\":[";
  for (size_t i = 0; i < problem.ms_factories.size(); ++i) {
    if (i) std::cout << ",";
    print_xyz(problem, problem.ms_factories[i], 0);
  }
  std::cout << "],\"data_slot_positions\":[";
  bool first = true;
  for (int x = 1; x < problem.width - 1; x += 2)
    for (int y = 1; y < problem.height - 1; y += 2) {
      if (!first) std::cout << ",";
      first = false;
      std::cout << "[" << x << "," << y << ",0]";
    }
  std::cout << "],\"paths\":[";
  for (size_t i = 0; i < result.surgery_paths.size(); ++i) {
    if (i) std::cout << ",";
    std::cout << "[";
    auto points = result.surgery_paths[i].getTimingPositions();
    for (size_t j = 0; j < points.size(); ++j) {
      if (j) std::cout << ",";
      print_xyz(problem, points[j].second, points[j].first);
    }
    std::cout << "]";
  }
  std::cout << "]}}\n";
}
