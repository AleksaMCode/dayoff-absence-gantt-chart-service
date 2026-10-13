#!/bin/bash

python -m coverage run -m unittest discover -s tests -p "test_*.py"
python -m coverage report -m