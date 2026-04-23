import json
import os
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

from i18n.loader import i18n
from logger.utils import get_logger

load_dotenv()
logger = get_logger(__name__)


# Incoming Webhook is to be retired in Teams - https://techcommunity.microsoft.com/discussions/teamsdeveloper/simple-workflow-to-replace-teams-incoming-webhooks/4225270
# TODO: We'll cross that bridge once needed.
# Probably need to switch eventually to https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/bots-filesv4?tabs=csharp1%2Ccsharp
def send_webhook_message(message: str, image_url: Optional[str] = None):
    """
    Sends a message to a Slack like app (Teams) via webhook.
    """
    payload = _build_webhook_payload(message=message, image_url=image_url)

    response = requests.post(
        os.getenv("TEAMS_WEBHOOK_URL"),
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
        timeout=10,
    )

    if response.status_code != 200:
        error_msg = f"Request to Teams returned an error {response.status_code}, the response is:\n{response.text}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    else:
        logger.info("Slack webhook message sent to Teams.")


def publish_to_channel(no_absences: bool = False, image_url: Optional[str] = None):
    logger.info("Publishing to teams channel")
    if not no_absences:
        msg = f"{i18n.t('msg.hello')} {i18n.t('msg.absences')}"
    else:
        msg = f"{i18n.t('msg.hello')} {i18n.t('no-absences')}"

    send_webhook_message(msg, image_url=image_url)


def _build_webhook_payload(
    message: str, image_url: Optional[str] = None
) -> Dict[str, Any]:
    if not image_url:
        return {"text": message}

    return {
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
                            "text": message,
                            "weight": "Bolder",
                            "wrap": True,
                        },
                        {"type": "Image", "url": image_url, "size": "Stretch"},
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "Open image",
                            "url": image_url,
                        }
                    ],
                },
            }
        ],
    }
