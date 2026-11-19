#!/usr/bin/env python3
"""Generate the HSC/JEE-A/BUET syllabus physics dataset artifact.

Compiles parameterized instances of canonical problem archetypes drawn from
the HSC Physics 1st/2nd Paper (NCTB Bangladesh) syllabi plus JEE Advanced /
BUET admission combined problem forms. Sourcing is honest: these are
canonical problem SHAPES with standard values, not OCR of specific past
papers — the value of the artifact is the coverage map (topic x difficulty x
single/combined) and the explicit solve-chain per problem, which is what
Parts 2/5 of the grammar rebuild consume.

Output: openverifiers/datasets/physics_syllabus_problems.csv
"""

import csv
import collections
import random
from dataclasses import dataclass
from pathlib import Path

random.seed(20260920)

OUT = Path(__file__).resolve().parent / "physics_syllabus_problems.csv"


@dataclass
class T:
    """One canonical problem archetype -> many instances."""
    paper: str
    topics: tuple[str, ...]
    difficulty: int
    kind: str                      # single | combined
    chain: tuple[str, ...]         # primitive names needed, in order
    text: str                      # template, {k} placeholders
    variants: list[dict]           # one dict per instance


def rot(seed, n):
    return [seed] * n


def f(x):
    """Format a float parameter for problem text WITHOUT losing tiny
    constants: round(x, 2) previously turned 6.674e-11, 1.2e-5 and
    9.11e-31 into literal 0 in the artifact — an unfilled-slot disguise.
    Python's general format keeps ~6 significant digits, so physical
    constants stay non-zero and human-scale numbers stay short."""
    return f"{x:g}"


N = 200
templates: list[T] = []
add = templates.append

# ================= HSC 1ST PAPER ============================================

add(T("1st", ("kinematics",), 1, "single",
      ("kin.suvat_v_u_at",),
      "A car accelerates uniformly from rest at {a} m/s^2 for {t} s. "
      "Find its final velocity and the distance covered.",
      [dict(a=2.0, t=10), dict(a=1.5, t=20), dict(a=3.2, t=8),
       dict(a=0.8, t=30), dict(a=2.4, t=15), dict(a=1.2, t=25)] * 3))

add(T("1st", ("kinematics",), 1, "single",
      ("kin.suvat_s_ut_athalf",),
      "A stone is dropped from rest. Find the distance it falls in the "
      "first {t} s (g = {g} m/s^2).",
      [dict(t=2.0, g=9.8), dict(t=3.0, g=9.8), dict(t=4.0, g=9.8),
       dict(t=1.5, g=9.8), dict(t=5.0, g=9.8), dict(t=2.5, g=9.8)] * 2
      + [dict(t=2.0, g=10.0), dict(t=3.0, g=10.0)]))

add(T("1st", ("kinematics",), 1, "single",
      ("kin.v2_u2_2",),
      "A train slows uniformly from {u} m/s and stops after {s} m. Compute "
      "the magnitude of the acceleration.",
      [dict(u=20.0, s=100.0), dict(u=30.0, s=150.0), dict(u=25.0, s=125.0),
       dict(u=40.0, s=200.0), dict(u=15.0, s=75.0), dict(u=22.0, s=121.0)]))

add(T("1st", ("kinematics", "vectors"), 2, "single",
      ("kin.projectile_range",),
      "A projectile is launched at {v} m/s at {a} degrees to the horizontal. "
      "Find its horizontal range (g = {g} m/s^2).",
      [dict(v=50.0, a=30.0, g=9.8), dict(v=40.0, a=45.0, g=9.8),
       dict(v=60.0, a=60.0, g=9.8), dict(v=35.0, a=30.0, g=9.8),
       dict(v=45.0, a=45.0, g=9.8), dict(v=55.0, a=30.0, g=9.8)] * 2))

add(T("1st", ("kinematics", "vectors"), 2, "single",
      ("kin.projectile_max_height",),
      "A ball is thrown at {v} m/s at {a} degrees. Find the maximum height "
      "reached (g = {g} m/s^2).",
      [dict(v=30.0, a=45.0, g=9.8), dict(v=40.0, a=30.0, g=9.8),
       dict(v=35.0, a=60.0, g=9.8), dict(v=25.0, a=45.0, g=9.8)] * 3))

add(T("1st", ("vectors",), 1, "single",
      ("vec.resultant_pythagoras",),
      "Two perpendicular forces {f1} N and {f2} N act on a body. Find the "
      "magnitude of the resultant.",
      [dict(f1=3.0, f2=4.0), dict(f1=6.0, f2=8.0), dict(f1=5.0, f2=12.0),
       dict(f1=9.0, f2=12.0), dict(f1=7.0, f2=24.0), dict(f1=8.0, f2=15.0)]))

