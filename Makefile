PYTHON ?= .venv/bin/python
PYTHON_BOOTSTRAP ?= python3.12
BUNDLE_DIR ?= artifacts

.PHONY: bootstrap doctor lint type test security verify bundle dev tree

bootstrap:
	./scripts/bootstrap_local.sh "$(PYTHON_BOOTSTRAP)" ".venv"

doctor:
	APPLAYLIST_PYTHON="$(PYTHON)" ./scripts/doctor.sh

lint:
	APPLAYLIST_PYTHON="$(PYTHON)" ./scripts/lint_gate.sh

type:
	APPLAYLIST_PYTHON="$(PYTHON)" ./scripts/type_gate.sh

test:
	PYTHONDONTWRITEBYTECODE=1 "$(PYTHON)" -m pytest -q

security:
	APPLAYLIST_PYTHON="$(PYTHON)" ./scripts/security_gate.sh

verify:
	$(MAKE) doctor PYTHON="$(PYTHON)"
	$(MAKE) lint PYTHON="$(PYTHON)"
	$(MAKE) type PYTHON="$(PYTHON)"
	$(MAKE) test PYTHON="$(PYTHON)"
	$(MAKE) security PYTHON="$(PYTHON)"
	APPLAYLIST_PYTHON="$(PYTHON)" ./scripts/restore_smoke.sh

bundle:
	./scripts/bundle_local.sh "$(BUNDLE_DIR)"

dev:
	"$(PYTHON)" -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

tree:
	find . -maxdepth 3 -type f | sort
