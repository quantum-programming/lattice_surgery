import TeleportRouter

# Get the circuit file path from command line argument
if length(ARGS) != 2
    println("Usage: julia process_circuit.jl <circuit_json_path> <qubit_count>")
    exit(1)
end

circuit_path = ARGS[1]
qubit_count = parse(Int, ARGS[2])
plain_size = Int(ceil(sqrt(qubit_count)))

# Load in a circuit from JSON and parse it to Ops and a DAG
ops, idx = TeleportRouter.parse_circuit(open(circuit_path, "r"))
dag = TeleportRouter.dag_circuit(ops, idx)
schedule = TeleportRouter.apply_ops(ops, dag, plain_size, plain_size)

# println(schedule)
# Vector{Vector{Vector{MappedOp}}}
# [
#     [
#         [TeleportRouter.MappedOp(1, "cxX", [3, 5], [25, 34, 33, 42, 41]),
#         TeleportRouter.MappedOp(2, "mx", [1], [21])]
#     ],
#     [
#         [TeleportRouter.MappedOp(3, "CX", [1, 2], [21, 12, 13, 22, 23])]
#     ],
#     [
#         [TeleportRouter.MappedOp(4, "tx", [3], [25, 16, 15, 6, 5]),
#         TeleportRouter.MappedOp(5, "CX", [1, 2], [21, 12, 13, 22, 23])]
#     ],
#     [
#         [TeleportRouter.MappedOp(6, "ccz", [3, 4, 1], [25])]
#     ]
# ]

"""Check if the given position is a magic state factory."""
function is_boundary(pos::Int)::Bool
    width = 2 * plain_size + 3
    x = (pos - 1) % width
    y = (pos - 1) ÷ width
    if isodd(x) || isodd(y)
        return false
    end
    return x == 0 || x == 2 * plain_size + 2 || y == 0 || y == 2 * plain_size + 2
end

code_beat = 0
circuit_volume = 0
for (i, layer_schedule_res) in enumerate(schedule)
    for step in layer_schedule_res
        layer_type_set = Set([x.op for x in step])
        @assert !isempty(layer_type_set)
        @assert issubset(layer_type_set, ["tz", "CX"]) "$layer_type_set"

        if "CX" ∈ layer_type_set
            path_cost = 2
        else
            path_cost = 1
        end

        # Check if EDP step was VDP
        is_edp = false
        visited = Set{Int}()
        for op in step, node in op.path
            if node ∈ visited
                is_edp = true
                break
            end
            push!(visited, node)
        end

        if is_edp
            layer_cost = path_cost * 2
        else
            layer_cost = path_cost
        end

        global code_beat += layer_cost

        for op in step
            # For simplicity, we ignore an additional circuit volume incurred by splitting EDP into VDP.
            if op.op == "CX"
                global circuit_volume += (length(op.path) - 2) * 2
            else
                global circuit_volume += (length(op.path) - 2)
            end
        end
    end
end

circuit_volume += code_beat * qubit_count
println("{\"code_beat\": $code_beat, \"circuit_volume\": $circuit_volume}\n")


