"""Syllabus physics primitives — ONE textbook relation per Transformation.

Registration is declarative and self-validating: a plain function IS the
relation, its parameter names ARE the variables, and `@relation(...)` calls
it once with sympy Symbols to build the expression by normal operator
overloading — no globals() injection, no alias table. Numeric or symbolic
execution is decided by the Primitive engine: bind all-but-one variable ->
numeric solve; leave the output plus a shared unknown free -> ExpressionFact.

Unit typing lives at the point of definition (the `units=` kwarg sits
against the function signature), so mislabels are caught in review, and the
decorator enforces `set(units) == set(parameters)`.

Angle convention: variables named `theta`/`t1`/`t2` carry ANGLE (dimensionless,
degrees); the expression embeds the pi/180 conversion so numeric and
symbolic modes agree.
"""

from __future__ import annotations

import inspect

import sympy as sp

from ..facts import Fact, Quantity, ExpressionFact, DIMENSIONLESS
from ..model import ParamTransformation, InputSpec
from ..units import Unit, Dimension
from ..v2 import Grammar
from .units_si import (Meter, Second, MeterPerSecond, MeterPerSecondSquared,
                       Newton, Joule, Watt, Kilogram, Hertz, Ampere, Coulomb,
                       Volt, Ohm, Tesla, Pascal, Kelvin)

# --------------------------------------------------------------------------
# composite unit types (corrected; previously mislabeled as bare Meter())
# --------------------------------------------------------------------------
ANGLE = DIMENSIONLESS          # degrees convention for theta/t1/t2
COUNT = DIMENSIONLESS          # dimensionless counts (N turns, n index)
R_INDEX = DIMENSIONLESS        # refractive index n1/n2; magnification m
MU_COEF = DIMENSIONLESS        # friction coefficient
# physical-law constants / material params — proper SI composites
K_COULOMB = Unit(dimension=Newton().dimension * Meter().dimension ** 2
                 / Coulomb().dimension ** 2)      # N m^2 / C^2
G_NEWTON = Unit(dimension=Newton().dimension * Meter().dimension ** 2
                / Kilogram().dimension ** 2)       # N m^2 / kg^2
RHO_RES = Unit(dimension=Ohm().dimension * Meter().dimension)  # Ohm m
AREA = Unit(dimension=Meter().dimension ** 2)
VOLUME = Unit(dimension=Meter().dimension ** 3)
MOL = Unit(dimension=Dimension(amount=1))
SPECIFIC_HEAT = Unit(dimension=Joule().dimension
                     / (Kilogram().dimension * Kelvin().dimension))  # J/(kg K)
GAS_R = Unit(dimension=Joule().dimension
             / (MOL.dimension * Kelvin().dimension))                 # J/(mol K)
PER_KELVIN = Unit(dimension=Kelvin().dimension ** -1)               # 1/K
HEAT_CAP = Unit(dimension=Joule().dimension / Kilogram().dimension)  # J/kg
PHOTON_H = Unit(dimension=Joule().dimension * Second().dimension)   # J s
EL_FIELD = Unit(dimension=Volt().dimension / Meter().dimension)     # V/m


