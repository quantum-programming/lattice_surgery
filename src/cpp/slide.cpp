#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <random>

#include "allocator/allocator.hpp"
#include "scheduler/doubleTimeSlice.hpp"
#include "scheduler/projective.hpp"
#include "scheduler/singleTimeSlice.hpp"

int main() {
  Problem prob("../../data/example/slide.in");

  prob.width = 5;
  prob.height = 5;
  prob.layer_count = 1;
  prob.chip_size = prob.width * prob.height * prob.layer_count;
  prob.data_qubits[0] = prob.xyz_to_position({1, 1, 0});
  prob.data_qubits[1] = prob.xyz_to_position({3, 3, 0});
  prob.data_qubits[2] = prob.xyz_to_position({3, 1, 0});
  prob.ms_factories.clear();
  prob.ms_factories.push_back(prob.xyz_to_position({1, 3, 0}));

  for (int i = 0; i < int(prob.data_qubits.size()); i++) {
    prob.position2qubit_index[prob.data_qubits[i]] = i;
  }
  for (int i = 0; i < int(prob.ms_factories.size()); i++) {
    prob.position2qubit_index[prob.ms_factories[i]] =
        prob.data_qubits.size() + i;
  }

  ProjectiveScheduler projective_scheduler(prob);
  auto projective_res = projective_scheduler.schedule<CareKinkParity>();
  std::ofstream projective_ofs("../../out/example/slide_projective.out");
  projective_res.to_visualizer(projective_ofs, 1000);

  DoubleTimeSliceScheduler double_scheduler(prob);
  auto double_res = double_scheduler.look_ahead_schedule<CareKinkParity>();
  std::ofstream double_ofs("../../out/example/slide_double.out");
  double_res.to_visualizer(double_ofs, 1000);

  return 0;
}
