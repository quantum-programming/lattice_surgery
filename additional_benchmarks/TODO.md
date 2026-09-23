# TODO

## Current Experimental Plan

1. Prepare common CNOT+T microbenchmarks with a few dozen gates and confirm that the inputs are semantically equivalent across all tools.
2. Collect depth, footprint, volume, and runtime under each tool's native/default conditions.
3. Add a controlled comparison with matched footprint or data density to separate the contribution of the 25% storage-density assumption from that of the scheduling method.
4. Compare TopoLS with ZX optimization enabled and disabled to directly demonstrate the contribution of gate merging noted by Reviewer 1.
5. Visualize the generated structures for small examples and, where possible, use TQEC/Stim or each implementation's verification features to confirm their semantics and fault-tolerant structure.
6. After the common microbenchmarks, add scaled-down examples from our Hamiltonian-simulation workload. For tools that cannot support them, state the reason for failure or the required lowering, and do not force a numerical comparison.
