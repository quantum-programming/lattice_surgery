def append_RZ_gate(gates, target, angle, epsilon):
    import mpmath
    from pygridsynth.gridsynth import gridsynth_gates

    mpmath.mp.dps = 128
    theta = mpmath.mpmathify(angle)
    epsilon = mpmath.mpmathify(epsilon)

    rz_gates = gridsynth_gates(theta=-theta, epsilon=epsilon)

    for gate in rz_gates:
        if gate == "H":
            gates.append({"name": "H", "targets": [target]})
        elif gate == "S":
            gates.append({"name": "S", "targets": [target]})
        elif gate == "T":
            gates.append({"name": "T", "targets": [target]})


def append_RX_gate(gates, target, angle, epsilon):
    import mpmath
    from pygridsynth.gridsynth import gridsynth_gates

    mpmath.mp.dps = 128
    theta = mpmath.mpmathify(angle)
    epsilon = mpmath.mpmathify(epsilon)

    rz_gates = gridsynth_gates(theta=-theta, epsilon=epsilon)

    for gate in rz_gates:
        if gate == "H":
            gates.append({"name": "H", "targets": [target]})
        elif gate == "S":
            gates.append({"name": "S", "targets": [target]})
        elif gate == "T":
            gates.append({"name": "T", "targets": [target]})
