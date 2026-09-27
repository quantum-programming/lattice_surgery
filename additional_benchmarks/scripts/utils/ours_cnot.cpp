// Fixed planar comparison: call the paper allocator, scheduler, and validator.
#include <iostream>
#include "../../../src/cpp/allocator/allocator.hpp"
#include "../../../src/cpp/scheduler/doubleTimeSlice.hpp"
#include "../../../src/cpp/scheduler/scheduleResultValidator.hpp"

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
  auto result = DoubleTimeSliceScheduler(problem).look_ahead_schedule<CareKinkParity>();
  ScheduleResultValidator(result, CareKinkParity).validate_all();

  const int side = (problem.width - 3) / 2;
  std::cout << "{\"depth\":" << result.total_time
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
  for (int x = 2; x < problem.width - 2; x += 2)
    for (int y = 2; y < problem.height - 2; y += 2) {
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