# --------------------------------------------------------------------------
# the relation decorator
# --------------------------------------------------------------------------
class Primitive(ParamTransformation):
    """Engine behind every decorated relation.

        all vars bound  -> consistency check (residual ~ 0), returns the
                           BOUND OUTPUT VALUE (not the residual)
        one var free    -> numeric solve
        >=2 free (or an ExpressionFact input chains) -> ExpressionFact
    """

    def __init__(self, *, name, vars, out, expr, units, doc=""):
        self.rule = {
            "name": name, "vars": tuple(vars), "out": out,
            "expr": expr, "units": units, "doc": doc,
        }
        inputs = (InputSpec(v, required=False) for v in vars)
        super().__init__(name=name, doc=doc, param_names=("axis", "theta"),
                         inputs=tuple(inputs))
        self._syms = {v: sp.Symbol(v) for v in vars}
        self._expr = expr
        self.out = out

    # -- numerics -----------------------------------------------------------
    @staticmethod
    def _num(fact: Fact, axis: int = 0) -> float:
        if fact is None:
            return None
        value = fact.value
        if value is None:
            return None
        if hasattr(value, "component"):          # Vector3
            comp = [value.x, value.y, value.z][axis]
            from ..units import to_canonical
            return float(to_canonical(comp, fact.unit))
        from ..facts import as_number
        return as_number(value, getattr(fact, "unit", None))

    def apply(self, inputs: dict, params: dict | None = None) -> Fact:
        params = params or {}
        axis = int(params.get("axis", 0) or 0)
        bound: dict[str, float] = {}
        chained: dict[sp.Symbol, sp.Expr] = {}
        for v in self.rule["vars"]:
            if v in inputs:
                f = inputs[v]
                if isinstance(f, ExpressionFact):
                    chained[self._syms[v]] = sp.sympify(f.expression)
                    continue
                num = self._num(f, axis)
                if num is None:
                    raise ValueError(f"input {v!r} has no numeric value")
                bound[v] = num
            elif v in params:
                bound[v] = float(params[v])

        subs = {self._syms[v]: b for v, b in bound.items()}
        subs.update(chained)
        out = self.rule["out"]
        out_unit = self.rule["units"][out]
        remaining = [v for v in self.rule["vars"]
                     if v not in bound and self._syms[v] not in chained]

        if len(remaining) == 0:
            # full verification path: every variable bound. The relation must
            # hold (residual ~ 0); the RETURNED value is the bound OUTPUT
            # value itself, never the residual.
            err = abs(float(sp.N(self._expr.subs(subs))))
            scale = max(1.0, abs(float(sp.N(subs.get(self._syms[out],
                                                     1.0)))))
            if err > 1e-6 * scale:
                raise ValueError(
                    f"relation {self.rule['name']} not satisfied by the "
                    f"bound values (residual {err:g})")
            return Quantity(value=float(bound[out]), unit=out_unit)

        if len(remaining) >= 2 or chained:
            expr = sp.solve(sp.Eq(self._expr, 0), self._syms[out])[0]
            expr = sp.simplify(expr.subs(subs))
            free = tuple(sorted({str(sv) for sv in expr.free_symbols}))
            return ExpressionFact(id="?", expression=str(expr),
                                  variables=free, unit=out_unit,
                                  source=self.rule["name"])

        target = self._syms[remaining[0]]
        roots = sp.solve(sp.Eq(self._expr.subs(subs), 0), target)
        vals = []
        for root in roots:
            try:
                n = complex(sp.N(root))
            except Exception:
                continue
            if abs(n.imag) > 1e-9:
                continue
            vals.append(n.real)
        if not vals:
            raise ValueError(f"no real solution for {remaining[0]!r} in "
                             f"{self.rule['name']}")
        pos = [v for v in vals if v > 0]
        val = pos[0] if pos else vals[0]
        return Quantity(value=float(val),
                        unit=self.rule["units"][remaining[0]])


_BY_NAME: dict[str, "Primitive"] = {}


def relation(name, *, units, out, doc=""):
    """Declare a plain function as a syllabus relation.

    Function parameters become the relation's variables (and the trace's
    role names); the function body is the residual expression, written with
    normal operators against sympy Symbols. Registration is side-effect free
    beyond this table: no globals() injection anywhere.
    """
    def deco(fn):
        params = tuple(inspect.signature(fn).parameters)
        units_inst = {k: (v() if isinstance(v, type) else v)
                      for k, v in units.items()}
        if set(units_inst) != set(params):
            raise ValueError(
                f"{name}: units keys {sorted(units)} do not match the "
                f"function's parameters {list(params)} — unit typing lives "
                f"next to the signature; they must agree exactly")
        syms = {p: sp.Symbol(p) for p in params}
        expr = sp.sympify(fn(**syms))
        if out not in params:
            raise ValueError(f"{name}: output {out!r} is not a parameter "
                             f"of {fn.__name__}")
        p = Primitive(name=name, vars=params, out=out, expr=expr,
                      units=units_inst, doc=doc)
        _BY_NAME[name] = p
        return p
    return deco


# ============================ relations ====================================

# -- vectors ----------------------------------------------------------------
@relation("vec.resultant_pythagoras",
          units={"f1": Newton, "f2": Newton, "F": Newton}, out="F",
          doc="perpendicular resultant |R| = sqrt(f1^2 + f2^2)")
def _resultant(f1, f2, F):
    return F - sp.sqrt(f1 ** 2 + f2 ** 2)


