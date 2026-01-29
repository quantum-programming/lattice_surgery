class Circuit:
    def __init__(self):
        self.gates = []

    def add_gate(self, gate: dict):
        self.gates.append(gate)

    def add_gate_list(self, gates: list):
        self.gates.extend(gates)

    def __repr__(self):
        s = "\n".join(map(str, self.gates))
        return s
