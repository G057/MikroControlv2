import unittest
from unittest.mock import patch

from app.core import crypto


class CryptoRotationTests(unittest.TestCase):
    def setUp(self):
        crypto._fernet_for.cache_clear()

    def tearDown(self):
        crypto._fernet_for.cache_clear()

    def test_previous_key_decrypts_during_rotation(self):
        previous = "previous-test-secret"
        current = "current-test-secret"
        stored = "enc:" + crypto._fernet_for(previous).encrypt(b"router-password").decode("utf-8")

        settings = type("Settings", (), {"SECRET_KEY": current, "SECRET_KEY_PREVIOUS": previous})()
        with patch("app.core.config.get_settings", return_value=settings):
            self.assertEqual(crypto.decrypt_secret(stored), "router-password")
            with self.assertRaises(Exception):
                crypto.decrypt_secret_with_current_key(stored)
