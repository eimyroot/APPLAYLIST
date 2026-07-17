.PHONY: dev test lint tree hygiene-audit hygiene-plan hygiene-verify

dev:
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -q

lint:
	ruff check .

tree:
	find . -maxdepth 3 -type f | sort

hygiene-audit:
	bash scripts/repo_hygiene.sh audit --stdout

hygiene-plan:
	bash scripts/repo_hygiene.sh quarantine

hygiene-verify:
	bash scripts/repo_hygiene.sh verify
