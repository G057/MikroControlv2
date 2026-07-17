import unittest
from unittest.mock import patch

from jose import jwt

from app.core.security import create_access_token


class SessionTokenTests(unittest.TestCase):
    def test_never_expiring_token_has_no_exp_claim(self):
        settings = type("Settings", (), {
            "SECRET_KEY": "test-secret",
            "ALGORITHM": "HS256",
            "ACCESS_TOKEN_EXPIRE_MINUTES": 480,
        })()
        with patch("app.core.security.settings", settings):
            token = create_access_token({"sub": "1"}, never_expires=True)
        payload = jwt.decode(token, "test-secret", algorithms=["HS256"], options={"verify_exp": False})
        self.assertNotIn("exp", payload)