@relation("vec.components",
          units={"F": Newton, "theta": ANGLE, "vx": Newton, "vy": Newton},
          out="vx", doc="horizontal component F cos(theta), theta in degrees")
def _h_comp(F, theta, vx, vy):
    return vx - F * sp.cos(theta * sp.pi / 180)


# -- kinematics -------------------------------------------------------------
@relation("kin.suvat_s_s0_vt",
          units={"s": Meter, "s0": Meter, "v": MeterPerSecond, "t": Second},
          out="s", doc="s = s0 + v t")
def _s_s0_vt(s, s0, v, t):
    return s - (s0 + v * t)


@relation("kin.suvat_s_ut_athalf",
          units={"s": Meter, "u": MeterPerSecond, "a": MeterPerSecondSquared,
                 "t": Second},
          out="s", doc="s = u t + 1/2 a t^2")
def _s_ut_athalf(s, u, a, t):
    return s - (u * t + sp.Rational(1, 2) * a * t ** 2)


@relation("kin.suvat_v_u_at",
          units={"v": MeterPerSecond, "u": MeterPerSecond,
                 "a": MeterPerSecondSquared, "t": Second},
          out="v", doc="v = u + a t")
def _v_u_at(v, u, a, t):
    return v - (u + a * t)


@relation("kin.v2_u2_2",
          units={"v": MeterPerSecond, "u": MeterPerSecond,
                 "a": MeterPerSecondSquared, "s": Meter},
          out="v", doc="v^2 = u^2 + 2 a s")
def _v2_u2_2(v, u, a, s):
    return v ** 2 - (u ** 2 + 2 * a * s)


@relation("kin.projectile_range",
          units={"R": Meter, "v": MeterPerSecond, "theta": ANGLE,
                 "g": MeterPerSecondSquared},
          out="R", doc="range v^2 sin(2 theta)/g, theta in degrees")
def _prange(R, v, theta, g):
    return R - (v ** 2 * sp.sin(2 * theta * sp.pi / 180) / g)


@relation("kin.projectile_max_height",
          units={"h": Meter, "v": MeterPerSecond, "theta": ANGLE,
                 "g": MeterPerSecondSquared},
          out="h", doc="max height v^2 sin^2(theta)/(2g), theta degrees")
def _pheight(h, v, theta, g):
    return h - (v ** 2 * sp.sin(theta * sp.pi / 180) ** 2 / (2 * g))


# -- dynamics ---------------------------------------------------------------
@relation("dyn.fma",
          units={"F": Newton, "m": Kilogram, "a": MeterPerSecondSquared},
          out="F", doc="Newton II: F = m a")
def _fma(F, m, a):
    return F - m * a


@relation("dyn.weight",
          units={"w": Newton, "m": Kilogram, "g": MeterPerSecondSquared},
          out="w", doc="weight w = m g")
def _weight(w, m, g):
    return w - m * g


@relation("dyn.parallel_force",
          units={"p": Newton, "F": Newton, "theta": ANGLE},
          out="p", doc="component along incline F sin(theta)")
def _par_force(p, F, theta):
    return p - F * sp.sin(theta * sp.pi / 180)


@relation("dyn.normal_force",
          units={"N": Newton, "F": Newton, "theta": ANGLE},
          out="N", doc="normal component F cos(theta)")
def _norm_force(N, F, theta):
    return N - F * sp.cos(theta * sp.pi / 180)


@relation("dyn.friction_kinetic",
          units={"f": Newton, "mu": MU_COEF, "N": Newton},
          out="f", doc="sliding friction f = mu N")
def _fric(f, mu, N):
    return f - mu * N


@relation("dyn.circular_centripetal_force",
          units={"F": Newton, "m": Kilogram, "v": MeterPerSecond,
                 "r": Meter},
          out="F", doc="centripetal force m v^2 / r")
def _centr(F, m, v, r):
    return F - m * v ** 2 / r


@relation("dyn.omega_2pi_T",
          units={"omega": Hertz, "T": Second}, out="omega",
          doc="angular speed 2 pi / T")
def _om_2pi_T(omega, T):
    return omega - 2 * sp.pi / T


@relation("dyn.circular_v_omega_r",
          units={"v": MeterPerSecond, "omega": Hertz, "r": Meter},
          out="v", doc="v = omega r")
def _v_om_r(v, omega, r):
    return v - omega * r


