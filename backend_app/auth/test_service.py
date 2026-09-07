import unittest
from unittest.mock import MagicMock, patch

from auth.router import RegisterRequest, register
from auth.service import create_user


class UserRegistrationRoleTest(unittest.TestCase):
    @patch("auth.service.bcrypt.hashpw", return_value=b"hashed-password")
    @patch("auth.service.bcrypt.gensalt", return_value=b"salt")
    @patch("auth.service.engine")
    def test_create_user_inserts_local_user_role(self, mock_engine, _mock_salt, _mock_hash):
        connection = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = connection

        create_user("new-user", "password", "new-user@example.com")

        params = connection.execute.call_args.args[1]
        self.assertEqual(params["role"], "LocalUser")

    @patch("auth.router.create_access_token", return_value="token")
    @patch("auth.router.create_user")
    @patch("auth.router.user_exists", return_value=False)
    def test_register_response_uses_local_user_role(
        self, _mock_exists, _mock_create_user, _mock_token
    ):
        result = register(
            RegisterRequest(
                username="new-user",
                password="password",
                email="new-user@example.com",
            )
        )

        self.assertEqual(result["role"], "LocalUser")


if __name__ == "__main__":
    unittest.main()
