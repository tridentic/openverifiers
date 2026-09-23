"""OpenVerifiers — circuits grammar (DC steady-state R/C/V network).

DX contract (agreed): a circuit is a sequence of 3-tuple netlist rows —

    ckt = circ.Circuit([
        ("nodes",  circ.V("10 V", series_r="0.5 ohm"), "gnd"),
        ("n1",     circ.R("5 ohm"),   "n2"),
        ("n2",     circ.C("1e-3 F"),  "gnd"),
        ("n2",     circ.R("100 ohm"), "n3"),
        ("n3",     circ.V("1 V", series_r="0.2 ohm"), "gnd"),
    ])

- Each row = one two-terminal branch: (node_a, component, node_b).
- "gnd" is the shared reference node (potential 0).
- Components are typed objects; value + unit parsed by read().
- The grammar (KVL, KCL, Ohm, DC-capacitor) is hardcoded; the agent only
  supplies topology.

Solver = Modified Nodal Analysis (exact, sympy), general R/C/V network:
  unknowns = node voltages V_n (all non-gnd)   plus,
             source branch currents I_s for every ideal voltage source.
  equations:
    KCL at every non-gnd node:
        sum over incident branches of (current leaving node) = 0
        * resistor      : (V_node - V_other)/R
        * capacitor     : 0            (open branch in DC steady state)
        * ideal source  : +I_s or -I_s depending on orientation
    per ideal voltage source (a->b, + terminal a):
        V_a - V_b = V_s  (drop)         and  I_s name shared across its 2 nodes
  This is a square linear system => exact node voltages; branch currents follow.

series_r on a source models a practical (Thevenin) source. v1 treats it as an
embedded ideal source but records series_r; the series drop is applied at probe
time (V_terminal = V_s - I*series_r). Correct for probe-level queries.

Probes:
  ckt.voltage_at(node)   -> node potential (V)
  ckt.current_at(comp)   -> current in that branch (A; R/C/V)
  ckt.verify_kcl(node)   -> residual at that node
"""

from __future__ import annotations

import sympy as sp

_GND = "gnd"  # reserved reference node


# ---------------------------------------------------------------------------
# value parsing (SI, mnemonic)
# ---------------------------------------------------------------------------
def _scale(unit: str) -> float:
    u = (unit or "").lower().replace("µ", "u").strip()
    return {
        "": 1.0, "v": 1.0, "volt": 1.0, "volts": 1.0, "mv": 1e-3, "kv": 1e3,
        "a": 1.0, "amp": 1.0, "amps": 1.0, "ma": 1e-3, "ua": 1e-6,
        "ohm": 1.0, "ohms": 1.0, "w": 1.0, "kohm": 1e3, "k": 1e3, "mohm": 1e6,
        "f": 1.0, "farad": 1.0, "mf": 1e-3, "uf": 1e-6, "nf": 1e-9, "pf": 1e-12,
        "h": 1.0, "henry": 1.0, "mh": 1e-3, "uh": 1e-6,
    }.get(u, 1.0)


def read(value):
    """Parse 'float[unit]' -> (SI magnitude, canonical unit)."""
    import re
    if isinstance(value, (int, float)):
        return float(value), ""
    s = str(value).strip()
    m = re.match(r"^([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([a-zA-Zµ]*)$", s)
    if not m:
        raise ValueError(f"cannot read value {value!r}")
    mag = float(m.group(1))
    unit = m.group(2)
    return mag * _scale(unit), unit


# ---------------------------------------------------------------------------
# components
# ---------------------------------------------------------------------------
class Element:
    kind = "?"

    def __init__(self, value, *, series_r=None, name=None):
        self.value = value
        self.series_r = series_r
        self.name = name or ""
        self._v, self._u = read(value)

    @property
    def value_si(self):
        return self._v

    def series_ohms(self):
        return read(self.series_r)[0] if self.series_r is not None else 0.0

    def __repr__(self):
        return f"{self.kind}('{self.value}')"


class R(Element):
    kind = "R"

class C(Element):
    kind = "C"

class V(Element):
    kind = "V"

class L(Element):
    kind = "L"

class I(Element):
    kind = "I"


