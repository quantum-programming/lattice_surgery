#pragma once

#include <iostream>
#include <vector>

#include "../allocator/allocator.hpp"
#include "../scheduler/doubleTimeSlice.hpp"
#include "../scheduler/projective.hpp"
#include "../scheduler/scheduleResult.hpp"
#include "../scheduler/singleTimeSlice.hpp"
#include "problem.hpp"

// Deduce result type based on Scheduler.
template <class Scheduler>
struct ScheduleResultType;

template <>
struct ScheduleResultType<SingleTimeSliceScheduler> {
  using type = SingleTimeSliceScheduleResult;
};

template <>
struct ScheduleResultType<DoubleTimeSliceScheduler> {
  using type = MultiTimeSliceScheduleResult;
};

template <>
struct ScheduleResultType<ProjectiveScheduler> {
  using type = MultiTimeSliceScheduleResult;
};

std::string problem_cache_file = "cached_problem_name.in";
std::map<std::tuple<std::string, std::string, int, double>, Problem>
    problem_cache;

template <class Scheduler, RoutingAlgorithm RoutingAlgoOrTag>
auto solveBest(Problem &prob, const std::string &factory_method,
               const std::string &allocation_method, const int layer_count) {
  if (problem_cache_file != prob.file_path) {
    problem_cache.clear();
    problem_cache_file = prob.file_path;
  }

  using Result = typename ScheduleResultType<Scheduler>::type;
  Result best_result(prob, {});
  best_result.total_time = 1e9;

  std::vector<double> msf_coeffs =
      allocation_method == "SA" ? std::vector<double>{0.001, 0.01, 0.1, 1.0}
                                : std::vector<double>{0.0};
  int iters = 1000000;

  for (double msf_coeff : msf_coeffs) {
    auto args = std::make_tuple(factory_method, allocation_method, layer_count,
                                msf_coeff);
    if (problem_cache.count(args)) {
      prob = problem_cache[args];
    } else {
      prob.reset();
      Allocator allocator;
      allocator.allocate(prob, factory_method, allocation_method, layer_count,
                         msf_coeff, iters);
      problem_cache[args] = prob;
    }

    Scheduler scheduler(prob);
    Result res(prob, {});
    if constexpr (std::is_same_v<Scheduler, SingleTimeSliceScheduler>) {
      res = scheduler.template look_ahead_schedule<RoutingAlgoOrTag>();
    } else if constexpr (std::is_same_v<Scheduler, DoubleTimeSliceScheduler>) {
      res = scheduler.template look_ahead_schedule<RoutingAlgoOrTag>();
    } else if constexpr (std::is_same_v<Scheduler, ProjectiveScheduler>) {
      res = scheduler.template schedule<RoutingAlgoOrTag>();
    }

    if (res.total_time < best_result.total_time) best_result = std::move(res);
    std::cerr << "schedule result: " << res.total_time
              << " with msf coeff: " << msf_coeff << std::endl;
  }

  std::cerr << "Best schedule result: " << best_result.total_time << std::endl;
  return best_result;
}