add(T("1st", ("vectors",), 1, "single",
      ("vec.components",),
      "Resolve a force of {f} N acting at {a} degrees above the horizontal "
      "into its horizontal and vertical components.",
      [dict(f=100.0, a=30.0), dict(f=50.0, a=60.0), dict(f=80.0, a=45.0),
       dict(f=120.0, a=30.0), dict(f=90.0, a=60.0), dict(f=70.0, a=45.0)]))

add(T("1st", ("dynamics",), 1, "single",
      ("dyn.fma",),
      "A {m} kg block accelerates at {a} m/s^2 under a single horizontal "
      "force. Find the force.",
      [dict(m=5.0, a=2.0), dict(m=10.0, a=3.0), dict(m=2.5, a=8.0),
       dict(m=12.0, a=1.5), dict(m=4.0, a=5.0), dict(m=8.0, a=2.25)] * 2))

add(T("1st", ("dynamics",), 2, "combined",
      ("dyn.fma", "kin.suvat_v_u_at"),
      "A {m} kg box starts from rest under a net force of {f} N. How long "
      "before it reaches {v} m/s?",
      [dict(m=4.0, f=8.0, v=12.0), dict(m=10.0, f=25.0, v=10.0),
       dict(m=2.0, f=6.0, v=9.0), dict(m=7.0, f=14.0, v=8.0)] * 2))

add(T("1st", ("dynamics", "friction"), 2, "combined",
      ("dyn.weight", "dyn.friction_kinetic", "dyn.fma"),
      "A {m} kg crate on a rough floor (mu_k = {mu}) is pushed by a "
      "{f} N horizontal force. Find its acceleration (g = {g} m/s^2).",
      [dict(m=10.0, mu=0.3, f=50.0, g=9.8), dict(m=5.0, mu=0.4, f=30.0,
                                                 g=9.8),
       dict(m=20.0, mu=0.2, f=60.0, g=9.8), dict(m=12.0, mu=0.35, f=70.0,
                                                 g=9.8)]))

add(T("1st", ("dynamics", "circular_motion"), 2, "single",
      ("dyn.circular_centripetal_force",),
      "A {m} kg ball swings on a {r} m string at {v} m/s. Find the "
      "centripetal force required.",
      [dict(m=2.0, r=1.5, v=6.0), dict(m=1.5, r=2.0, v=5.0),
       dict(m=3.0, r=1.0, v=8.0), dict(m=2.5, r=3.0, v=9.0)] * 2))

add(T("1st", ("dynamics", "circular_motion"), 2, "combined",
      ("dyn.omega_2pi_T", "dyn.circular_v_omega_r",
       "dyn.circular_centripetal_force"),
      "A {m} kg object moves uniformly on a {r} m radius circle with "
      "period {t} s. Find its centripetal force.",
      [dict(m=2.0, r=2.0, t=4.0), dict(m=3.0, r=5.0, t=10.0),
       dict(m=1.0, r=1.0, t=2.0), dict(m=4.0, r=3.0, t=6.0)] * 2))

add(T("1st", ("gravitation",), 1, "single",
      ("dyn.grav_force",),
      "Two bodies of masses {m1} kg and {m2} kg are {r} m apart. Find the "
      "gravitational force between them "
      "(G = 6.674e-11, use G = {G} in the data set).",
      [dict(m1=100.0, m2=100.0, r=1.0, G=6.674e-11),
       dict(m1=2e3, m2=3e3, r=2.0, G=6.674e-11),
       dict(m1=5e2, m2=8e2, r=4.0, G=6.674e-11),
       dict(m1=1e4, m2=2e4, r=10.0, G=6.674e-11)] * 2))

add(T("1st", ("gravitation",), 2, "single",
      ("dyn.grav_force", "dyn.weight"),
      "A {m} kg person stands at a height h = {h} km above Earth's surface "
      "(radius R = {Rr} km, M = 5.972e24 kg). Find the gravitational force "
      "(G = 6.674e-11).",
      [dict(m=70.0, h=400.0, Rr=6371.0),
       dict(m=60.0, h=0.0, Rr=6371.0),
       dict(m=80.0, h=1000.0, Rr=6371.0)]))

add(T("1st", ("work_energy_power",), 1, "single",
      ("en.kinetic",),
      "A {m} kg body moves at {v} m/s. Find its kinetic energy.",
      [dict(m=2.0, v=10.0), dict(m=5.0, v=4.0), dict(m=1.5, v=12.0),
       dict(m=3.0, v=8.0), dict(m=4.0, v=5.0), dict(m=2.5, v=6.0)] * 2))

