import unittest

from fastapi import HTTPException

from app.core.user_ops import validate_password_strength


class PasswordPolicyTests(unittest.TestCase):
    def test_accepts_long_mixed_password(self):
        validate_password_strength("SecurePass123")

    def test_rejects_password_without_required_character_classes(self):
        for password in ("alllowercase12", "ALLUPPERCASE12", "NoDigitsHereXX"):
            with self.assertRaises(HTTPException):
                validate_password_strength(password)


if __name__ == "__main__":
    unittest.main()
