import requests
from bs4 import BeautifulSoup
from dateutil import parser
from datetime import datetime, timedelta, timezone
import logging
import feedparser
import ssl
import xml.etree.ElementTree as ET

# Workaround for SSL certificate verify failed on some systems
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SOURCES = [
    {
        "name": "Anthropic Engineering",
        "type": "html",
        "url": "https://www.anthropic.com/engineering",
        "article_selector": 'a[class*="ArticleList_cardLink"]',
        "title_selector": "h3, h2",
        "date_selector": "h3 + div",
        "link_selector": None, # The article element itself is the link
        "base_url": "https://www.anthropic.com"
    },
    {
        "name": "Google Developers (AI)",
        "type": "feed",
        "url": "https://developers.googleblog.com/feeds/posts/default?alt=atom&category=AI",
        "sitemap_url": "https://developers.googleblog.com/sitemap.xml"
    }
]

def normalize_url(url):
    """Normalizes URL for comparison (removes query params and trailing slashes)."""
    if not url: return ""
    return url.split('?')[0].rstrip('/')

def fetch_sitemap_dates(sitemap_url):
    """Fetches sitemap and returns a dict of {normalized_url: date_str}."""
    logging.info(f"Fetching sitemap: {sitemap_url}")
    try:
        response = requests.get(sitemap_url, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        # Sitemaps use namespace http://www.sitemaps.org/schemas/sitemap/0.9
        ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        sitemap_dates = {}
        for url_tag in root.findall('s:url', ns):
            loc = url_tag.find('s:loc', ns).text
            lastmod_tag = url_tag.find('s:lastmod', ns)
            if loc and lastmod_tag is not None:
                sitemap_dates[normalize_url(loc)] = lastmod_tag.text
        
        logging.info(f"Loaded {len(sitemap_dates)} URLs from sitemap.")
        return sitemap_dates
    except Exception as e:
        logging.error(f"Failed to fetch/parse sitemap: {e}")
        return {}

def check_for_new_articles(lookback_hours=24):
    """
    Scrapes configured blogs and checks for articles published
    within the last `lookback_hours`.
    """
    logging.info(f"Checking for articles published in the last {lookback_hours} hours...")
    
    all_new_articles = []
    now = datetime.now(timezone.utc)
    # Calculate cutoff date (ignoring time)
    cutoff_date = (now - timedelta(hours=lookback_hours)).date()

    for source in SOURCES:
        logging.info(f"Checking {source['name']}...")
        
        if source.get('type') == 'feed':
            # Feed Parsing (RSS/Atom) using feedparser
            try:
                feed = feedparser.parse(source['url'])
                logging.info(f"Found {len(feed.entries)} entries in feed for {source['name']}.")
                
                # Lazy load sitemap if needed
                sitemap_dates = None
                if source.get('sitemap_url'):
                    # Only fetch if we encounter missing dates, or just fetch once?
                    # Fetching once per source is safer/simpler.
                    sitemap_dates = fetch_sitemap_dates(source['sitemap_url'])

                for entry in feed.entries:
                    title = entry.title
                    link = entry.link
                    
                    # feedparser normalizes dates to struct_time in 'published_parsed' or 'updated_parsed'
                    date_struct = entry.get('published_parsed') or entry.get('updated_parsed')
                    
                    pub_date = None
                    if date_struct:
                        # Convert struct_time to datetime
                        pub_date = datetime(*date_struct[:6], tzinfo=timezone.utc)
                    elif sitemap_dates:
                        # Fallback to sitemap lookup
                        norm_link = normalize_url(link)
                        if norm_link in sitemap_dates:
                            date_str = sitemap_dates[norm_link]
                            try:
                                pub_date = parser.parse(date_str)
                                if pub_date.tzinfo is None:
                                    pub_date = pub_date.replace(tzinfo=timezone.utc)
                            except Exception:
                                logging.warning(f"Could not parse sitemap date for {link}: {date_str}")
                    
                    if not pub_date:
                        logging.warning(f"No date found for entry: {title}")
                        continue

                    # Compare dates only (ignore time)
                    if pub_date.date() >= cutoff_date:
                        logging.info(f"New article found on {source['name']}: {title} ({pub_date})")
                        all_new_articles.append({
                            'source': source['name'],
                            'title': title,
                            'date': pub_date.strftime("%Y-%m-%d"),
                            'url': link,
                            'timestamp': pub_date.isoformat()
                        })
                    else:
                        logging.debug(f"Skipping old article: {title}")

            except Exception as e:
                logging.warning(f"Error parsing feed for {source['name']}: {e}")
                continue

        else:
            # HTML Scraping (Anthropic)
            try:
                response = requests.get(source['url'], timeout=10)
                response.raise_for_status()
            except requests.RequestException as e:
                logging.error(f"Failed to fetch {source['url']}: {e}")
                continue

            soup = BeautifulSoup(response.content, 'html.parser')
            articles = soup.select(source['article_selector'])
            logging.info(f"Found {len(articles)} articles on {source['name']}.")

            for article in articles:
                link = None
                try:
                    # Title
                    title_tag = article.select_one(source['title_selector'])
                    if not title_tag:
                        continue
                    title = title_tag.get_text(strip=True)

                    # Date
                    if source['name'] == "Anthropic Engineering":
                         # Special handling for Anthropic's sibling structure
                         date_tag = title_tag.find_next_sibling('div')
                    else:
                         date_tag = article.select_one(source['date_selector'])
                    
                    if date_tag:
                        date_str = date_tag.get_text(strip=True)
                    else:
                        # Fallback: Fetch detail page if date is missing (e.g. Featured articles)
                        logging.info(f"Date missing for '{title}', fetching detail page...")
                        
                        # Link extraction (needed early for fallback)
                        if source['link_selector']:
                            link_tag = article.select_one(source['link_selector'])
                            link = link_tag.get('href') if link_tag else None
                        else:
                            link = article.get('href')

                        if link and not link.startswith('http'):
                            link = f"{source['base_url']}{link}"
                            
                        if not link:
                            logging.warning(f"Could not find link for date fallback: {title}")
                            continue
                            
                        try:
                            detail_resp = requests.get(link, timeout=10)
                            detail_resp.raise_for_status()
                            detail_soup = BeautifulSoup(detail_resp.content, 'html.parser')
                            # Try to find date in detail page
                            # Selector based on debug: p[class*="HeroEngineering_date"]
                            detail_date_tag = detail_soup.select_one('p[class*="HeroEngineering_date"]')
                            if detail_date_tag:
                                date_str = detail_date_tag.get_text(strip=True).replace('Published', '')
                            else:
                                logging.warning(f"Could not find date in detail page for: {title}")
                                continue
                        except Exception as e:
                            logging.warning(f"Failed to fetch detail page for {link}: {e}")
                            continue

                    # Parse date
                    try:
                        pub_date = parser.parse(date_str)
                    except Exception:
                        logging.debug(f"Could not parse date: {date_str}")
                        continue
                    
                    if pub_date.tzinfo is None:
                        pub_date = pub_date.replace(tzinfo=timezone.utc)

                    # Link (if not already extracted)
                    if not link:
                        if source['link_selector']:
                            link_tag = article.select_one(source['link_selector'])
                            link = link_tag.get('href') if link_tag else None
                        else:
                            link = article.get('href')

                        if link and not link.startswith('http'):
                            link = f"{source['base_url']}{link}"

                    # Compare dates only (ignore time)
                    if pub_date.date() >= cutoff_date:
                        logging.info(f"New article found on {source['name']}: {title} ({date_str})")
                        all_new_articles.append({
                            'source': source['name'],
                            'title': title,
                            'date': date_str,
                            'url': link,
                            'timestamp': pub_date.isoformat()
                        })
                    else:
                        logging.debug(f"Skipping old article: {title} ({date_str})")

                except Exception as e:
                    logging.warning(f"Error parsing an article on {source['name']}: {e}")
                    continue

    return all_new_articles

if __name__ == "__main__":
    # For local testing, look back 30 days
    found = check_for_new_articles(lookback_hours=24 * 30)
    print(f"Found {len(found)} new articles.")
    for art in found:
        print(f"- [{art['source']}] {art['title']} ({art['url']})")
