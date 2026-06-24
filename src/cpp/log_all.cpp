#include <cstring>
#include <filesystem>
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

namespace fs = std::filesystem;

constexpr bool execute_single = true, execute_proj = true,
               execute_double = true;

template <class Result>
void output(std::string file_name, Result result) {
  RoutingAlgorithm routing_algo;
  if (file_name.find(std::string("Yes_Kink")) != std::string::npos) {
    routing_algo = CareKinkParity;
  } else if (file_name.find(std::string("No_Kink")) != std::string::npos) {
    routing_algo = IgnoreKinkParity;
  } else if (file_name.find(std::string("No_Top")) != std::string::npos) {
    routing_algo = IgnoreTopology;
  } else if (file_name.find(std::string("No_MP")) != std::string::npos) {
    routing_algo = IgnoreMagicTopology;
  } else if (file_name.find(std::string("No_MSF")) != std::string::npos) {
    routing_algo = IgnoreTopologyInfiniteMagic;
  } else {
    assert(false);
  }
  ScheduleResultValidator(result, routing_algo).validate_all();

  std::ofstream ofs(file_name);
  result.to_visualizer(ofs, INT32_MAX);
  std::cout << "Output path: " << file_name << std::endl;
}

void execute(Problem& prob, const std::string& output_dir) {
  auto to_file_name = [&](std::string routing_name) -> std::string {
    return output_dir + routing_name + ".txt";
  };

  if constexpr (execute_single) {
    SingleTimeSliceScheduler single_scheduler(prob);

    output(to_file_name("Single_No_MSF"),
           single_scheduler.look_ahead_schedule<IgnoreTopologyInfiniteMagic>());
    output(to_file_name("Single_No_Top"),
           single_scheduler.look_ahead_schedule<IgnoreTopology>());
    output(to_file_name("Single_No_MP"),
           single_scheduler.look_ahead_schedule<IgnoreMagicTopology>());
    output(to_file_name("Single_No_Kink"),
           single_scheduler.look_ahead_schedule<IgnoreKinkParity>());
    if (prob.layer_count > 1) {
      output(to_file_name("Single_Yes_Kink"),
             single_scheduler.look_ahead_schedule<CareKinkParity>());
    }
  }
  if constexpr (execute_proj) {
    ProjectiveScheduler proj_scheduler(prob);

    output(to_file_name("Proj_No_MSF"),
           proj_scheduler.look_ahead_schedule<IgnoreTopologyInfiniteMagic>());
    output(to_file_name("Proj_No_Top"),
           proj_scheduler.look_ahead_schedule<IgnoreTopology>());
    output(to_file_name("Proj_No_MP"),
           proj_scheduler.look_ahead_schedule<IgnoreMagicTopology>());
    output(to_file_name("Proj_No_Kink"),
           proj_scheduler.look_ahead_schedule<IgnoreKinkParity>());
    output(to_file_name("Proj_Yes_Kink"),
           proj_scheduler.look_ahead_schedule<CareKinkParity>());
  }
  if constexpr (execute_double) {
    DoubleTimeSliceScheduler double_scheduler(prob);

    output(to_file_name("Double_No_MSF"),
           double_scheduler.look_ahead_schedule<IgnoreTopologyInfiniteMagic>());
    output(to_file_name("Double_No_Top"),
           double_scheduler.look_ahead_schedule<IgnoreTopology>());
    output(to_file_name("Double_No_MP"),
           double_scheduler.look_ahead_schedule<IgnoreMagicTopology>());
    output(to_file_name("Double_No_Kink"),
           double_scheduler.look_ahead_schedule<IgnoreKinkParity>());
    output(to_file_name("Double_Yes_Kink"),
           double_scheduler.look_ahead_schedule<CareKinkParity>());
  }
}

int main(int argc, char* argv[]) {
  fs::path input_path;
  std::string factory, allocator;
  int layer_count, msf_prep_time;
  double msf_coeff;

  fs::path executable_dir =
      fs::weakly_canonical(fs::path(argv[0])).remove_filename();

  if (argc == 1) {
    input_path =
        executable_dir /
        "../../data/circuit/result_SELECT_10_FermiHubbard2D_cylinder_0_0_1.in";
    factory = "outer";
    layer_count = 1;
    allocator = "SA";
    msf_coeff = 0.1;
    msf_prep_time = 2;
  } else if (argc == 7) {
    input_path = argv[1];
    factory = argv[2];
    layer_count = std::stoi(argv[3]);
    allocator = argv[4];
    msf_coeff = std::stod(argv[5]);
    msf_prep_time = std::stoi(argv[6]);
  } else {
    std::cerr << "Usage: " << argv[0]
              << " [input_path] [factory] [layer_count] [allocator] "
                 "[msf_coeff] [msf_prep_time]"
              << std::endl;
    return 1;
  }

  Problem prob(input_path.string(), msf_prep_time);
  Allocator().allocate(prob, factory, allocator, layer_count, msf_coeff,
                       1000000);

  // Remove trailing zero of to_string(msf_coeff).
  std::string msf_coeff_str = std::to_string(msf_coeff);
  msf_coeff_str.erase(msf_coeff_str.find_last_not_of('0') + 1,
                      std::string::npos);
  msf_coeff_str.erase(msf_coeff_str.find_last_not_of('.') + 1,
                      std::string::npos);

  fs::path circuit_dir =
      executable_dir / "../../out/result/" / input_path.stem().string();
  fs::create_directory(circuit_dir);
  fs::path param_dir = circuit_dir / (                                        //
                                         factory + "_"                        //
                                         + std::to_string(layer_count) + "_"  //
                                         + allocator + "_"                    //
                                         + msf_coeff_str + "_" +
                                         std::to_string(msf_prep_time) + "/");
  fs::create_directory(param_dir);
  execute(prob, param_dir.string());

  return 0;
}
