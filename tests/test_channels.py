import unittest
from unittest.mock import Mock, patch

from channels.telegram import TelegramChannel, telegram_channel


class TestChannels(unittest.TestCase):
    def test_telegram_channel_initialization(self):
        channel = TelegramChannel()
        self.assertEqual(channel.id, "telegram")
        self.assertEqual(channel.name, "Telegram Remote Gateway")
        self.assertTrue(channel.is_enabled)

    def test_token_and_chat_id_persistence(self):
        channel = TelegramChannel()
        with patch("utils.profile_manager.profile_manager.set") as mock_set, patch("config.update_dotenv_var"):
            channel.set_bot_token("TEST_CHAN_TOKEN")
            mock_set.assert_called_with("telegram_bot_token", "TEST_CHAN_TOKEN")
            self.assertEqual(channel.get_bot_token(), "TEST_CHAN_TOKEN")

            channel.set_allowed_chat_id("998877")
            mock_set.assert_called_with("telegram_allowed_chat_id", "998877")
            self.assertEqual(channel.get_allowed_chat_id(), "998877")

    @patch("requests.get")
    def test_telegram_get_me(self, mock_get):
        channel = TelegramChannel()
        channel._bot_token = "123:TOKEN"
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ok": True,
            "result": {"id": 123456, "is_bot": True, "username": "openclaw_bot"}
        }
        mock_get.return_value = mock_resp

        ok, info = channel.get_me()
        self.assertTrue(ok)
        self.assertEqual(channel.bot_username, "openclaw_bot")

    @patch("requests.post")
    def test_telegram_send_message(self, mock_post):
        channel = TelegramChannel()
        channel._bot_token = "123:TOKEN"
        channel._allowed_chat_id = "555"
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": {"message_id": 99}}
        mock_post.return_value = mock_resp

        success = channel.send_message("Test notification")
        self.assertTrue(success)
        mock_post.assert_called_once()

    def test_pairing_pin_get_and_set(self):
        channel = TelegramChannel()
        pin = channel.get_pairing_pin()
        self.assertTrue(len(pin) >= 6)
        channel.set_pairing_pin("SEC123")
        self.assertEqual(channel.get_pairing_pin(), "SEC123")

    @patch("requests.post")
    def test_pairing_flow_start_and_pair(self, mock_post):
        channel = TelegramChannel()
        channel._allowed_chat_id = ""
        channel.set_pairing_pin("PIN999")
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        mock_post.return_value = mock_resp

        # 1. /start command
        with patch.object(channel, "get_allowed_chat_id", return_value=""):
            with patch.object(channel, "get_bot_token", return_value="FAKE_TOKEN"):
                channel._handle_update({
                    "message": {
                        "chat": {"id": 12345},
                        "from": {"id": 12345},
                        "text": "/start"
                    }
                })
                self.assertTrue(mock_post.called)

                # 2. Invalid /pair PIN
                channel._handle_update({
                    "message": {
                        "chat": {"id": 12345},
                        "from": {"id": 12345},
                        "text": "/pair WRONGPIN"
                    }
                })

                # 3. Valid /pair PIN
                with patch.object(channel, "set_allowed_chat_id") as mock_set_allowed:
                    channel._handle_update({
                        "message": {
                            "chat": {"id": 12345},
                            "from": {"id": 12345},
                            "text": "/pair PIN999"
                        }
                    })
                    mock_set_allowed.assert_called_with("12345")


if __name__ == "__main__":
    unittest.main()

