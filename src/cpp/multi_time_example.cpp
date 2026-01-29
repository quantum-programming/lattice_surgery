#include <cstring>
#include <iostream>
#include <random>

#include "allocator/allocator.hpp"
#include "scheduler/doubleTimeSlice.hpp"
#include "scheduler/projective.hpp"
#include "scheduler/scheduleResult.hpp"
#include "scheduler/scheduleResultValidator.hpp"
#include "scheduler/singleTimeSlice.hpp"
#include "util/problem.hpp"
#include "util/solveBest.hpp"

constexpr bool execute_single = true, execute_proj = true,
               execute_double = true;

template <class Result>
void output(std::string name, Result result) {
  std::cout << name << ": " << result.total_time << std::endl;

  int check_level;
  if (name.find(std::string("Yes Kink")) != std::string::npos) {
    check_level = 3;
  } else if (name.find(std::string("No Kink")) != std::string::npos) {
    check_level = 2;
  } else if (name.find(std::string("No Top")) != std::string::npos) {
    check_level = 1;
  } else if (name.find(std::string("No MSF")) != std::string::npos) {
    check_level = 0;
  } else {
    assert(false);
  }

  ScheduleResultValidator(result, check_level).validate_all();
}

void execute(Problem &prob, const std::string &factory,
             const std::string &allocation, const int layer_count) {
  std::string name_suffix = " (" + std::to_string(layer_count) + " " + factory +
                            " " + allocation + ")";
  if constexpr (execute_single) {
    output("Single No MSF" + name_suffix,
           solveBest<SingleTimeSliceScheduler, IgnoreTopologyInfiniteMagic>(
               prob, factory, allocation, layer_count));
    output("Single No Top" + name_suffix,
           solveBest<SingleTimeSliceScheduler, IgnoreTopology>(
               prob, factory, allocation, layer_count));
    output("Single No Kink" + name_suffix,
           solveBest<SingleTimeSliceScheduler, IgnoreKinkParity>(
               prob, factory, allocation, layer_count));
    if (layer_count > 1) {
      output("Single Yes Kink" + name_suffix,
             solveBest<SingleTimeSliceScheduler, CareKinkParity>(
                 prob, factory, allocation, layer_count));
    }
  }
  if constexpr (execute_proj) {
    output("Proj No MSF" + name_suffix,
           solveBest<ProjectiveScheduler, IgnoreTopologyInfiniteMagic>(
               prob, factory, allocation, layer_count));
    output("Proj No Top" + name_suffix,
           solveBest<ProjectiveScheduler, IgnoreTopology>(
               prob, factory, allocation, layer_count));
    output("Proj No Kink" + name_suffix,
           solveBest<ProjectiveScheduler, IgnoreKinkParity>(
               prob, factory, allocation, layer_count));
    output("Proj Yes Kink" + name_suffix,
           solveBest<ProjectiveScheduler, CareKinkParity>(
               prob, factory, allocation, layer_count));
  }
  if constexpr (execute_double) {
    output("Double No MSF" + name_suffix,
           solveBest<DoubleTimeSliceScheduler, IgnoreTopologyInfiniteMagic>(
               prob, factory, allocation, layer_count));
    output("Double No Top" + name_suffix,
           solveBest<DoubleTimeSliceScheduler, IgnoreTopology>(
               prob, factory, allocation, layer_count));
    output("Double No Kink" + name_suffix,
           solveBest<DoubleTimeSliceScheduler, IgnoreKinkParity>(
               prob, factory, allocation, layer_count));
    output("Double Yes Kink" + name_suffix,
           solveBest<DoubleTimeSliceScheduler, CareKinkParity>(
               prob, factory, allocation, layer_count));
  }
}

int main(int argc, char *argv[]) {
  // Load the instance.
  std::string file_path;
  if (argc == 1) {
    file_path =
        "../../data/circuit/result_SELECT_10_FermiHubbard2D_cylinder_0_0_1.in";
  } else if (argc == 2) {
    file_path = argv[1];
  } else {
    std::cerr << "Usage: " << argv[0] << " [file_path]" << std::endl;
    return 1;
  }

  Allocator allocator;
  for (int layer_count = 1; layer_count <= 2; layer_count++) {
    for (std::string factory : {"outer", "inner"}) {
      for (std::string allocation : {"SA"}) {
        Problem prob(file_path);
        execute(prob, factory, allocation, layer_count);
      }
    }
  }

  return 0;
}
