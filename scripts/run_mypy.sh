#!/bin/bash

# This runs mypy's static type checker on parts of Captum supporting type
# hints.

# TODO: Fix type issues with insights and add mypy checks here.
mypy -p captum.attr --ignore-missing-imports
mypy -p tests --ignore-missing-imports