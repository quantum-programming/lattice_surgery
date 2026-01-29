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
  for (std::string input_prefix : {"stair", "chain"}) {
    Problem prob("../../data/example/" + input_prefix + ".in");

    {
      Allocator allocator;
      allocator.allocate(prob, "outer", "naive", 1, 0.0, 0);

      ProjectiveScheduler projective_scheduler(prob);
      auto projective_res = projective_scheduler.schedule<CareKinkParity>();
      std::ofstream projective_ofs("../../out/example/" + input_prefix +
                                   "_projective.out");
      projective_res.to_visualizer(projective_ofs, 1000);

      DoubleTimeSliceScheduler double_scheduler(prob);
      auto double_res = double_scheduler.look_ahead_schedule<CareKinkParity>();
      std::ofstream double_ofs("../../out/example/" + input_prefix +
                               "_double.out");
      double_res.to_visualizer(double_ofs, 1000);
    }

    {
      prob.reset();
      Allocator allocator;
      allocator.allocate(prob, "outer", "naive", 2, 0.0, 0);

      SingleTimeSliceScheduler single_scheduler(prob);
      auto single_res = single_scheduler.look_ahead_schedule<CareKinkParity>();
      std::ofstream single_ofs("../../out/example/" + input_prefix +
                               "_single.out");
      single_res.to_visualizer(single_ofs, 1000);
    }
  }

  return 0;
}
