.PHONY: dev test lint tree

dev:
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -q

lint:
	ruff check .

tree:
	find . -maxdepth 3 -type f | sort
