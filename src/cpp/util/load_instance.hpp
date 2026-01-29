#pragma once

#include <iostream>
#include <stdexcept>
#include <string>
#include <tuple>

std::tuple<std::string, std::string, std::string, int, int, std::string>
load_instance(int argc, char const* argv[]) {
  // Parse command line arguments.
  std::string input_path, factory_method, allocation_method, routing_alg;
  int layer_count, iters;
  if (argc <= 2) {
    if (argc == 2)
      input_path = argv[1];
    else
      input_path = "../../data/example/demo.in";
    factory_method = "outer";
    allocation_method = "SA";
    layer_count = 2;
    iters = 1000000;
    routing_alg = "CareKinkParity";
  } else if (argc == 7) {
    input_path = argv[1];
    factory_method = argv[2];
    allocation_method = argv[3];
    layer_count = std::stoi(argv[4]);
    iters = std::stoi(argv[5]);
    routing_alg = argv[6];
  } else {
    throw std::runtime_error(
        "Usage: ./main [input_path] [factory_method] [allocation_method] "
        "[layer_count] [iters] [routing_alg]");
  }
  return {input_path,  factory_method, allocation_method,
          layer_count, iters,          routing_alg};
}
