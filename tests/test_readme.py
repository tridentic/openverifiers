"""The README's domain-pack example must run and stay under 20 lines."""

from __future__ import annotations

import re
from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_domain_pack_example_runs() -> None:
    text = README.read_text()
    m = re.search(r"<!-- readme-example -->\n```python\n(.*?)```", text, re.S)
    assert m, "example block missing"
    code = m.group(1)
    assert len(code.strip().splitlines()) < 20
    exec(compile(code, "README.md", "exec"), {})