@relation("dyn.momentum",
          units={"p": Unit(dimension=Newton().dimension * Second().dimension),
                 "m": Kilogram, "v": MeterPerSecond},
          out="p", doc="momentum p = m v")
def _momentum(p, m, v):
    return p - m * v


@relation("dyn.grav_force",
          units={"F": Newton, "G": G_NEWTON, "m1": Kilogram, "m2": Kilogram,
                 "r": Meter},
          out="F", doc="Newton gravitation G m1 m2 / r^2")
def _grav(F, G, m1, m2, r):
    return F - G * m1 * m2 / r ** 2


@relation("dyn.hooke",
          units={"F": Newton,
                 "k": Unit(dimension=Newton().dimension / Meter().dimension),
                 "x": Meter},
          out="F", doc="Hooke F = k x")
def _hooke(F, k, x):
    return F - k * x


# -- SHM ----------------------------------------------------------------------
@relation("dyn.shm_omega_k_m",
          units={"omega": Hertz,
                 "k": Unit(dimension=Newton().dimension / Meter().dimension),
                 "m": Kilogram},
          out="omega", doc="angular frequency sqrt(k/m)")
def _shm_om(omega, k, m):
    return omega - sp.sqrt(k / m)


@relation("dyn.shm_period_k_m",
          units={"T": Second,
                 "k": Unit(dimension=Newton().dimension / Meter().dimension),
                 "m": Kilogram},
          out="T", doc="period 2 pi sqrt(m/k)")
def _shm_T(T, k, m):
    return T - 2 * sp.pi * sp.sqrt(m / k)


@relation("dyn.shm_vmax",
          units={"v": MeterPerSecond, "omega": Hertz, "A": Meter},
          out="v", doc="max SHM speed omega A")
def _shm_vmax(v, omega, A):
    return v - omega * A


@relation("dyn.pendulum_period",
          units={"T": Second, "L": Meter, "g": MeterPerSecondSquared},
          out="T", doc="pendulum period 2 pi sqrt(L/g)")
def _pendulum_T(T, L, g):
    return T - 2 * sp.pi * sp.sqrt(L / g)


# -- energy / power -----------------------------------------------------------
@relation("en.kinetic",
          units={"ke": Joule, "m": Kilogram, "v": MeterPerSecond},
          out="ke", doc="kinetic energy 1/2 m v^2")
def _kinetic(ke, m, v):
    return ke - sp.Rational(1, 2) * m * v ** 2


@relation("en.grav_pe",
          units={"pe": Joule, "m": Kilogram, "g": MeterPerSecondSquared,
                 "h": Meter},
          out="pe", doc="gravitational potential m g h")
def _grav_pe(pe, m, g, h):
    return pe - m * g * h


@relation("en.work",
          units={"W": Joule, "F": Newton, "d": Meter, "theta": ANGLE},
          out="W", doc="work F d cos(theta)")
def _work(W, F, d, theta):
    return W - F * d * sp.cos(theta * sp.pi / 180)


@relation("en.power_work_time",
          units={"P": Watt, "w": Joule, "t": Second}, out="w",
          doc="energy w = P t")
def _pow_time(P, w, t):
    return w - P * t


@relation("en.wet_ke_ke0_work",
          units={"ke_f": Joule, "ke0": Joule, "work": Joule}, out="ke_f",
          doc="work-energy: KE = KE0 + net work")
def _wet(ke_f, ke0, work):
    return ke_f - (ke0 + work)


# -- heat / thermodynamics ----------------------------------------------------
@relation("th.q_mc_dt",
          units={"Q": Joule, "m": Kilogram, "c": SPECIFIC_HEAT, "dT": Kelvin},
          out="Q", doc="sensible heat m c dT")
def _q_mc(Q, m, c, dT):
    return Q - m * c * dT


@relation("th.q_ml",
          units={"Q": Joule, "m": Kilogram, "L": HEAT_CAP},
          out="Q", doc="latent heat m L")
def _q_ml(Q, m, L):
    return Q - m * L


@relation("th.expansion_len",
          units={"dl": Meter, "alpha": PER_KELVIN, "L0": Meter, "dT": Kelvin},
          out="dl", doc="linear expansion alpha L0 dT")
def _expand(dl, alpha, L0, dT):
    return dl - alpha * L0 * dT


