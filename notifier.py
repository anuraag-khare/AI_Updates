import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

def send_telegram_notification(message):
    """
    Sends a message to a Telegram chat using a Bot.
    Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        logging.warning("Telegram credentials not found. Skipping notification.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Telegram notification sent successfully.")
        return True
    except requests.RequestException as e:
        logging.error(f"Failed to send Telegram notification: {e}")
        return False
