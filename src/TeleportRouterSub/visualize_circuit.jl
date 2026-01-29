import TeleportRouter

# Get the circuit file path from command line argument
if length(ARGS) != 2
    println("Usage: julia process_circuit.jl <circuit_json_path> <plain_size>")
    exit(1)
end

circuit_path = ARGS[1]
plain_size = parse(Int, ARGS[2])

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
record = Dict()
for (i, layer_schedule_res) in enumerate(schedule)
    for step in layer_schedule_res
        layer_type_set = Set([x.op for x in step])
        @assert !isempty(layer_type_set)
        @assert issubset(layer_type_set, ["tz", "CX"]) "$layer_type_set"

        if "CX" ∈ layer_type_set
            layer_cost = 2
        else
            layer_cost = 1
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
            layer_cost *= 2
        end

        record[code_beat] = step

        # global code_beat += layer_cost
        global code_beat += 1
    end
end

println("$(length(ops)) $code_beat")

sorted_beats = sort(collect(keys(record)))
for t in sorted_beats
    step = record[t]
    for op in step
        if length(op.qubits) == 1
            # We can compute the exact position of msf,
            # but we ignore it and use an arbitrary value
            # since it is not critical in the visualizer.
            push!(op.qubits, plain_size * plain_size)
        end
        println(length(op.qubits))
        println(join(op.qubits, " "))
        println(length(op.path))
        for pos in op.path
            width = 2 * plain_size + 3
            x = (pos - 1) ÷ width
            y = (pos - 1) % width
            z = 0
            println("$t $x $y $z")
        end
    end
end
