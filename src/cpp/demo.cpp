#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <random>

#include "allocator/allocator.hpp"
#include "scheduler/projective.hpp"

// make demo files for the visualizer

int main() {
  {
    Problem prob("../../data/example/demo.in");

    Allocator allocator;
    allocator.allocate(prob, "outer", "naive", 2, 0.1, 10000);

    ProjectiveScheduler scheduler(prob);
    auto care_kink = scheduler.schedule<IgnoreKinkParity>();

    std::ofstream ofs("../../out/example/demo_outer.out");
    care_kink.to_visualizer(ofs, 1000);
  }

  {
    Problem prob("../../data/example/demo.in");

    Allocator allocator;
    allocator.allocate(prob, "inner", "naive", 2, 0.1, 10000);

    ProjectiveScheduler scheduler(prob);
    auto care_kink = scheduler.schedule<IgnoreKinkParity>();

    std::ofstream ofs("../../out/example/demo_inner.out");
    care_kink.to_visualizer(ofs, 1000);
  }

  {
    Problem prob;
    prob.reset();
    prob.data_qubits.assign(8, -1);

    Allocator allocator;
    allocator.allocate(prob, "outer", "naive", 1, 0.1, 10000);

    MultiTimeSliceScheduleResult care_kink(prob, {});
    std::ofstream ofs("../../out/example/legend_outer.out");
    care_kink.to_visualizer(ofs, 1000);
  }
  {
    Problem prob;
    prob.reset();
    prob.data_qubits.assign(8, -1);

    Allocator allocator;
    allocator.allocate(prob, "inner", "random", 2, 0.1, 10000);

    MultiTimeSliceScheduleResult care_kink(prob, {});
    std::ofstream ofs("../../out/example/legend_inner.out");
    care_kink.to_visualizer(ofs, 1000);
  }

  return 0;
}
