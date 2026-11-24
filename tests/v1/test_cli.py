"""The `ov` command: every subcommand answers --help, and `ov FILE.ov` runs the file
(the founding brief's `ov program.ov --verbose`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openverifiers.cli import COMMANDS, main

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("cmd", sorted(COMMANDS))
def test_every_command_answers_help(cmd: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([cmd, "--help"]) == 0
    assert capsys.readouterr().out.strip()


def test_bare_file_runs_like_ov_run(capsys: pytest.CaptureFixture[str]) -> None:
    q11 = str(ROOT / "examples/chem/q11.ov")
    assert main([q11, "--verbose"]) == main(["run", q11, "--verbose"]) == 0
    out = capsys.readouterr().out
    assert out.count("FIND ?A, ?C, ?D") == 2


def test_usage_and_unknown_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2 and main(["--help"]) == 0 and main(["frobnicate"]) == 2
