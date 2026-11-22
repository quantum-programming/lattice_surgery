#include <algorithm>
#include <filesystem>
#include <iostream>
#include <sstream>
#include <type_traits>

#include "allocator/allocator.hpp"
#include "scheduler/doubleTimeSlice.hpp"
#include "scheduler/projective.hpp"
#include "scheduler/scheduleResult.hpp"
#include "scheduler/scheduleResultValidator.hpp"
#include "scheduler/singleTimeSlice.hpp"
#include "util/problem.hpp"

namespace fs = std::filesystem;

const char* routing_option_name(RoutingAlgorithm algo) {
  switch (algo) {
    case IgnoreTopologyInfiniteMagic:
      return "No_MSF";
    case IgnoreTopology:
      return "No_Top";
    case IgnoreMagicTopology:
      return "No_MP";
    case IgnoreKinkParity:
      return "No_Kink";
    case CareKinkParity:
      return "Yes_Kink";
    default:
      assert(false);
      return "";
  }
}

template <typename Result, RoutingAlgorithm... algorithms, typename Scheduler>
void append_metrics(std::ostream& out, const std::string& prefix,
                    const char* scheduler_name, Scheduler& scheduler) {
  const auto append_row = [&](RoutingAlgorithm algo, const auto& result) {
    ScheduleResultValidator(result, algo).validate_all();
    out << prefix << scheduler_name << ',' << routing_option_name(algo) << ','
        << result.total_time << ',' << result.compute_circuit_volume() << '\n';
  };

  if constexpr (std::is_void_v<Result>) {
    (append_row(algorithms,
                scheduler.template look_ahead_schedule<algorithms>()),
     ...);
  } else {
    (append_row(algorithms,
                scheduler.template look_ahead_schedule<algorithms, Result>()),
     ...);
  }
}

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

  const bool has_multibody = std::any_of(
      prob.instructions.begin(), prob.instructions.end(),
      [](const Instruction& inst) { return inst.targetIds.size() > 2; });
  if (has_multibody) {
    DoubleTimeSliceScheduler double_scheduler(prob);
    append_metrics<MultiTimeSliceMultiBodyScheduleResult,
                   IgnoreTopologyInfiniteMagic, IgnoreTopology,
                   IgnoreMagicTopology, IgnoreKinkParity, CareKinkParity>(
        ss, csv_row_prefix, "Double", double_scheduler);
  } else {
    SingleTimeSliceScheduler single_scheduler(prob);
    append_metrics<void, IgnoreTopologyInfiniteMagic, IgnoreTopology,
                   IgnoreMagicTopology, IgnoreKinkParity>(
        ss, csv_row_prefix, "Single", single_scheduler);
    if (layer_count > 1) {
      append_metrics<void, CareKinkParity>(ss, csv_row_prefix, "Single",
                                           single_scheduler);
    }

    DoubleTimeSliceScheduler double_scheduler(prob);
    append_metrics<void, IgnoreTopologyInfiniteMagic, IgnoreTopology,
                   IgnoreMagicTopology, IgnoreKinkParity, CareKinkParity>(
        ss, csv_row_prefix, "Double", double_scheduler);

    ProjectiveScheduler projective_scheduler(prob);
    append_metrics<void, IgnoreTopologyInfiniteMagic, IgnoreTopology,
                   IgnoreMagicTopology, IgnoreKinkParity, CareKinkParity>(
        ss, csv_row_prefix, "Proj.", projective_scheduler);
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
