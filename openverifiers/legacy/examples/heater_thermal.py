"""Heater-thermal (HSC 2nd paper, combined) — circuits x heat composed in
the trace with the SAME primitives the other examples use.

Run:  python3 openverifiers/examples/heater_thermal.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", ".."))

from openverifiers.legacy import Quantity
from openverifiers.legacy.v2 import Registry, run_trace, parse_dsl
from openverifiers.legacy.domains.algebra import ALGEBRA
from openverifiers.legacy.domains.physics_primitives import PRIMITIVES
from openverifiers.legacy.domains.units_si import (Ohm, Volt, Kilogram, Joule,
                                            Kelvin)
from openverifiers.legacy.units import Unit

CWATER = Unit(dimension=Joule().dimension /
              (Kilogram().dimension * Kelvin().dimension))

background = {
    "volts": Quantity(value=220.0, unit=Volt(), id="volts"),
    "R": Quantity(value=40.0, unit=Ohm(), id="R"),
    "mw": Quantity(value=1.0, unit=Kilogram(), id="mw"),
    "cwater": Quantity(value=4200.0, unit=CWATER, id="cwater"),
    "dtemp": Quantity(value=75.0, unit=Kelvin(), id="dtemp"),
}

TRACE = """
i = ckt.ohms(v=volts, r=R)              # current through the heater
p = ckt.power_i2r(i=i, r=R)             # joule heating power
q = th.q_mc_dt(m=mw, c=cwater, dT=dtemp)  # heat needed for the water
ep = en.power_work_time(P=p)            # energy = P t  (expression in t)
t = alg.equate(a=ep, b=q) with variable=t
"""

if __name__ == "__main__":
    reg = Registry([ALGEBRA, PRIMITIVES])
    r = run_trace(reg, background, parse_dsl(TRACE))
    print(r.render())
    if r.verdict == "pass":
        print(f"I = {r.env['i'].value:.1f} A | P = {r.env['p'].value:.0f} W | "
              f"Q = {r.env['q'].value:.0f} J | t = {r.env['t'].value:.1f} s")