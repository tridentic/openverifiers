"""OpenVerifiers — physics benchmark problem set (JEE/CBSE/HSC level).

Each entry: (id, problem_text, target_kind, expected_answer, explicit_overrides).

explicit_overrides supply givens that the deterministic extractor's vocabulary
cannot pull from prose (unit/register mismatch). This mirrors the README/ARCH §5
schema-forced extraction contract: the extractor is deterministic; ambiguous input
needs explicit grounding, and the engine still verifies everything itself.
"""

BENCH = [
    # --- kinematics: v = u + at ---------------------------------------------
    ("kin-01",
     "A car starts from rest and accelerates at 2 m/s^2 for 5 seconds. Find its final velocity.",
     "final_velocity", 10.0, {}),
    ("kin-02",
     "A body has an initial velocity of 10 m/s and accelerates at 2 m/s^2 for 4 seconds. Find its final velocity.",
     "final_velocity", 18.0, {}),
    ("kin-03",
     "A stone is dropped from rest. Find its velocity after 3 seconds. (free fall, g = 9.8 m/s^2)",
     "final_velocity", 29.4, {}),
    ("kin-19",
     "A ball is released from rest and falls freely under gravity. Find its velocity after 2 seconds.",
     "final_velocity", 19.6, {}),
    ("kin-15",
     "A body with initial velocity 2 m/s accelerates at 3 m/s^2 and reaches a final velocity of 14 m/s. Find the time taken.",
     "time", 4.0, {}),
    # --- kinematics: s = ut + 1/2 at^2 ---------------------------------------
    ("kin-04",
     "A car starts from rest and accelerates at 4 m/s^2. Find the distance after 5 seconds.",
     "displacement", 50.0, {}),
    ("kin-05",
     "A body has initial velocity 5 m/s and acceleration 2 m/s^2. Find the displacement after 10 seconds.",
     "displacement", 150.0, {}),
    ("kin-18",
     "A body starts from rest with uniform acceleration 2 m/s^2. Find the distance moved in 6 seconds.",
     "displacement", 36.0, {}),
    # --- kinematics: v^2 = u^2 + 2as -----------------------------------------
    ("kin-06",
     "A train starts from rest and accelerates uniformly at 1 m/s^2. Find its velocity after travelling 50 m.",
     "final_velocity", 10.0, {}),
    ("kin-13",
     "A body with initial velocity 3 m/s accelerates at 2 m/s^2 over 4 m. Find its final velocity.",
     "final_velocity", 5.0, {}),
    ("kin-14",
     "A body is dropped from rest and falls 4.9 m under gravity (g = 9.8 m/s^2). Find its final velocity.",
     "final_velocity", 9.8, {}),
    # --- kinematics: s = (u+v)/2 * t ------------------------------------------
    ("kin-08c",
     "A particle moving with initial velocity 10 m/s reaches a final velocity 30 m/s in 5 seconds. Find the distance travelled.",
     "displacement", 100.0, {}),
    ("kin-20",
     "A train moving with uniform velocity 40 m/s travels for 2 seconds. Find the distance covered.",
     "displacement", 80.0, {"initial_velocity": 40}),
    # --- dynamics: F = ma, a = F/m, m = F/a -----------------------------------
    ("dyn-08",
     "A mass of 10 kg is accelerated at 5 m/s^2. Find the force required.",
     "force", 50.0, {}),
    ("dyn-09",
     "A force of 20 N acts on a body of mass 5 kg. Find the acceleration.",
     "acceleration", 4.0, {}),
    ("dyn-10",
     "A force of 100 N acts on a mass of 20 kg. Find the acceleration produced.",
     "acceleration", 5.0, {}),
    ("dyn-17",
     "A force of 12 N produces an acceleration of 3 m/s^2. Find the mass of the body.",
     "mass", 4.0, {}),
    # --- energy/work -----------------------------------------------------------
    ("en-11",
     "A force of 10 N moves a body through 5 m. Find the work done.",
     "work", 50.0, {}),
    ("en-12",
     "A body of mass 2 kg moves with a velocity of 3 m/s. Find its kinetic energy.",
     "kinetic_energy", 9.0, {}),
    ("en-16",
     "Find the kinetic energy of a body of mass 4 kg moving at 5 m/s.",
     "kinetic_energy", 50.0, {}),
]

# assertions
assert len(BENCH) == 20, f"expected 20 problems, got {len(BENCH)}"