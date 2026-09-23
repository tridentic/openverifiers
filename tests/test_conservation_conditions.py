from openverifiers import (ConditionController, Quantity)

from openverifiers.domains.units_si import (Joule, KilogramMeterPerSecond)
"""Task 2 — momentum and energy conservation as conditions on a
ConditionController, compared with the shared 1e-6 tolerance.

Intent mapping from the legacy derivation fixtures:
  deriv-mom-01      -> test_momentum_balance_holds
  deriv-mom-broken  -> test_momentum_dropped_term_fails
  deriv-en-broken   -> test_energy_dropped_term_fails
  deriv-unknown     -> test_unknown_member_is_inapplicable (momentum variant)
  Task 5 intent     -> test_tolerance_matches_rest (sums differ by < 1e-6 pass)
"""

from openverifiers.domains.conservation import (ConservationCheck,
                                                build_conservation_controller)
from openverifiers.facts import Quantity
from openverifiers.domains.units_si import (KilogramMeterPerSecond, Joule)
from openverifiers.domains.coding import PASS, FAIL, INAPPLICABLE

P_MOM = KilogramMeterPerSecond
P_ENG = Joule


def _q(value, unit, status="truth", fid="?"):
    return Quantity(value=float(value), unit=unit, status=status, id=fid)


CTRL = build_conservation_controller()


def _check(**kw):
    chk = ConservationCheck(**kw)
    verdicts = [v for (_n, v, _r) in CTRL.check((), chk)]
    return verdicts[0] if verdicts else None


def test_momentum_balance_holds():
    chk = ConservationCheck(seq=1, law="momentum",
                            before=(_q(6, P_MOM()), _q(0, P_MOM())),
                            after=(_q(4, P_MOM()), _q(2, P_MOM())))
    verdict, reason = CTRL.check((), chk)[0][1:]
    assert verdict == PASS
    assert "holds" in reason


def test_momentum_dropped_term_fails():
    chk = ConservationCheck(seq=1, law="momentum",
                            before=(_q(6, P_MOM()), _q(0, P_MOM())),
                            after=(_q(4, P_MOM()), _q(1, P_MOM())))
    verdict, reason = CTRL.check((), chk)[0][1:]
    assert verdict == FAIL
    assert "violated" in reason


def test_energy_dropped_term_fails():
    chk = ConservationCheck(seq=1, law="energy",
                            before=(_q(100, P_ENG()), _q(50, P_ENG())),
                            after=(_q(120, P_ENG()),))
    verdict, reason = CTRL.check((), chk)[0][1:]
    assert verdict == FAIL
    assert "violated" in reason


def test_unknown_member_is_inapplicable_never_guessed():
    chk = ConservationCheck(seq=1, law="momentum",
                            before=(_q(6, P_MOM()),
                                    _q(0, P_MOM(), status="unknown", fid="p2")),
                            after=(_q(4, P_MOM()), _q(2, P_MOM())))
    verdict, reason = CTRL.check((), chk)[0][1:]
    assert verdict == INAPPLICABLE
    assert "p2" in reason and "inapplicable" in reason


def test_wrong_dimension_member_fails_on_dimension():
    chk = ConservationCheck(seq=1, law="momentum",
                            before=(_q(6, P_MOM()), _q(3, P_ENG())),  # J in momentum
                            after=(_q(4, P_MOM()), _q(2, P_MOM())))
    verdict, reason = CTRL.check((), chk)[0][1:]
    assert verdict == FAIL
    assert "dimension mismatch" in reason


def test_tolerance_matches_rest_of_codebase():
    # sums that differ by 1e-9 (well inside 1e-6 relative) MUST pass — this
    # is the task-5 fix: conservation no longer uses exact ==.
    chk = ConservationCheck(seq=1, law="momentum",
                            before=(_q(1.0, P_MOM()),),
                            after=(_q(1.0 - 1e-9, P_MOM()),))
    verdict, _reason = CTRL.check((), chk)[0][1:]
    assert verdict == PASS


def test_conservation_controller_is_domain_agnostic():
    # The controller class itself must not know "momentum": only instance
    # content does. The class only binds named predicates to verdicts.
    import inspect
    from openverifiers.controllers import ConditionController
    src = inspect.getsource(ConditionController.__check_trace) if False else \
          inspect.getsource(ConditionController)
    assert "momentum" not in src and "energy" not in src