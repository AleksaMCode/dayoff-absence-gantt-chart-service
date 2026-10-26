PYTHON ?= python

.PHONY: run test test-with-coverage coverage-badge fmt

run:
	$(PYTHON) -m main

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

test-with-coverage:
	$(PYTHON) -m coverage run -m unittest discover -s tests -p "test_*.py" -v
	$(PYTHON) -m coverage report -m

coverage-badge:
	$(PYTHON) -m coverage run -m unittest discover -s tests -p "test_*.py" -v
	$(PYTHON) -m coverage report -m > coverage.txt
	$(PYTHON) scripts/coverage_generator.py

fmt:
	$(PYTHON) -m black .
	$(PYTHON) -m isort . --profile black
