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

std::string global_input_path;
std::string global_factory_method;
std::string global_routing_alg;
std::string global_routing_alg_sub;
int global_layer_count;

constexpr bool execute_single = true, execute_proj = true,
               execute_double = true;

template <class Result>
void output(std::string name, Result result)
{
  std::cout << name << ": " << result.total_time << std::endl;

  int check_level;
  if (name.find(std::string("Yes Kink")) != std::string::npos)
  {
    check_level = 3;
  }
  else if (name.find(std::string("No Kink")) != std::string::npos)
  {
    check_level = 2;
  }
  else if (name.find(std::string("No Top")) != std::string::npos)
  {
    check_level = 1;
  }
  else if (name.find(std::string("No MSF")) != std::string::npos)
  {
    check_level = 0;
  }
  else
  {
    assert(false);
  }

  ScheduleResultValidator(result, check_level).validate_all();

  std::string output_path = global_input_path.substr(global_input_path.find_last_of("/") + 1);
  output_path = output_path.substr(0, output_path.find_last_of('.'));
  output_path = "../../out/result/"                        //
                + output_path + "_"                        //
                + global_factory_method + "_"              //
                + global_routing_alg + "_"                 //
                + global_routing_alg_sub + "_"             //
                + std::to_string(global_layer_count) + "_" //
                + "_"                                      //
                + ".out";
  std::ofstream ofs(output_path);
  result.to_visualizer(ofs, 1e9);
  std::cout << "Output path: " << output_path << std::endl;
}

void execute(Problem &prob, const std::string &factory,
             const std::string &allocation, const int layer_count)
{
  std::string name_suffix = " (" + std::to_string(layer_count) + " " + factory +
                            " " + allocation + ")";
  if constexpr (execute_single)
  {
    global_routing_alg = "single";
    global_routing_alg_sub = "IgnoreTopologyInfiniteMagic";
    output("Single No MSF" + name_suffix,
           solveBest<SingleTimeSliceScheduler, IgnoreTopologyInfiniteMagic>(
               prob, factory, allocation, layer_count));
    global_routing_alg_sub = "IgnoreTopology";
    output("Single No Top" + name_suffix,
           solveBest<SingleTimeSliceScheduler, IgnoreTopology>(
               prob, factory, allocation, layer_count));
    global_routing_alg_sub = "IgnoreKinkParity";
    output("Single No Kink" + name_suffix,
           solveBest<SingleTimeSliceScheduler, IgnoreKinkParity>(
               prob, factory, allocation, layer_count));
    if (layer_count > 1)
    {
      global_routing_alg_sub = "CareKinkParity";
      output("Single Yes Kink" + name_suffix,
             solveBest<SingleTimeSliceScheduler, CareKinkParity>(
                 prob, factory, allocation, layer_count));
    }
  }
  if constexpr (execute_proj)
  {
    global_routing_alg = "projective";
    global_routing_alg_sub = "IgnoreTopologyInfiniteMagic";
    output("Proj No MSF" + name_suffix,
           solveBest<ProjectiveScheduler, IgnoreTopologyInfiniteMagic>(
               prob, factory, allocation, layer_count));
    global_routing_alg_sub = "IgnoreTopology";
    output("Proj No Top" + name_suffix,
           solveBest<ProjectiveScheduler, IgnoreTopology>(
               prob, factory, allocation, layer_count));
    global_routing_alg_sub = "IgnoreKinkParity";
    output("Proj No Kink" + name_suffix,
           solveBest<ProjectiveScheduler, IgnoreKinkParity>(
               prob, factory, allocation, layer_count));
    global_routing_alg_sub = "CareKinkParity";
    output("Proj Yes Kink" + name_suffix,
           solveBest<ProjectiveScheduler, CareKinkParity>(
               prob, factory, allocation, layer_count));
  }
  if constexpr (execute_double)
  {
    global_routing_alg = "double";
    global_routing_alg_sub = "IgnoreTopologyInfiniteMagic";
    output("Double No MSF" + name_suffix,
           solveBest<DoubleTimeSliceScheduler, IgnoreTopologyInfiniteMagic>(
               prob, factory, allocation, layer_count));
    global_routing_alg_sub = "IgnoreTopology";
    output("Double No Top" + name_suffix,
           solveBest<DoubleTimeSliceScheduler, IgnoreTopology>(
               prob, factory, allocation, layer_count));
    global_routing_alg_sub = "IgnoreKinkParity";
    output("Double No Kink" + name_suffix,
           solveBest<DoubleTimeSliceScheduler, IgnoreKinkParity>(
               prob, factory, allocation, layer_count));
    global_routing_alg_sub = "CareKinkParity";
    output("Double Yes Kink" + name_suffix,
           solveBest<DoubleTimeSliceScheduler, CareKinkParity>(
               prob, factory, allocation, layer_count));
  }
}

int main(int argc, char *argv[])
{
  // Load the instance.
  std::string file_path;
  if (argc == 1)
  {
    file_path =
        "../../data/circuit/result_SELECT_10_FermiHubbard2D_cylinder_0_0_1.in";
  }
  else if (argc == 2)
  {
    file_path = argv[1];
  }
  else
  {
    std::cerr << "Usage: " << argv[0] << " [file_path]" << std::endl;
    return 1;
  }

  Allocator allocator;
  for (int layer_count = 1; layer_count <= 2; layer_count++)
  {
    for (std::string factory : {"outer", "inner"})
    {
      for (std::string allocation : {"SA"})
      {
        Problem prob(file_path);
        global_input_path = file_path;
        global_factory_method = factory;
        global_layer_count = layer_count;
        execute(prob, factory, allocation, layer_count);
      }
    }
  }

  return 0;
}
