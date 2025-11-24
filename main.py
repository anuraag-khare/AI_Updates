import logging
from scraper import check_for_new_articles
from notifier import send_telegram_notification

def main(request):
    """
    Cloud Function entry point.
    Args:
        request (flask.Request): The request object.
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`.
    """
    logging.info("Cloud Function triggered.")
    
    # Default to 24 hours
    new_articles = check_for_new_articles(lookback_hours=24)
    
    if new_articles:
        count = len(new_articles)
        msg_lines = [f"Found {count} new article(s) on Anthropic Engineering Blog:"]
        for art in new_articles:
            msg_lines.append(f"- [{art['title']}]({art['url']}) ({art['date']})")
        
        message = "\n".join(msg_lines)
        logging.info(message)
        
        # Send notification
        send_telegram_notification(message)
        
        return f"Sent notification for {count} articles."
    else:
        msg = "No new articles found."
        logging.info(msg)
        return msg

if __name__ == "__main__":
    # Local test
    main(None)
