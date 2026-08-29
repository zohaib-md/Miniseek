def is_palindrome(text):
    import string
    text = text.lower()
    return text[::-1] == text