add(T("1st", ("work_energy_power",), 1, "single",
      ("en.grav_pe",),
      "A {m} kg load is raised {h} m. Find its gain in gravitational "
      "potential energy (g = {g}).",
      [dict(m=10.0, h=20.0, g=9.8), dict(m=5.0, h=50.0, g=9.8),
       dict(m=2.0, h=100.0, g=9.8), dict(m=8.0, h=25.0, g=9.8)] * 2))

add(T("1st", ("work_energy_power",), 2, "combined",
      ("en.kinetic", "en.wet_ke_ke0_work", "en.work"),
      "A {m} kg sled moving at {v0} m/s is stopped by a constant braking "
      "force over a distance {d} m. Find the force magnitude.",
      [dict(m=20.0, v0=10.0, d=25.0), dict(m=12.0, v0=8.0, d=16.0),
       dict(m=30.0, v0=6.0, d=18.0), dict(m=15.0, v0=12.0, d=30.0)]))

add(T("1st", ("work_energy_power",), 3, "combined",
      ("en.kinetic", "dyn.weight", "dyn.parallel_force",
       "dyn.friction_kinetic", "en.work", "alg.equate"),
      "A {m} kg block slides up a {th} deg incline at {v} m/s. Coefficient "
      "of kinetic friction is {mu}. Find how far it travels before "
      "stopping (g = {g}).",
      [dict(m=2.0, th=30.0, v=10.0, mu=0.3, g=9.8),
       dict(m=5.0, th=45.0, v=8.0, mu=0.2, g=9.8),
       dict(m=3.0, th=37.0, v=12.0, mu=0.25, g=9.8),
       dict(m=4.0, th=25.0, v=9.0, mu=0.4, g=9.8)]))

add(T("1st", ("work_energy_power",), 1, "single",
      ("en.power_work_time",),
      "A pump does {w} J of work in {t} s. Find its average power.",
      [dict(w=6000.0, t=10.0), dict(w=1e5, t=20.0), dict(w=250.0, t=5.0),
       dict(w=4800.0, t=12.0), dict(w=9e4, t=30.0), dict(w=360.0, t=6.0)]))

add(T("1st", ("elasticity",), 2, "single",
      ("dyn.hooke",),
      "A spring of natural length {l} m is stretched {x} m by a force of "
      "{f} N. Find the spring constant.",
      [dict(l=0.5, x=0.1, f=20.0), dict(l=1.0, x=0.05, f=15.0),
       dict(l=0.8, x=0.2, f=40.0), dict(l=0.6, x=0.08, f=16.0)] * 2))

add(T("1st", ("elasticity", "shm"), 3, "combined",
      ("dyn.hooke", "dyn.shm_omega_k_m", "dyn.shm_vmax"),
      "A {m} g mass hangs on a spring of constant {k} N/m. It is pulled "
      "down by an amplitude {a} m and released. Find the maximum speed.",
      [dict(m=0.2, k=200.0, a=0.05), dict(m=0.5, k=320.0, a=0.04),
       dict(m=0.1, k=90.0, a=0.06), dict(m=0.25, k=250.0, a=0.05)] * 2))

add(T("1st", ("shm",), 1, "single",
      ("dyn.shm_period_k_m",),
      "A {m} kg mass attached to a {k} N/m spring oscillates. Find the "
      "period.",
      [dict(m=0.5, k=50.0), dict(m=0.2, k=80.0), dict(m=2.0, k=200.0),
       dict(m=0.8, k=100.0)] * 3))

add(T("1st", ("shm",), 2, "single",
      ("dyn.pendulum_period",),
      "A simple pendulum of length {l} m (g = {g}) oscillates with small "
      "amplitude. Find its period.",
      [dict(l=0.25, g=9.8), dict(l=1.0, g=9.8), dict(l=4.0, g=9.8),
       dict(l=0.09, g=9.8), dict(l=2.0, g=9.8)] * 2))

add(T("1st", ("mechanical_waves",), 1, "single",
      ("w.speed_freq_len",),
      "A wave travels with frequency {f} Hz and wavelength {l} m. Find the "
      "wave speed.",
      [dict(f=50.0, l=2.0), dict(f=20.0, l=5.0), dict(f=100.0, l=0.5),
       dict(f=25.0, l=4.0), dict(f=200.0, l=0.25), dict(f=10.0, l=8.0)]))

add(T("1st", ("mechanical_waves", "strings"), 2, "single",
      ("w.string_speed_tension",),
      "A string under tension {t} N has linear density {mu} kg/m. Find the "
      "wave speed.",
      [dict(t=64.0, mu=0.01), dict(t=100.0, mu=0.04), dict(t=25.0, mu=0.01),
       dict(t=80.0, mu=0.02), dict(t=200.0, mu=0.08), dict(t=50.0, mu=0.02)]))

