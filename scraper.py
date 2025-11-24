import requests
from bs4 import BeautifulSoup
from dateutil import parser
from datetime import datetime, timedelta, timezone
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

URL = "https://www.anthropic.com/engineering"

def check_for_new_articles(lookback_hours=24):
    """
    Scrapes the Anthropic Engineering blog and checks for articles published
    within the last `lookback_hours`.
    """
    logging.info(f"Checking for articles published in the last {lookback_hours} hours...")
    
    try:
        response = requests.get(URL, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Failed to fetch {URL}: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Selector based on inspection: a tag with class containing 'ArticleList_cardLink'
    # Note: Class names might be hashed (e.g., ArticleList_cardLink__2dk5j), so we use a partial match if possible
    # or just the specific class if it seems stable enough. 
    # Using a partial match on class is safer in BS4: soup.select('a[class*="ArticleList_cardLink"]')
    articles = soup.select('a[class*="ArticleList_cardLink"]')
    
    new_articles = []
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=lookback_hours)

    logging.info(f"Found {len(articles)} total articles on the page.")

    for article in articles:
        try:
            # Title is in h3
            title_tag = article.find('h3')
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)

            # Date is in the div immediately following the h3
            # Structure: h3 + div
            date_tag = title_tag.find_next_sibling('div')
            if not date_tag:
                continue
            date_str = date_tag.get_text(strip=True)
            
            # Parse date. Anthropic blog dates are usually like "Nov 24, 2025"
            # parser.parse is robust enough to handle this.
            pub_date = parser.parse(date_str)
            
            # Ensure pub_date is timezone-aware for comparison (assuming UTC if not specified, 
            # though often these are just dates. We'll treat them as UTC dates at 00:00)
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)

            link = article.get('href')
            if link and not link.startswith('http'):
                link = f"https://www.anthropic.com{link}"

            if pub_date >= cutoff_time:
                logging.info(f"New article found: {title} ({date_str})")
                new_articles.append({
                    'title': title,
                    'date': date_str,
                    'url': link,
                    'timestamp': pub_date.isoformat()
                })
            else:
                logging.debug(f"Skipping old article: {title} ({date_str})")

        except Exception as e:
            logging.warning(f"Error parsing an article: {e}")
            continue

    return new_articles

if __name__ == "__main__":
    # For local testing, look back 30 days to ensure we find something if the blog hasn't updated today
    found = check_for_new_articles(lookback_hours=24 * 30)
    print(f"Found {len(found)} new articles.")
    for art in found:
        print(f"- {art['title']} ({art['url']})")
