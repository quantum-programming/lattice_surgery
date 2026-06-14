#include <filesystem>
#include <iostream>

#include "allocator/allocator.hpp"
#include "scheduler/doubleTimeSlice.hpp"
#include "scheduler/projective.hpp"
#include "scheduler/scheduleResult.hpp"
#include "scheduler/scheduleResultValidator.hpp"
#include "scheduler/singleTimeSlice.hpp"
#include "util/problem.hpp"

namespace fs = std::filesystem;

template <class Result>
void validate(std::string routing_option, Result result) {
  RoutingAlgorithm routing_algo;
  if (routing_option == "Yes_Kink") {
    routing_algo = CareKinkParity;
  } else if (routing_option == "No_Kink") {
    routing_algo = IgnoreKinkParity;
  } else if (routing_option == "No_Top") {
    routing_algo = IgnoreTopology;
  } else if (routing_option == "No_MP") {
    routing_algo = IgnoreMagicTopology;
  } else if (routing_option == "No_MSF") {
    routing_algo = IgnoreTopologyInfiniteMagic;
  } else {
    assert(false);
  }
  ScheduleResultValidator(result, routing_algo).validate_all();
};

std::string to_csv(fs::path input_path, std::string factory, int layer_count,
                   std::string allocator, double msf_coeff, int msf_prep_time) {
  Problem prob(input_path.string(), msf_prep_time);

  Allocator().allocate(prob, factory, allocator, layer_count, msf_coeff,
                       1000000);

  // Remove trailing zero of to_string(msf_coeff).
  std::string msf_coeff_str = std::to_string(msf_coeff);
  msf_coeff_str.erase(msf_coeff_str.find_last_not_of('0') + 1,
                      std::string::npos);
  msf_coeff_str.erase(msf_coeff_str.find_last_not_of('.') + 1,
                      std::string::npos);

  std::stringstream ss;
  // CSV Header
  ss << "circuit,factory,layer_count,allocator,msf_coeff,msf_prep_time,"
        "routing_algo,routing_option,total_code_beat,circuit_"
        "volume\n";

  std::string csv_row_prefix =
      input_path.stem().string() + "," + factory + ","  //
      + std::to_string(layer_count) + ","               //
      + allocator + ","                                 //
      + msf_coeff_str + "," + std::to_string(msf_prep_time) + ",";

  {
    SingleTimeSliceScheduler single_scheduler(prob);

    std::vector<std::pair<std::string, SingleTimeSliceScheduleResult>> results =
        {
            {"No_MSF", single_scheduler
                           .look_ahead_schedule<IgnoreTopologyInfiniteMagic>()},
            {"No_Top", single_scheduler.look_ahead_schedule<IgnoreTopology>()},
            {"No_MP",
             single_scheduler.look_ahead_schedule<IgnoreMagicTopology>()},
            {"No_Kink",
             single_scheduler.look_ahead_schedule<IgnoreKinkParity>()},

        };
    if (layer_count > 1) {
      results.push_back(
          {"Yes_Kink", single_scheduler.look_ahead_schedule<CareKinkParity>()});
    }

    for (auto&& [option, result] : results) {
      validate(option, result);
      ss << csv_row_prefix << "Single" << "," << option << ","
         << result.total_time << "," << result.compute_circuit_volume() << "\n";
    }
  }
  {
    DoubleTimeSliceScheduler double_scheduler(prob);

    std::vector<std::pair<std::string, MultiTimeSliceScheduleResult>> results =
        {
            {"No_MSF", double_scheduler
                           .look_ahead_schedule<IgnoreTopologyInfiniteMagic>()},
            {"No_Top", double_scheduler.look_ahead_schedule<IgnoreTopology>()},
            {"No_MP",
             double_scheduler.look_ahead_schedule<IgnoreMagicTopology>()},
            {"No_Kink",
             double_scheduler.look_ahead_schedule<IgnoreKinkParity>()},
            {"Yes_Kink",
             double_scheduler.look_ahead_schedule<CareKinkParity>()},
        };

    for (auto&& [option, result] : results) {
      validate(option, result);
      ss << csv_row_prefix << "Double" << "," << option << ","
         << result.total_time << "," << result.compute_circuit_volume() << "\n";
    }
  }
  {
    ProjectiveScheduler proj_scheduler(prob);

    std::vector<std::pair<std::string, MultiTimeSliceScheduleResult>> results =
        {
            {"No_MSF",
             proj_scheduler.look_ahead_schedule<IgnoreTopologyInfiniteMagic>()},
            {"No_Top", proj_scheduler.look_ahead_schedule<IgnoreTopology>()},
            {"No_MP",
             proj_scheduler.look_ahead_schedule<IgnoreMagicTopology>()},
            {"No_Kink", proj_scheduler.look_ahead_schedule<IgnoreKinkParity>()},
            {"Yes_Kink", proj_scheduler.look_ahead_schedule<CareKinkParity>()},
        };

    for (auto&& [option, result] : results) {
      validate(option, result);
      ss << csv_row_prefix << "Proj." << "," << option << ","
         << result.total_time << "," << result.compute_circuit_volume() << "\n";
    }
  }

  return ss.str();
}

int main(int argc, char* argv[]) {
  fs::path input_path;
  std::string factory, allocator;
  int layer_count, msf_prep_time;
  double msf_coeff;

  fs::path executable_dir =
      fs::weakly_canonical(fs::path(argv[0])).remove_filename();

  if (argc == 1) {
    input_path = executable_dir /
                 "../../data/circuit/"
                 "result_SELECT_10_FermiHubbard2D_cylinder_0_0_1.in";
    factory = "outer";
    layer_count = 2;
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

  std::cout << to_csv(input_path, factory, layer_count, allocator, msf_coeff,
                      msf_prep_time);
  std::flush(std::cout);

  return 0;
}