add(T("1st", ("mechanical_waves", "strings"), 3, "combined",
      ("w.string_speed_tension", "w.fundamental_freq"),
      "A string of length {l} m, mass {m} g, under tension {t} N vibrates in "
      "its fundamental mode. Find the fundamental frequency.",
      [dict(l=1.0, m=4.0, t=100.0), dict(l=0.5, m=2.0, t=50.0),
       dict(l=0.8, m=3.2, t=60.0), dict(l=1.2, m=6.0, t=90.0)] * 2))

add(T("1st", ("dynamics", "momentum"), 2, "single",
      ("dyn.momentum",),
      "A {m} kg truck moves at {v} m/s. Find its momentum.",
      [dict(m=2000.0, v=15.0), dict(m=1200.0, v=20.0), dict(m=3000.0, v=10.0),
       dict(m=800.0, v=25.0), dict(m=1500.0, v=18.0), dict(m=2500.0, v=12.0)]))

add(T("1st", ("dynamics", "momentum", "collisions"), 3, "combined",
      ("dyn.momentum", "alg.equate", "alg.solve"),
      "A {m1} kg object moving at {v1} m/s collides inelastically head-on "
      "with a stationary {m2} kg object and they move together. Find the "
      "common speed.",
      [dict(m1=2.0, v1=6.0, m2=1.0), dict(m1=4.0, v1=10.0, m2=6.0),
       dict(m1=3.0, v1=8.0, m2=2.0), dict(m1=5.0, v1=4.0, m2=5.0)] * 2))

add(T("1st", ("circular_motion", "gravitation"), 3, "combined",
      ("dyn.grav_force", "dyn.circular_centripetal_force", "alg.equate"),
      "A satellite of mass {m} kg orbits Earth at radius {r} m from the "
      "center (M = 5.972e24, G = 6.674e-11). Find the orbital speed.",
      [dict(m=500.0, r=7.0e6), dict(m=1000.0, r=7.4e6), dict(m=200.0, r=6.8e6)]))

add(T("1st", ("kinematics", "circular_motion"), 2, "combined",
      ("kin.suvat_v_u_at", "dyn.circular_v_omega_r"),
      "A car reaches {v} m/s in {t} s from rest. Its wheels of radius {r} m "
      "then turn without slipping. Find the final angular velocity of the "
      "wheels.",
      [dict(v=20.0, t=10.0, r=0.35), dict(v=30.0, t=15.0, r=0.4),
       dict(v=25.0, t=12.0, r=0.3)] * 3))

# ================= HSC 2ND PAPER ============================================

add(T("2nd", ("heat",), 1, "single",
      ("th.q_mc_dt",),
      "How much heat raises {m} g of water from {t1} to {t2} C "
      "(c = 4200 J/kg/K)?",
      [dict(m=0.2, t1=20.0, t2=70.0), dict(m=0.5, t1=25.0, t2=100.0),
       dict(m=1.0, t1=10.0, t2=60.0), dict(m=0.3, t1=15.0, t2=85.0)] * 3))

add(T("2nd", ("heat",), 1, "single",
      ("th.q_ml",),
      "Find the heat needed to melt {m} kg of ice at 0 C "
      "(L_f = 3.34e5 J/kg).",
      [dict(m=0.5), dict(m=1.0), dict(m=0.25), dict(m=2.0), dict(m=0.75),
       dict(m=1.5)]))

add(T("2nd", ("heat",), 3, "combined",
      ("th.q_ml", "th.q_mc_dt", "alg.equate"),
      "Ice at 0 C of mass {m} kg is placed in {mw} kg of water at {t} C. "
      "Find the final temperature (c = 4200, L_f = 3.34e5).",
      [dict(m=0.05, mw=0.2, t=30.0), dict(m=0.1, mw=0.4, t=40.0),
       dict(m=0.04, mw=0.1, t=50.0)]))

add(T("2nd", ("heat", "thermal_expansion"), 2, "single",
      ("th.expansion_len",),
      "A {l} m steel rail heats up by {dt} C. Coefficient of linear "
      "expansion is {al} /K. Find the expansion.",
      [dict(l=100.0, dt=30.0, al=1.2e-5), dict(l=50.0, dt=50.0, al=1.2e-5),
       dict(l=200.0, dt=20.0, al=2.4e-5), dict(l=25.0, dt=40.0, al=1.2e-5)] * 2))

