# Documentation targets only. The Masterbook: docs/masterbook/ (see Appendix K).
PY ?= .venv/bin/python

.PHONY: masterbook masterbook-accept

masterbook:
	$(PY) scripts/build_masterbook.py

masterbook-accept:
	$(PY) scripts/build_masterbook.py --accept
