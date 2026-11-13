import io
import unittest
from unittest.mock import MagicMock, Mock, patch

from plugins.telegram_plugin import TelegramPlugin


class TestTelegramPlugin(unittest.TestCase):
    def setUp(self):
        self.plugin = TelegramPlugin()
        self.plugin._bot_token = "123456:TEST_TOKEN"
        self.plugin._allowed_chat_id = "987654321"

    def tearDown(self):
        if self.plugin.is_bot_running():
            self.plugin.stop_bot()

    def test_metadata_and_initialization(self):
        self.assertEqual(self.plugin.id, "telegram")
        self.assertEqual(self.plugin.name, "Telegram Remote Gateway")
        self.assertEqual(self.plugin.category, "Communication")
        self.assertTrue(self.plugin.is_builtin)
        self.assertTrue(self.plugin.is_enabled)

    def test_token_and_chat_id_storage(self):
        with patch("plugins.telegram_plugin.profile_manager.set") as mock_set, patch("config.update_dotenv_var"):
            self.plugin.set_bot_token("NEW_TOKEN_ABC")
            mock_set.assert_called_with("telegram_bot_token", "NEW_TOKEN_ABC")
            self.assertEqual(self.plugin.get_bot_token(), "NEW_TOKEN_ABC")

            self.plugin.set_allowed_chat_id("11223344")
            mock_set.assert_called_with("telegram_allowed_chat_id", "11223344")
            self.assertEqual(self.plugin.get_allowed_chat_id(), "11223344")

    @patch("requests.get")
    def test_get_me_success(self, mock_get):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ok": True,
            "result": {"id": 123456, "is_bot": True, "username": "privacy68_tele_bot"}
        }
        mock_get.return_value = mock_resp

        ok, info = self.plugin.get_me()
        self.assertTrue(ok)
        self.assertEqual(self.plugin.bot_username, "privacy68_tele_bot")
        self.assertEqual(info["username"], "privacy68_tele_bot")

    @patch("requests.post")
    def test_send_message_success(self, mock_post):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": {"message_id": 1}}
        mock_post.return_value = mock_resp

        success = self.plugin.send_message("Hello from test", chat_id="987654321")
        self.assertTrue(success)
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs["json"]["chat_id"], "987654321")
        self.assertEqual(call_kwargs["json"]["text"], "Hello from test")

    @patch("requests.post")
    def test_send_photo_success(self, mock_post):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": {"message_id": 2}}
        mock_post.return_value = mock_resp

        dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        success = self.plugin.send_photo(dummy_png, caption="Test Screen", chat_id="987654321")
        self.assertTrue(success)
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args[1]["data"]["caption"], "Test Screen")

    def test_send_test_message_requires_allowed_chat(self):
        self.plugin._allowed_chat_id = ""
        with patch.object(self.plugin, "get_allowed_chat_id", return_value=""):
            ok, msg = self.plugin.send_test_message()
            self.assertFalse(ok)
            self.assertIn("No allowed chat ID", msg)

    @patch("server.remote_server.get_auth_token", return_value="PIN123")
    def test_unpaired_flow_and_pin_authorization(self, mock_token):
        self.plugin._allowed_chat_id = ""
        with patch.object(self.plugin, "get_allowed_chat_id", return_value=""):
            with patch.object(self.plugin, "send_message") as mock_send:
                # 1. /start command sent by unauthenticated user
                update_start = {
                    "message": {
                        "chat": {"id": "555666"},
                        "from": {"id": "555666"},
                        "text": "/start"
                    }
                }
                self.plugin._handle_update(update_start)
                mock_send.assert_called()
                self.assertIn("Welcome", mock_send.call_args[0][0])

                # 2. Wrong PIN sent
                update_wrong_pin = {
                    "message": {
                        "chat": {"id": "555666"},
                        "from": {"id": "555666"},
                        "text": "/pair WRONGPIN"
                    }
                }
                self.plugin._handle_update(update_wrong_pin)
                self.assertIn("Invalid pairing PIN", mock_send.call_args[0][0])

                # 3. Correct PIN sent
                update_correct_pin = {
                    "message": {
                        "chat": {"id": "555666"},
                        "from": {"id": "555666"},
                        "text": "/pair PIN123"
                    }
                }
                with patch.object(self.plugin, "set_allowed_chat_id") as mock_set_chat:
                    self.plugin._handle_update(update_correct_pin)
                    mock_set_chat.assert_called_once_with("555666")
                    self.assertIn("Successfully paired", mock_send.call_args[0][0])

    def test_unauthorized_chat_is_rejected_when_paired(self):
        self.plugin._allowed_chat_id = "987654321"
        with patch.object(self.plugin, "send_message") as mock_send:
            update = {
                "message": {
                    "chat": {"id": "999999"},
                    "from": {"id": "999999"},
                    "text": "open chrome"
                }
            }
            self.plugin._handle_update(update)
            mock_send.assert_called_with("🔒 Access denied. This PRIVACY68 assistant is paired to another user.", chat_id="999999")

    @patch("actions.executor.execute_system_command_detailed")
    def test_authorized_command_execution(self, mock_exec):
        mock_exec.return_value = {"success": True, "message": "Opened Chrome."}
        with patch.object(self.plugin, "send_message") as mock_send:
            update = {
                "message": {
                    "chat": {"id": "987654321"},
                    "from": {"id": "987654321"},
                    "text": "open chrome"
                }
            }
            self.plugin._handle_update(update)
            mock_exec.assert_called_once_with("open chrome")
            self.assertTrue(any("Opened Chrome." in call[0][0] for call in mock_send.call_args_list))

    @patch("PIL.ImageGrab.grab")
    def test_screenshot_command(self, mock_grab):
        mock_img = Mock()
        mock_img.save.side_effect = lambda buf, format: buf.write(b"PNGDATA")
        mock_grab.return_value = mock_img

        with patch.object(self.plugin, "send_photo") as mock_photo:
            update = {
                "message": {
                    "chat": {"id": "987654321"},
                    "from": {"id": "987654321"},
                    "text": "/screenshot"
                }
            }
            self.plugin._handle_update(update)
            mock_photo.assert_called_once()
            self.assertEqual(mock_photo.call_args[0][0], b"PNGDATA")

    @patch("actions.executor.execute_system_command_detailed")
    def test_voice_note_transcription_and_execution(self, mock_exec):
        mock_exec.return_value = {"success": True, "message": "Volume set to 50%"}

        with patch.object(self.plugin, "_transcribe_telegram_voice", return_value="set volume to 50 percent"):
            with patch.object(self.plugin, "send_message") as mock_send:
                update = {
                    "message": {
                        "chat": {"id": "987654321"},
                        "from": {"id": "987654321"},
                        "voice": {"file_id": "VOICE_FILE_123"}
                    }
                }
                self.plugin._handle_update(update)
                mock_exec.assert_called_once_with("set volume to 50 percent")
                self.assertTrue(any("Volume set to 50%" in call[0][0] for call in mock_send.call_args_list))

    def test_status_command(self):
        with patch.object(self.plugin, "send_message") as mock_send:
            update = {
                "message": {
                    "chat": {"id": "987654321"},
                    "from": {"id": "987654321"},
                    "text": "/status"
                }
            }
            self.plugin._handle_update(update)
            mock_send.assert_called_once()
            msg = mock_send.call_args[0][0]
            self.assertIn("PRIVACY68 PC Status", msg)
            self.assertIn("CPU Load", msg)
            self.assertIn("Gateway: 🟢 Online", msg)

    def test_bot_start_stop_lifecycle(self):
        with patch.object(self.plugin, "get_me", return_value=(True, {"username": "test_bot"})):
            with patch("requests.get") as mock_get:
                # Mock getUpdates to simulate long polling
                mock_resp = Mock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"ok": True, "result": []}
                mock_get.return_value = mock_resp

                ok, msg = self.plugin.start_bot()
                self.assertTrue(ok)
                self.assertTrue(self.plugin.is_bot_running())

                # Double start
                ok2, msg2 = self.plugin.start_bot()
                self.assertTrue(ok2)
                self.assertIn("already running", msg2)

                # Stop
                ok_stop, msg_stop = self.plugin.stop_bot()
                self.assertTrue(ok_stop)
                self.assertFalse(self.plugin.is_bot_running())

    def test_plugin_execute_actions(self):
        with patch("webbrowser.open", return_value=True) as mock_open:
            self.assertTrue(self.plugin.execute("open"))
            mock_open.assert_called_once_with("https://web.telegram.org")

        with patch.object(self.plugin, "send_message", return_value=True) as mock_send:
            self.assertTrue(self.plugin.execute("send_message", message="Test alert"))
            mock_send.assert_called_once_with("Test alert")


if __name__ == "__main__":
    unittest.main()