add(T("2nd", ("heat", "thermodynamics"), 2, "single",
      ("th.pv_nrt",),
      "A container holds {n} mol of ideal gas at {t} C and {p} Pa. Find "
      "the volume (R = 8.314).",
      [dict(n=1.0, t=27.0, p=1e5), dict(n=2.0, t=127.0, p=2e5),
       dict(n=0.5, t=57.0, p=1e5), dict(n=4.0, t=27.0, p=5e4)] * 2))

add(T("2nd", ("thermodynamics",), 2, "single",
      ("th.first_law_delta_u",),
      "A gas absorbs {q} J of heat while doing {w} J of work. Find the "
      "change in internal energy.",
      [dict(q=500.0, w=200.0), dict(q=1000.0, w=700.0), dict(q=250.0, w=100.0),
       dict(q=800.0, w=300.0), dict(q=1200.0, w=500.0), dict(q=300.0, w=150.0)]))

add(T("2nd", ("electrostatics",), 1, "single",
      ("el.coulomb",),
      "Two point charges {q1} uC and {q2} uC are {r} cm apart. Find the "
      "electric force between them (k = 8.99e9).",
      [dict(q1=2.0, q2=3.0, r=10.0), dict(q1=5.0, q2=4.0, r=20.0),
       dict(q1=1.0, q2=1.0, r=30.0), dict(q1=6.0, q2=2.0, r=15.0)] * 3))

add(T("2nd", ("electrostatics",), 2, "single",
      ("el.field_point",),
      "Find the electric field at {r} m from a point charge of {q} uC "
      "(k = 8.99e9).",
      [dict(q=5.0, r=0.5), dict(q=10.0, r=1.0), dict(q=2.0, r=0.4),
       dict(q=8.0, r=2.0), dict(q=15.0, r=0.8), dict(q=3.0, r=1.5)]))

add(T("2nd", ("electrostatics",), 2, "combined",
      ("el.coulomb", "dyn.fma"),
      "A {m} g charged particle (charge {q} uC) is released in a uniform "
      "field of {e} N/C. Find its initial acceleration.",
      [dict(m=0.5, q=2.0, e=1e4), dict(m=1.0, q=5.0, e=2e3),
       dict(m=0.2, q=1.0, e=1e5), dict(m=2.0, q=4.0, e=5e3)] * 2))

add(T("2nd", ("current_electricity",), 1, "single",
      ("ckt.ohms",),
      "A resistor of {r} ohm carries {i} A. Find the voltage across it.",
      [dict(r=10.0, i=2.0), dict(r=5.0, i=4.0), dict(r=20.0, i=0.5),
       dict(r=12.0, i=3.0), dict(r=8.0, i=1.5), dict(r=100.0, i=0.2)]))

add(T("2nd", ("current_electricity",), 2, "single",
      ("ckt.series_res",),
      "Two resistors {r1} ohm and {r2} ohm are connected in series. Find "
      "the effective resistance.",
      [dict(r1=10.0, r2=20.0), dict(r1=5.0, r2=15.0), dict(r1=30.0, r2=40.0),
       dict(r1=12.0, r2=18.0), dict(r1=25.0, r2=35.0), dict(r1=4.0, r2=16.0)]))

add(T("2nd", ("current_electricity",), 2, "single",
      ("ckt.parallel_res",),
      "Two resistors {r1} ohm and {r2} ohm are connected in parallel. Find "
      "the effective resistance.",
      [dict(r1=10.0, r2=10.0), dict(r1=6.0, r2=12.0), dict(r1=20.0, r2=30.0),
       dict(r1=15.0, r2=5.0), dict(r1=8.0, r2=24.0), dict(r1=18.0, r2=9.0)]))

add(T("2nd", ("current_electricity", "circuits"), 3, "combined",
      ("ckt.ohms", "ckt.parallel_res", "ckt.series_res"),
      "A {v} V battery drives current through {r1} ohm in parallel with "
      "{r2} ohm, and the pair in series with {r3} ohm. Find the current "
      "drawn from the battery.",
      [dict(v=12.0, r1=6.0, r2=12.0, r3=4.0),
       dict(v=24.0, r1=10.0, r2=15.0, r3=6.0),
       dict(v=9.0, r1=4.0, r2=8.0, r3=3.0),
       dict(v=18.0, r1=12.0, r2=24.0, r3=5.0)] * 2))

add(T("2nd", ("current_electricity",), 2, "single",
      ("ckt.power_i2r",),
      "A heater of resistance {r} ohm draws {i} A. Find the power "
      "dissipated.",
      [dict(r=20.0, i=5.0), dict(r=10.0, i=8.0), dict(r=50.0, i=2.0),
       dict(r=25.0, i=4.0), dict(r=40.0, i=3.0), dict(r=15.0, i=6.0)]))

