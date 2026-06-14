#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <random>
#include <stdexcept>

#include "allocator/allocator.hpp"
#include "scheduler/doubleTimeSlice.hpp"
#include "scheduler/projective.hpp"
#include "scheduler/singleTimeSlice.hpp"
#include "util/load_instance.hpp"
#include "util/solveBest.hpp"
#include "util/timer.hpp"

int main(int argc, char const* argv[]) {
  // Load the instance.
  auto [input_path, factory_method, allocation_method, layer_count, iters,
        routing_alg] = load_instance(argc, argv);
  assert(iters == 1000000);
  Problem prob(input_path);

  MultiTimeSliceScheduleResult best_schedule_result(prob, {});

  if (routing_alg == "IgnoreTopologyInfiniteMagic") {
    best_schedule_result =
        solveBest<DoubleTimeSliceScheduler, IgnoreTopologyInfiniteMagic>(
            prob, factory_method, allocation_method, layer_count);
  } else if (routing_alg == "CareKinkParity") {
    best_schedule_result = solveBest<DoubleTimeSliceScheduler, CareKinkParity>(
        prob, factory_method, allocation_method, layer_count);
  } else {
    throw std::runtime_error("Unknown routing algorithm: " + routing_alg);
  }

  std::cout << "Best schedule result: " << best_schedule_result.total_time
            << std::endl;

// Also, output the result in the visualizer format.
#ifndef NO_VIS
  std::string output_path = input_path.substr(input_path.find_last_of("/") + 1);
  output_path = output_path.substr(0, output_path.find_last_of('.'));
  output_path = "../../out/result/"                  //
                + output_path + "_"                  //
                + factory_method + "_"               //
                + allocation_method + "_"            //
                + std::to_string(layer_count) + "_"  //
                + std::to_string(iters) + "_"        //
                + routing_alg + ".out";
  std::ofstream ofs(output_path);
  best_schedule_result.to_visualizer(ofs, 1000);
  std::cout << "Output path: " << output_path << std::endl;
#endif

  return 0;
}
