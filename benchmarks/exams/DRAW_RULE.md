# How exam problems are drawn (fixed before any paper is read)

The CTO's anti-cherry-picking rule: the list is drawn mechanically, committed,
and only then formalized. The library is then built for exactly what the
drawn problems need.

**Sources.**
- **Originals** (papers, answer keys, mark schemes) live in the gitignored
  `private/sources/` and are never committed.
- **The repo gets** source references, paraphrases and gold answers only.

**JEE Advanced.**
- **Papers.** Take Paper 1 and Paper 2 of the most recent year whose official
  final answer key is published on the official JEE Advanced site.
- **Numbering.** For each subject (physics, chemistry, mathematics), number
  the questions in official order: all of Paper 1, then all of Paper 2.
  Let n be that count.
- **Step.** N = floor(n / 10). Take the questions at positions 1, 1 + N,
  1 + 2N, and so on.
- **Skips.**
  - Skip a picked question **only** if:
    - it depends on a diagram, a graph or a figure whose content cannot be
      stated in words; or
    - the official key marks it dropped, or gives marks to all.
  - On a skip, take the next question in order instead.
  - Record every skip, with its reason.
- **Count.** Stop at 10 per subject. If the year runs out, continue with the
  previous year's papers by the same rule.

**HSC and A-level** (from the folder Arjo provides):
- **Papers.** Order the provided papers by year (newest first), then by paper
  number.
- **Rule.** Apply the same rule per subject, with 15 per subject for HSC and
  10 for A-level.
- **Questions.** A question with parts is one question. Its first
  self-contained part that asks for a value or a verdict is the one drawn.

**Gold.**
- **JEE and A-level:** the official answer key or mark scheme
  (`gold_provenance: official_key`).
- **HSC:** two independent solutions (`gold_provenance: dual_independent`).
  1. Arjo, by hand.
  2. A separate Claude session with no repo access and no OV.

  When they agree, that is gold. When they disagree, Arjo resolves it with a
  teacher.
- **Gold is committed before OV runs on the problem** (the gold gate).