add(T("2nd", ("current_electricity", "heat"), 3, "combined",
      ("ckt.ohms", "ckt.power_i2r", "th.q_mc_dt", "en.power_work_time",
       "alg.equate"),
      "A heater of resistance {r} ohm runs on {v} V. How long must it run "
      "to raise {mw} kg of water from {t1} to {t2} C (c = 4200)?",
      [dict(r=40.0, v=220.0, mw=1.0, t1=25.0, t2=100.0),
       dict(r=80.0, v=220.0, mw=2.0, t1=20.0, t2=80.0),
       dict(r=30.0, v=120.0, mw=0.5, t1=30.0, t2=90.0)] * 2))

add(T("2nd", ("magnetism",), 1, "single",
      ("mag.force_wire",),
      "A {l} m conducting wire carries {i} A perpendicular to a {b} T "
      "magnetic field. Find the magnetic force on it.",
      [dict(l=0.5, i=3.0, b=0.2), dict(l=1.0, i=5.0, b=0.1),
       dict(l=0.8, i=2.0, b=0.5), dict(l=2.0, i=4.0, b=0.05)] * 3))

add(T("2nd", ("magnetism",), 2, "single",
      ("mag.force_charge",),
      "A particle with charge {q} uC and speed {v} m/s enters a {b} T "
      "field perpendicularly. Find the magnetic force.",
      [dict(q=3.0, v=2e4, b=0.1), dict(q=1.0, v=5e5, b=0.01),
       dict(q=5.0, v=1e4, b=0.2), dict(q=2.0, v=1e5, b=0.05)] * 2))

add(T("2nd", ("electromagnetic_induction",), 2, "single",
      ("mag.emf_motion",),
      "A {l} m conductor moves at {v} m/s perpendicular to a {b} T field. "
      "Find the induced EMF.",
      [dict(l=0.5, v=20.0, b=0.4), dict(l=1.0, v=10.0, b=0.2),
       dict(l=2.0, v=5.0, b=0.5), dict(l=0.4, v=30.0, b=0.3)] * 2))

add(T("2nd", ("electromagnetic_induction",), 2, "single",
      ("mag.flux_change_emf",),
      "The magnetic flux through a {n}-turn coil changes by {d} Wb in "
      "{t} s. Find the average induced EMF.",
      [dict(n=100.0, d=0.02, t=0.1), dict(n=50.0, d=0.05, t=0.25),
       dict(n=200.0, d=0.01, t=0.05), dict(n=25.0, d=0.04, t=0.2)] * 2))

add(T("2nd", ("optics",), 1, "single",
      ("opt.snell",),
      "Light enters glass (n = {n}) from air (n = 1) at {a} degrees to "
      "the normal. Find the refraction angle.",
      [dict(n=1.5, a=30.0), dict(n=1.6, a=45.0), dict(n=1.33, a=40.0),
       dict(n=1.5, a=60.0), dict(n=2.0, a=30.0), dict(n=1.5, a=20.0)] * 2))

add(T("2nd", ("optics",), 2, "single",
      ("opt.mirror_lens",),
      "An object is placed {u} cm in front of a concave mirror of focal "
      "length {f} cm. Find the image distance.",
      [dict(u=30.0, f=20.0), dict(u=40.0, f=15.0), dict(u=25.0, f=10.0),
       dict(u=60.0, f=20.0), dict(u=50.0, f=30.0), dict(u=20.0, f=8.0)] * 2))

add(T("2nd", ("optics",), 3, "combined",
      ("opt.mirror_lens", "opt.magnification"),
      "An object {h} cm tall is placed {u} cm in front of a concave lens "
      "of focal length {f} cm. Find the image height.",
      [dict(h=2.0, u=20.0, f=10.0), dict(h=3.0, u=30.0, f=15.0),
       dict(h=1.5, u=25.0, f=12.0), dict(h=4.0, u=40.0, f=20.0)] * 2))

add(T("2nd", ("optics",), 2, "single",
      ("opt.critical",),
      "Find the critical angle for light going from glass (n = {n}) into "
      "air.",
      [dict(n=1.5), dict(n=1.6), dict(n=2.0), dict(n=1.33),
       dict(n=1.8), dict(n=1.4)]))

add(T("2nd", ("modern_physics", "photoelectric"), 2, "single",
      ("mod.photon_energy",),
      "Find the photon energy for light of frequency {f} Hz "
      "(h = 6.626e-34).",
      [dict(f=5.0e14), dict(f=6.0e14), dict(f=7.5e14), dict(f=4.5e14),
       dict(f=1.0e15), dict(f=2.5e14)] * 2))

