"""Work-energy incline (HSC 1st paper, combined) — solved with ONLY
registered syllabus primitives composed in the trace.

Run:  python3 openverifiers/examples/incline_energy.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", ".."))

from openverifiers.legacy import Quantity
from openverifiers.legacy.v2 import Registry, run_trace, parse_dsl
from openverifiers.legacy.domains.algebra import ALGEBRA
from openverifiers.legacy.domains.physics_primitives import PRIMITIVES
from openverifiers.legacy.domains.units_si import (Meter, MeterPerSecond,
                                            MeterPerSecondSquared, Newton,
                                            Kilogram, Joule)

background = {
    "mass": Quantity(value=2.0, unit=Kilogram(), id="mass"),
    "vel": Quantity(value=10.0, unit=MeterPerSecond(), id="vel"),
    "g": Quantity(value=9.8, unit=MeterPerSecondSquared(), id="g"),
    "theta": Quantity(value=30.0, unit=Meter(), id="theta"),
    "mu": Quantity(value=0.3, unit=Meter(), id="mu"),
    "kezero": Quantity(value=0.0, unit=Joule(), id="kezero"),
}

TRACE = """
ke = en.kinetic(m=mass, v=vel)              # 1/2 m v^2
w = dyn.weight(m=mass, g=g)                 # m g
fp = dyn.parallel_force(F=w, theta=theta)   # m g sin30
N = dyn.normal_force(F=w, theta=theta)      # m g cos30
ff = dyn.friction_kinetic(mu=mu, N=N)       # mu N
wg = en.work(F=fp) with theta=180           # -(mg sin30) d  (expression in d)
wf = en.work(F=ff) with theta=180           # -(mu N) d
wtot = alg.add(a=wg, b=wf)                  # -(fp+ff) d
kf = en.wet_ke_ke0_work(ke0=ke, work=wtot)  # KE - (work) = 0  (expression)
d = alg.equate(a=kf, b=kezero) with variable=d
"""

if __name__ == "__main__":
    reg = Registry([ALGEBRA, PRIMITIVES])
    r = run_trace(reg, background, parse_dsl(TRACE))
    print(r.render())
    if r.verdict == "pass":
        print(f"distance before stopping: d = {r.env['d'].value:.2f} m "
              f"(roughly {r.env['d'].value:.1f} m; v^2/(2g(sin30+mu cos30)) "
              f"= 100/(2*9.8*(0.5+0.3*0.866)) m)")