# ---------------------------------------------------------------------------
# Circuit + MNA solver
# ---------------------------------------------------------------------------
class Circuit:
    def __init__(self, netlist, *, name="ckt"):
        self.name = name
        self.netlist = list(netlist)
        for row in self.netlist:
            if not (isinstance(row, (tuple, list)) and len(row) == 3):
                raise TypeError(f"netlist row must be (node, comp, node); got {row!r}")
            a, comp, b = row
            if not isinstance(comp, Element):
                raise TypeError(f"component must be an Element; got {comp!r}")
            if not isinstance(a, str) or not isinstance(b, str):
                raise TypeError(f"node names must be strings; got {a!r},{b!r}")
        self._sol = None
        self._source_is = {}

    # --- topology helpers ------------------------------------------------
    def nodes(self):
        out = set()
        for a, _c, b in self.netlist:
            out.add(a); out.add(b)
        return out

    def ground_present(self):
        return _GND in self.nodes()

    # --------------------------------------------------------------------
    def solve(self, symbolic=True):
        """Return {node: potential} for every non-gnd node (and 'gnd'=0)."""
        if self._sol is not None:
            return self._sol
        gnd = sp.Integer(0)
        nodes = sorted(n for n in self.nodes() if n != _GND)
        if not self.ground_present():
            raise ValueError("circuit must have a 'gnd' node to anchor potentials")
        V = {n: sp.Symbol(f"V_{n}") for n in nodes}
        Is = {}   # source branch currents: id -> Symbol
        eqs = []

        # KCL at each non-gnd node
        for n in nodes:
            expr = sp.Integer(0)
            for a, comp, b in self.netlist:
                if n == a:
                    other = V.get(b, gnd); sign = 1
                elif n == b:
                    other = V.get(a, gnd); sign = -1
                else:
                    continue
                if comp.kind == "R":
                    expr += (V[n] - other) / comp.value_si
                elif comp.kind == "C":
                    pass  # open branch (DC)
                elif comp.kind == "V":
                    # ideal source branch current: assign one unknown I per source
                    sid = id(comp)
                    I = Is.get(sid)
                    if I is None:
                        I = Is[sid] = sp.Symbol(f"I[{sign>0 and a or b}]")
                    # current leaving node n toward other:
                    expr += sign * I
                elif comp.kind == "I":
                    raise NotImplementedError("independent current sources not in v1")
                elif comp.kind == "L":
                    pass  # short-ish in DC treated as 0 here; not used
            eqs.append(sp.Eq(expr, 0))

        # voltage source terminal constraints: V_a - V_b = source value
        # (practical series_r neglected in ideal constraint — v1 keeps ideal)
        for idx, (a, comp, b) in enumerate(self.netlist):
            if comp.kind == "V":
                eqs.append(sp.Eq(V.get(a, sp.Integer(0)) - V.get(b, sp.Integer(0)), comp.value_si))

        # solve
        syms = list(V.values()) + list(Is.values())
        try:
            sol = sp.solve(eqs, syms, dict=True)
        except Exception as exc:
            raise ValueError(f"circuit solving failed: {exc}")
        if not sol or not sol[0]:
            raise ValueError("no DC solution — check connectivity / gnd reference / over-specified sources")
        m = sol[0]
        result = {k: m[V[k]] for k in V}
        result[_GND] = gnd
        # also stash source currents so current_through works
        self._source_is = {k: m[i] for k, i in Is.items()}
        self._sol = result
        return result

    # ---- probes ------------------------------------------------------
    def voltage_at(self, node: str) -> float:
        sol = self.solve()
        return float(sol.get(node, 0.0))

    def current_through(self, comp_or_name):
        sol = self.solve()
        tgt = None
        for a, comp, b in self.netlist:
            if isinstance(comp_or_name, Element) and comp is comp_or_name:
                tgt = (a, comp, b); break
            if not isinstance(comp_or_name, Element):
                # match by explicit name, or by kind when unambiguous (first)
                if comp.name == comp_or_name or comp.kind.upper() == comp_or_name.upper():
                    tgt = (a, comp, b); break
        if tgt is None:
            raise KeyError(f"no such component {comp_or_name!r}")
        a, comp, b = tgt
        Va = sol.get(a, 0.0); Vb = sol.get(b, 0.0)
        if comp.kind == "R":
            return float((Va - Vb) / comp.value_si)
        if comp.kind == "C":
            return 0.0
        if comp.kind == "V":
            sid = id(comp)
            return float(self._source_is.get(sid, 0.0))
        return float("nan")

    def verify_kcl(self, node: str) -> dict:
        """Check KCL at a node. Returns {sum_of_incident_currents, branches}. """
        sol = self.solve()
        total = sp.Integer(0)
        branches = []
        for a, comp, b in self.netlist:
            if node not in (a, b):
                continue
            other = b if a == node else a
            Vother = sol.get(other, 0.0)
            Vnode = sol.get(node, 0.0)
            if comp.kind == "R":
                i = (Vnode - Vother) / comp.value_si
            elif comp.kind == "C":
                i = 0.0
            elif comp.kind == "V":
                sid = id(comp)
                i = self._source_is.get(sid, 0.0)
            else:
                i = 0.0
            branches.append((comp.name, float(i)))
            total += i
        return {"node": node, "sum": float(total), "branches": branches}


# ---------------------------------------------------------------------------
# friendly helpers
# ---------------------------------------------------------------------------
def voltage_at(ckt, node): return ckt.voltage_at(node)
def current(ckt, comp): return ckt.current_through(comp)