add(T("2nd", ("modern_physics", "photoelectric"), 2, "single",
      ("mod.photoelectric",),
      "Light of frequency {f} Hz strikes a metal with work function "
      "{ph} eV. Find the max kinetic energy of ejected electrons "
      "(h = 6.626e-34, 1 eV = 1.602e-19 J).",
      [dict(f=8.0e14, ph=2.0), dict(f=1.0e15, ph=2.0), dict(f=6.0e14, ph=1.5),
       dict(f=9.0e14, ph=2.5)] * 2))

add(T("2nd", ("modern_physics", "photoelectric"), 3, "combined",
      ("mod.photoelectric", "en.kinetic", "mag.force_charge"),
      "Photoelectrons (mass {m} kg) are released at max speed from a "
      "surface (work function {ph} eV) by light of {f} Hz, then enter a "
      "{b} T perpendicular field. Find the magnetic force on each.",
      [dict(m=9.11e-31, ph=2.0, f=1.2e15, b=0.02),
       dict(m=9.11e-31, ph=2.3, f=1.5e15, b=0.01)] * 3))

add(T("2nd", ("modern_physics", "nuclear"), 2, "single",
      ("mod.half_life",),
      "A sample has activity {a} Bq and half-life {t} days. Find the "
      "remaining fraction after {d} days.",
      [dict(a=1e6, t=8.0, d=24.0), dict(a=5e5, t=3.0, d=9.0),
       dict(a=2e6, t=10.0, d=30.0), dict(a=1e5, t=5.0, d=20.0)] * 2))

add(T("2nd", ("modern_physics", "atomic"), 2, "single",
      ("mod.hydrogen_en",),
      "Find the ionization energy of hydrogen from the n = {n} level "
      "(13.6 eV / n^2).",
      [dict(n=1.0), dict(n=2.0), dict(n=3.0), dict(n=4.0)] * 3))

add(T("2nd", ("modern_physics", "semiconductors"), 2, "single",
      ("mod.diode_current",),
      "A diode carries {i} mA at a forward bias of {v} V. Find the forward "
      "resistance at the operating point (simplified linear model).",
      [dict(i=20.0, v=0.7), dict(i=30.0, v=0.8), dict(i=10.0, v=0.6),
       dict(i=25.0, v=0.9)] * 2))

# ===== explicitly OUT OF SCOPE today (calculus/DE or non-algebraic) =========
add(T("JEE-A", ("kinematics", "calculus"), 4, "combined",
      ("OUT_OF_SCOPE:CALCULUS",),
      "A particle moves as x(t) = {a}t^3 - {b}t. Find its instantaneous "
      "velocity at t = {t} s.",
      [dict(a=2.0, b=5.0, t=3.0)] * 2))
add(T("JEE-A", ("current_electricity", "rc_circuits"), 4, "combined",
      ("OUT_OF_SCOPE:ODE",),
      "An RC circuit (R = {r} ohm, C = {c} uF) charges from a {v} V "
      "source. Find the charge at t = {t} s.",
      [dict(r=1e3, c=10.0, v=12.0, t=2.0)] * 2))
add(T("JEE-A", ("shm", "oscillation"), 4, "combined",
      ("OUT_OF_SCOPE:ODE",),
      "A damped oscillator (k = {k} N/m, gamma = {g} s^-1) is released. "
      "Write the solution form; find the amplitude after {t} s.",
      [dict(k=40.0, g=0.2, t=5.0)] * 2))
add(T("BUET", ("kinematics", "calculus"), 4, "combined",
      ("OUT_OF_SCOPE:CALCULUS",),
      "Velocity of a body is v(t) = {a}t^2 + {b}t. Find total displacement "
      "over the first {t} s.",
      [dict(a=2.0, b=3.0, t=4.0)] * 2))
add(T("2nd", ("optics", "interference"), 3, "combined",
      ("OUT_OF_SCOPE:NOT_BUILT",),
      "Young double-slit: slit separation {d} mm, screen {l} m away, "
      "lambda = {w} nm. Find the fringe width.",
      [dict(d=0.2, l=1.5, w=550.0)] * 2))
add(T("2nd", ("modern_physics", "doppler"), 3, "combined",
      ("OUT_OF_SCOPE:NOT_BUILT",),
      "A source at {f} Hz moves at {v} m/s toward a stationary observer "
      "(v_sound = {c} m/s). Find the observed frequency.",
      [dict(f=1000.0, v=40.0, c=343.0)] * 2))


print("templates:", len(templates))

# ================= JEE ADVANCED / BUET combined =============================