@relation("th.pv_nrt",
          units={"P": Pascal, "V": VOLUME, "n": MOL, "R": GAS_R,
                 "T": Kelvin},
          out="V", doc="ideal gas P V = n R T")
def _pv_nrt(P, V, n, R, T):
    return P * V - n * R * T


@relation("th.first_law_delta_u",
          units={"U": Joule, "Q": Joule, "W": Joule}, out="U",
          doc="first law: dU = Q - W")
def _first_law(U, Q, W):
    return U - (Q - W)


# -- electrostatics -------------------------------------------------------------
@relation("el.coulomb",
          units={"F": Newton, "k": K_COULOMB, "q1": Coulomb, "q2": Coulomb,
                 "r": Meter},
          out="F", doc="Coulomb k q1 q2 / r^2")
def _coulomb(F, k, q1, q2, r):
    return F - k * q1 * q2 / r ** 2


@relation("el.field_point",
          units={"E": EL_FIELD, "k": K_COULOMB, "Q": Coulomb, "r": Meter},
          out="E", doc="point-charge field k Q / r^2")
def _field_point(E, k, Q, r):
    return E - k * Q / r ** 2


@relation("el.cap_energy",
          units={"U": Joule, "C": Unit(dimension=Coulomb().dimension
                                       / Volt().dimension), "V": Volt},
          out="U", doc="capacitor energy 1/2 C V^2")
def _cap_energy(U, C, V):
    return U - sp.Rational(1, 2) * C * V ** 2


# -- circuits -------------------------------------------------------------------
@relation("ckt.ohms",
          units={"v": Volt, "i": Ampere, "r": Ohm}, out="v",
          doc="Ohm v = i r")
def _ohms(v, i, r):
    return v - i * r


@relation("ckt.series_res",
          units={"r": Ohm, "r1": Ohm, "r2": Ohm}, out="r",
          doc="series resistance r = r1 + r2")
def _series_res(r, r1, r2):
    return r - (r1 + r2)


@relation("ckt.parallel_res",
          units={"r": Ohm, "r1": Ohm, "r2": Ohm}, out="r",
          doc="parallel resistance 1/r = 1/r1 + 1/r2")
def _parallel_res(r, r1, r2):
    return 1 / r - (1 / r1 + 1 / r2)


@relation("ckt.power_i2r",
          units={"p": Watt, "i": Ampere, "r": Ohm}, out="p",
          doc="joule heating i^2 r")
def _power_i2r(p, i, r):
    return p - i ** 2 * r


@relation("ckt.resistivity",
          units={"r": Ohm, "rho": RHO_RES, "l": Meter, "A": AREA}, out="r",
          doc="r = rho l / A")
def _resistivity(r, rho, l, A):
    return r - rho * l / A


@relation("ckt.current_charge_time",
          units={"i": Ampere, "Q": Coulomb, "t": Second}, out="i",
          doc="i = Q / t")
def _current(i, Q, t):
    return i - Q / t


# -- magnetism / induction --------------------------------------------------------
@relation("mag.force_wire",
          units={"F": Newton, "B": Tesla, "i": Ampere, "L": Meter}, out="F",
          doc="force on wire B i L (perpendicular)")
def _mag_wire(F, B, i, L):
    return F - B * i * L


@relation("mag.force_charge",
          units={"F": Newton, "q": Coulomb, "v": MeterPerSecond, "B": Tesla},
          out="F", doc="force on charge q v B (perpendicular)")
def _mag_charge(F, q, v, B):
    return F - q * v * B


@relation("mag.emf_motion",
          units={"emf": Volt, "B": Tesla, "L": Meter, "v": MeterPerSecond},
          out="emf", doc="motional EMF B L v")
def _emf_motion(emf, B, L, v):
    return emf - B * L * v


@relation("mag.flux_change_emf",
          units={"emf": Volt, "N": COUNT, "dPhi": Unit(dimension=
                  Volt().dimension * Second().dimension), "dt": Second},
          out="emf", doc="induced EMF N dPhi/dt")
def _emf_flux(emf, N, dPhi, dt):
    return emf - N * dPhi / dt


# -- optics ----------------------------------------------------------------------
@relation("opt.mirror_lens",
          units={"f": Meter, "v": Meter, "u": Meter}, out="f",
          doc="1/f = 1/v + 1/u")
def _mirror(f, v, u):
    return 1 / f - (1 / v + 1 / u)


