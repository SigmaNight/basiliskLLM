"""Unit tests runner for the project.

This script automatically discovers and runs all unit tests located in the 'tests' directory.
"""

import unittest

test_loader = unittest.TestLoader()
test_suite = test_loader.discover('tests')

test_runner = unittest.TextTestRunner()
test_runner.run(test_suite)