add(T("JEE-A", ("kinematics", "waves"), 4, "combined",
      ("kin.suvat_s_ut_athalf", "w.speed_freq_len", "alg.solve"),
      "A stone is dropped from a cliff of height {h} m. Use v = {vs} m/s "
      "for sound in air. Find the time between releasing the stone and "
      "hearing the splash (g = {g}).",
      [dict(h=45.0, vs=340.0, g=9.8), dict(h=80.0, vs=340.0, g=9.8),
       dict(h=20.0, vs=340.0, g=9.8)]))

add(T("JEE-A", ("work_energy_power", "escape", "gravitation"), 4, "combined",
      ("en.grav_pe", "en.kinetic", "alg.equate"),
      "Find the escape speed from a planet of mass {m} kg and radius "
      "{r} km, neglecting air resistance (G = 6.674e-11).",
      [dict(m=5.972e24, r=6371.0), dict(m=3.3e23, r=2439.0),
       dict(m=7.35e22, r=1737.0)] * 2))

add(T("BUET", ("kinematics", "dynamics"), 4, "combined",
      ("kin.suvat_s_ut_athalf", "dyn.fma", "dyn.weight", "alg.equate"),
      "A projectile is launched vertically from a {m} kg rocket at "
      "{v} m/s. Thrust {f} N acts for {t} s during ascent; then only "
      "gravity (g = {g}). Find the maximum height reached.",
      [dict(m=50.0, v=0.0, f=800.0, t=5.0, g=9.8),
       dict(m=200.0, v=0.0, f=2500.0, t=8.0, g=9.8)] * 2))

add(T("BUET", ("current_electricity", "heat"), 4, "combined",
      ("ckt.series_res", "ckt.ohms", "ckt.power_i2r", "th.q_mc_dt",
       "en.power_work_time"),
      "An immersion heater made of two resistors {r1} and {r2} ohm in "
      "series is connected to {v} V. It must raise {mw} kg of water "
      "{dt} K. Find the time required (c = 4200).",
      [dict(r1=20.0, r2=30.0, v=220.0, mw=1.0, dt=60.0),
       dict(r1=10.0, r2=20.0, v=110.0, mw=0.8, dt=50.0)] * 2))

add(T("BUET", ("magnetism", "circular_motion"), 4, "combined",
      ("mag.force_charge", "dyn.circular_centripetal_force", "alg.equate"),
      "A charged particle (charge {q} uC, mass {m} kg) enters a {b} T "
      "field at {v} m/s perpendicularly. Find the radius of its circular "
      "path.",
      [dict(q=2.0, m=6.64e-27, b=0.5, v=1e6),
       dict(q=1.0, m=9.11e-31, b=0.1, v=5e5)] * 3))

print("templates ok:", len(templates))

# build instances from all templates, selecting exactly N rows with fixed
# per-paper quotas (round-robin within each paper so the slice keeps mix)
QUOTAS = {"1st": 112, "2nd": 62, "JEE-A": 13, "BUET": 13}
rows = []
rid = 0
by_paper: dict[str, list[dict]] = {p: [] for p in QUOTAS}
for t in templates:
    for vars_ in t.variants:
        rid += 1
        fmt_vars = {k: (f(v) if isinstance(v, float) else v)
                    for k, v in vars_.items()}
        try:
            text = t.text.format(**fmt_vars)
        except KeyError:
            text = t.text
        by_paper[t.paper].append({
            "id": f"P{rid:03d}", "paper": t.paper,
            "topics": ";".join(t.topics), "difficulty": t.difficulty,
            "kind": t.kind, "chain": ";".join(t.chain),
            "problem": text,
        })

# select exactly N rows with fixed per-paper quotas; within a paper, modular
# selection across ALL archetype instances so every template appears
comp = collections.Counter()
picks: dict[str, int] = {p: 0 for p in QUOTAS}
rows = []
rid = 0
for _ in range(N):
    shortages = [(QUOTAS[p] - comp[p], p) for p in QUOTAS
                 if comp[p] < QUOTAS[p]]
    if not shortages:
        break
    _, p = max(shortages)             # paper farthest below quota
    pool = by_paper[p]
    step = 7                          # coprime with every pool length ->
                                      # indices sweep the WHOLE pool, so all
                                      # archetypes appear in the quota slice
    src = pool[(picks[p] * step) % len(pool)]
    picks[p] += 1
    rid += 1
    rows.append(dict(src, id=f"P{rid:03d}"))
    comp[p] += 1


with open(OUT, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["id", "paper", "topics", "difficulty",
                                        "kind", "chain", "problem"])
    w.writeheader()
    for r in rows:
        w.writerow(r)

papers = {}
kinds = {}
for r in rows:
    papers[r["paper"]] = papers.get(r["paper"], 0) + 1
    kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
print(f"wrote {len(rows)} rows -> {OUT}")
print("papers:", papers)
print("kinds:", kinds)