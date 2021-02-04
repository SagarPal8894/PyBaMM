#
# Test no Li plating submodel
#

import pybamm
import tests
import unittest


class TestNoPlating(unittest.TestCase):
    def test_public_functions(self):
        param = pybamm.LithiumIonParameters()
        variables = {}
        submodel = pybamm.lithium_plating.NoPlating(param, "Negative")
        std_tests = tests.StandardSubModelTests(submodel, variables)
        std_tests.test_all()
        submodel = pybamm.lithium_plating.NoPlating(param, "Positive")
        std_tests = tests.StandardSubModelTests(submodel, variables)
        std_tests.test_all()


if __name__ == "__main__":
    print("Add -v for more debug output")
    import sys

    if "-v" in sys.argv:
        debug = True
    pybamm.settings.debug_mode = True
    unittest.main()
