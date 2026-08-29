import unittest
from calculator import add, divide

class TestCalculator(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(3, 4), 7)

    def test_divide(self):
        self.assertEqual(divide(10, 2), 5)

if __name__ == '__main__':
    unittest.main()
