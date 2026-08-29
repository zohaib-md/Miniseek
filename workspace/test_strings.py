import string_utils
import unittest

class TestStringMethods(unittest.TestCase):

    def test_is_palindrome(self):
        self.assertTrue(string_utils.is_palindrome('racecar'))
        self.assertTrue(string_utils.is_palindrome('Race Car'))
        self.assertFalse(string_utils.is_palindrome('Hello'))

    def test_is_palindrome_with_spaces(self):
        self.assertTrue(string_utils.is_palindrome('A man, a plan, a canal: Panama'))
        self.assertFalse(string_utils.is_palindrome('A man, a plan, a canal: Panama'))

    def test_is_palindrome_with_capitals(self):
        self.assertTrue(string_utils.is_palindrome('Madam, in Eden, I am Adam'))
        self.assertFalse(string_utils.is_palindrome('Madam, in Eden, I am Adam'))

if __name__ == '__main__':
    unittest.main()