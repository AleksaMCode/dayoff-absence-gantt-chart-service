import json
import unittest
from unittest.mock import Mock, patch

from microsoft.teams.utils import publish_to_channel, send_webhook_message


class TestTeamsUtils(unittest.TestCase):
    @patch("microsoft.teams.utils.logger.info")
    @patch("microsoft.teams.utils.requests.post")
    @patch("microsoft.teams.utils.os.getenv")
    def test_send_webhook_message_success(
        self,
        mock_getenv: Mock,
        mock_post: Mock,
        mock_logger_info: Mock,
    ) -> None:
        mock_getenv.return_value = "https://example.test/webhook"
        mock_post.return_value = Mock(status_code=200, text="ok")

        send_webhook_message("Hello Teams")

        mock_post.assert_called_once_with(
            "https://example.test/webhook",
            data=json.dumps({"text": "Hello Teams"}),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        mock_logger_info.assert_called_once_with("Slack webhook message sent to Teams.")

    @patch("microsoft.teams.utils.requests.post")
    @patch("microsoft.teams.utils.os.getenv")
    def test_send_webhook_message_uses_adaptive_card_when_image_url(
        self,
        mock_getenv: Mock,
        mock_post: Mock,
    ) -> None:
        mock_getenv.return_value = "https://example.test/webhook"
        mock_post.return_value = Mock(status_code=200, text="ok")

        send_webhook_message(
            "Hello Absences today",
            image_url="https://contoso.sharepoint.com/file.png",
        )

        expected_payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": "Hello Absences today",
                                "weight": "Bolder",
                                "wrap": True,
                            },
                            {
                                "type": "Image",
                                "url": "https://contoso.sharepoint.com/file.png",
                                "size": "Stretch",
                            },
                        ],
                        "actions": [
                            {
                                "type": "Action.OpenUrl",
                                "title": "Open image",
                                "url": "https://contoso.sharepoint.com/file.png",
                            }
                        ],
                    },
                }
            ],
        }
        mock_post.assert_called_once_with(
            "https://example.test/webhook",
            data=json.dumps(expected_payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

    @patch("microsoft.teams.utils.requests.post")
    @patch("microsoft.teams.utils.os.getenv")
    def test_send_webhook_message_raises_on_http_error(
        self,
        mock_getenv: Mock,
        mock_post: Mock,
    ) -> None:
        mock_getenv.return_value = "https://example.test/webhook"
        mock_post.return_value = Mock(status_code=500, text="test")

        with self.assertRaisesRegex(
            ValueError, "Request to Teams returned an error 500"
        ):
            send_webhook_message("Failure path")

    @patch("microsoft.teams.utils.send_webhook_message")
    @patch("microsoft.teams.utils.i18n.t")
    def test_publish_to_channel_default_message(
        self,
        mock_i18n_t: Mock,
        mock_send_webhook: Mock,
    ) -> None:
        translations = {
            "msg.hello": "Hello",
            "msg.absences": "Absences today",
        }
        mock_i18n_t.side_effect = lambda key: translations[key]

        publish_to_channel()

        mock_send_webhook.assert_called_once_with(
            "Hello Absences today", image_url=None
        )

    @patch("microsoft.teams.utils.send_webhook_message")
    @patch("microsoft.teams.utils.i18n.t")
    def test_publish_to_channel_with_image_url(
        self,
        mock_i18n_t: Mock,
        mock_send_webhook: Mock,
    ) -> None:
        translations = {
            "msg.hello": "Hello",
            "msg.absences": "Absences today",
        }
        mock_i18n_t.side_effect = lambda key: translations[key]

        publish_to_channel(image_url="https://contoso.sharepoint.com/file.png")

        mock_send_webhook.assert_called_once_with(
            "Hello Absences today", image_url="https://contoso.sharepoint.com/file.png"
        )

    @patch("microsoft.teams.utils.send_webhook_message")
    @patch("microsoft.teams.utils.i18n.t")
    def test_publish_to_channel_no_absences_message(
        self,
        mock_i18n_t: Mock,
        mock_send_webhook: Mock,
    ) -> None:
        translations = {
            "msg.hello": "Hello",
            "no-absences": "No absences this week",
        }
        mock_i18n_t.side_effect = lambda key: translations[key]

        publish_to_channel(no_absences=True)

        mock_send_webhook.assert_called_once_with(
            "Hello No absences this week", image_url=None
        )


if __name__ == "__main__":
    unittest.main()
