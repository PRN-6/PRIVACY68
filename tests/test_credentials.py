import unittest
from unittest.mock import Mock, patch

from utils import credentials


class TestCredentials(unittest.TestCase):
    def test_get_github_token_env_fallback(self):
        with patch.object(credentials, "_credential_manager", side_effect=Exception("No win32cred")), \
             patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_mock_token_123"}):
            token = credentials.get_github_token()
            self.assertEqual(token, "ghp_mock_token_123")

    def test_set_and_delete_github_token(self):
        with patch.object(credentials, "_credential_manager", side_effect=Exception("No win32cred")), \
             patch("config.update_dotenv_var") as mock_dotenv:
            success = credentials.set_github_token("ghp_test_token_456")
            self.assertTrue(success)
            mock_dotenv.assert_called()

            del_success = credentials.delete_github_token()
            self.assertTrue(del_success)

    @patch("requests.get")
    def test_get_github_connection_status(self, mock_get):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"login": "octocat", "name": "The Octocat"}
        mock_get.return_value = mock_resp

        with patch.object(credentials, "get_github_token", return_value="ghp_valid"):
            status = credentials.get_github_connection_status()
            self.assertTrue(status["connected"])
            self.assertEqual(status["login"], "octocat")


if __name__ == "__main__":
    unittest.main()

