"""SI unit instances + display tokens.

These are concrete SI instances — reusable by any physical-science domain
(physics now, chemistry/engineering later), but NOT domain-agnostic like the
`Unit`/`Dimension` base machinery in core. They stay OUT of core and OUT of
`domains/physics.py`'s kinematics/dynamics content, so a future non-mechanics
science domain can import units without dragging in chase-adjacent relations.
"""

from __future__ import annotations

from openverifiers.legacy.units import Unit, Dimension, UnitSystem

from openverifiers.legacy.facts import register_unit_token, register_unit_display


class Meter(Unit):
    dimension: Dimension = Dimension(length=1)


class Kilogram(Unit):
    dimension: Dimension = Dimension(mass=1)


class Second(Unit):
    dimension: Dimension = Dimension(time=1)


class Ampere(Unit):
    dimension: Dimension = Dimension(current=1)


class Kelvin(Unit):
    dimension: Dimension = Dimension(temperature=1)


class Mole(Unit):
    dimension: Dimension = Dimension(amount=1)


class Candela(Unit):
    dimension: Dimension = Dimension(luminous=1)


class MeterPerSecond(Unit):
    dimension: Dimension = Meter().dimension / Second().dimension


class MeterPerSecondSquared(Unit):
    dimension: Dimension = Meter().dimension / (Second().dimension ** 2)


class Newton(Unit):
    dimension: Dimension = Kilogram().dimension * Meter().dimension \
                           / (Second().dimension ** 2)


class Joule(Unit):
    dimension: Dimension = Kilogram().dimension * (Meter().dimension ** 2) \
                           / (Second().dimension ** 2)


class KilogramMeterPerSecond(Unit):
    dimension: Dimension = Kilogram().dimension * Meter().dimension \
                           / Second().dimension


class Kilometer(Unit):
    dimension: Dimension = Meter().dimension
    scale: float = 1000.0


class Dollar(Unit):
    """Money, modeled as its own dimensionless base for v2 scenario math."""
    dimension: Dimension = Dimension()


# -- derived mechanical / electrical / thermal units --------------------------
class Watt(Unit):
    dimension: Dimension = Joule().dimension / Second().dimension


class Hertz(Unit):
    dimension: Dimension = Second().dimension ** -1


class Coulomb(Unit):
    dimension: Dimension = Ampere().dimension * Second().dimension


class Volt(Unit):
    dimension: Dimension = Joule().dimension / Coulomb().dimension


class Ohm(Unit):
    dimension: Dimension = Volt().dimension / Ampere().dimension


class Tesla(Unit):
    dimension: Dimension = Newton().dimension / (Ampere().dimension
                                                 * Meter().dimension)


class Weber(Unit):
    dimension: Dimension = Volt().dimension * Second().dimension


class Farad(Unit):
    dimension: Dimension = Coulomb().dimension / Volt().dimension


class Pascal(Unit):
    dimension: Dimension = Newton().dimension / (Meter().dimension ** 2)



# -- display tokens (generic core prints through these; registering here is
#    application-level sugar, core stays unit-agnostic) ----------------------
for _token, _unit in {
    "m": Meter(), "kg": Kilogram(), "s": Second(),
    "m/s": MeterPerSecond(), "m/s^2": MeterPerSecondSquared(),
    "N": Newton(), "J": Joule(), "kg m/s": KilogramMeterPerSecond(),
    "km": Kilometer(),
    "USD": Dollar(),
    "W": Watt(), "Hz": Hertz(), "C": Coulomb(), "V": Volt(),
    "ohm": Ohm(), "T": Tesla(), "Wb": Weber(), "F": Farad(),
    "Pa": Pascal(),
}.items():
    register_unit_token(_token, _unit)
    register_unit_display(_unit, _token)


SI_SYSTEM = UnitSystem(name="si", base_units={
    Meter().dimension: Meter(),
    Kilogram().dimension: Kilogram(),
    Second().dimension: Second(),
    Ampere().dimension: Ampere(),
    Kelvin().dimension: Kelvin(),
    Mole().dimension: Mole(),
    Candela().dimension: Candela(),
})

