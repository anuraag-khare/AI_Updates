import os
import logging
from notifier import send_telegram_notification
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_notification():
    print("Testing Telegram Notification...")
    
    # Check if env vars are set
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("WARNING: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        print("Skipping actual API call. Logic verification only.")
        
        # Mocking the behavior for verification
        if not token:
            print("- Missing TELEGRAM_BOT_TOKEN")
        if not chat_id:
            print("- Missing TELEGRAM_CHAT_ID")
            
        print("Logic check: `notifier.py` handles missing credentials gracefully.")
        result = send_telegram_notification("Test message")
        if result is False:
            print("SUCCESS: Function returned False as expected with missing credentials.")
        else:
            print("FAILURE: Function should have returned False.")
    else:
        print("Credentials found. Attempting to send message...")
        result = send_telegram_notification("Test message from Anthropic Scraper")
        if result:
            print("SUCCESS: Notification sent!")
        else:
            print("FAILURE: Notification failed.")

if __name__ == "__main__":
    test_notification()
