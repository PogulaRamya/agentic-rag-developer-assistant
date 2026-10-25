.PHONY: test serve candidates
test:
	python -m pytest -q
serve:
	uvicorn app.main:app --host 127.0.0.1 --port 8000
candidates:
	python evaluation/validate_set.py evaluation/candidates.jsonl
