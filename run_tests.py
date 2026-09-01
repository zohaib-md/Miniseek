import os
import sys
import unittest

if __name__ == "__main__":
    os.environ["PYTHONUNBUFFERED"] = "1"
    loader = unittest.TestLoader()
    suite = loader.discover("tests")
    print(f"Discovered {suite.countTestCases()} test cases across test suites.")
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    print(f"\n=======================================================")
    print(f"Total Tests Run: {result.testsRun}")
    print(f"Errors: {len(result.errors)}, Failures: {len(result.failures)}")
    print(f"Overall Status: {'SUCCESS (ALL PASS)' if result.wasSuccessful() else 'FAILED'}")
    print(f"=======================================================\n")
    sys.exit(0 if result.wasSuccessful() else 1)