@relation("opt.magnification",
          units={"m": R_INDEX, "v": Meter, "u": Meter}, out="m",
          doc="linear magnification v/u (signed by convention)")
def _magnification(m, v, u):
    return m - v / u


@relation("opt.snell",
          units={"n1": R_INDEX, "n2": R_INDEX, "t1": ANGLE, "t2": ANGLE},
          out="t2", doc="Snell n1 sin t1 = n2 sin t2; angles in degrees")
def _snell(n1, n2, t1, t2):
    return n1 * sp.sin(t1 * sp.pi / 180) - n2 * sp.sin(t2 * sp.pi / 180)


@relation("opt.critical",
          units={"n1": R_INDEX, "n2": R_INDEX, "tc": ANGLE}, out="tc",
          doc="sin tc = n2/n1, tc in degrees")
def _critical(n1, n2, tc):
    return sp.sin(tc * sp.pi / 180) - n2 / n1


@relation("opt.power",
          units={"P": Unit(dimension=Meter().dimension ** -1), "f": Meter},
          out="P", doc="lens power P = 1/f")
def _lens_power(P, f):
    return P - 1 / f


# -- modern physics ----------------------------------------------------------------
@relation("mod.photon_energy",
          units={"E": Joule, "h": PHOTON_H, "f": Hertz}, out="E",
          doc="photon E = h f")
def _photon(E, h, f):
    return E - h * f


@relation("mod.photoelectric",
          units={"E": Joule, "h": PHOTON_H, "f": Hertz, "phi": Joule},
          out="E", doc="KE = h f - phi")
def _photoelectric(E, h, f, phi):
    return E - (h * f - phi)


@relation("mod.hydrogen_en",
          units={"E": DIMENSIONLESS, "n": COUNT}, out="E",
          doc="hydrogen level -13.6/n^2 (values in eV, kept numeric)")
def _hydrogen(E, n):
    return E - (-13.6 / n ** 2)


@relation("mod.half_life",
          units={"N": COUNT, "N0": COUNT, "t": Second, "T": Second}, out="N",
          doc="N = N0 2^(-t/T)")
def _halflife(N, N0, t, T):
    return N - N0 * 2 ** (-t / T)


@relation("mod.debroglie",
          units={"lam": Meter, "h": PHOTON_H,
                 "p": Unit(dimension=Newton().dimension * Second().dimension)},
          out="lam", doc="de Broglie lambda = h / p")
def _debroglie(lam, h, p):
    return lam - h / p


@relation("mod.diode_current",
          units={"v": Volt, "i": Ampere, "r": Ohm}, out="r",
          doc="linear diode operating point v = i r")
def _diode(v, i, r):
    return v - i * r


@relation("mod.binding_energy",
          units={"E": Joule, "dm": Kilogram, "c": MeterPerSecond}, out="E",
          doc="binding energy dm c^2")
def _binding(E, dm, c):
    return E - dm * c ** 2


# -- waves -----------------------------------------------------------------------
@relation("w.speed_freq_len",
          units={"v": MeterPerSecond, "f": Hertz, "lam": Meter}, out="v",
          doc="wave speed f lambda")
def _wspeed(v, f, lam):
    return v - f * lam


@relation("w.string_speed_tension",
          units={"v": MeterPerSecond, "T": Newton,
                 "mu": Unit(dimension=Kilogram().dimension
                            / Meter().dimension)},
          out="v", doc="string wave speed sqrt(T/mu)")
def _wstring(v, T, mu):
    return v - sp.sqrt(T / mu)


@relation("w.fundamental_freq",
          units={"f": Hertz, "v": MeterPerSecond, "L": Meter}, out="f",
          doc="fundamental string f = v/(2L)")
def _wfundamental(f, v, L):
    return f - v / (2 * L)


# -- algebra convenience -------------------------------------------------------
@relation("alg.solve",
          units={"x": DIMENSIONLESS, "val": DIMENSIONLESS}, out="x",
          doc="x = val (bind val, leave x free or vice versa)")
def _solve_one(x, val):
    return x - val


# -------------------------------------------------------------------------------
PRIMITIVES = Grammar(
    name="physics",
    doc="One syllabus relation per transformation; composition is left to "
        "the agent-authored trace (see datasets/physics_syllabus_problems.csv).",
    transformations=dict(_BY_NAME),
)