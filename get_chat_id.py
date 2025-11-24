import requests
import os
from dotenv import load_dotenv

load_dotenv()
def get_chat_id():
    print("--- Get Telegram Chat ID ---")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Token is required.")
        return
    else:
        print(f"Token found: {token}")

    print(f"\nStep 1: Open your bot in Telegram.")
    print(f"Step 2: Send a message (e.g., 'hello') to your bot.")
    input("Step 3: Press Enter here AFTER you have sent the message...")

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if not data.get('ok'):
            print(f"Error from Telegram: {data.get('description')}")
            return

        results = data.get('result', [])
        if not results:
            print("\nNo updates found!")
            print("Troubleshooting:")
            print("1. Make sure you are messaging the correct bot.")
            print("2. Send another message to the bot.")
            print("3. Wait a few seconds and try running this script again.")
            return

        # Look for the most recent message
        last_update = results[-1]
        if 'message' in last_update:
            chat = last_update['message']['chat']
            chat_id = chat['id']
            username = chat.get('username', 'Unknown')
            first_name = chat.get('first_name', 'Unknown')
            
            print(f"\nSUCCESS!")
            print(f"Found conversation with: {first_name} (@{username})")
            print(f"--------------------------------------------------")
            print(f"YOUR CHAT ID: {chat_id}")
            print(f"--------------------------------------------------")
            print(f"Use this value for TELEGRAM_CHAT_ID.")
        else:
            print("Found an update, but it wasn't a standard message. Try sending text again.")

    except Exception as e:
        print(f"Error fetching updates: {e}")

if __name__ == "__main__":
    get_chat_id()
