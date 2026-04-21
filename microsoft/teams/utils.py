import json
import os

import requests
from dotenv import load_dotenv

from i18n.loader import i18n
from logger import get_logger

load_dotenv()
logger = get_logger(__name__)


# Incoming Webhook is to be retired in Teams - https://techcommunity.microsoft.com/discussions/teamsdeveloper/simple-workflow-to-replace-teams-incoming-webhooks/4225270
# We'll cross that bridge once needed.
# Probably need to switch eventually to https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/bots-filesv4?tabs=csharp1%2Ccsharp
def send_webhook_message(message: str):
    """
    Sends a message to a Slack like app (Teams) via webhook.
    """
    payload = {"text": message}

    response = requests.post(
        os.getenv("TEAMS_WEBHOOK_URL"),
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
        timeout=10,
    )

    if response.status_code != 200:
        raise ValueError(
            f"Request to Teams returned an error {response.status_code}, the response is:\n{response.text}"
        )
    else:
        logger.info("Slack webhook message sent to Teams.")


def publish_to_channel():
    logger.info("Publishing to teams channel")
    msg = f"{i18n.t("msg.hello")} {i18n.t("msg.start")}"
    send_webhook_message(msg)
