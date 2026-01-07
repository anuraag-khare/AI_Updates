import re
import requests
from bs4 import BeautifulSoup
from dateutil import parser
from datetime import datetime, timedelta, timezone
import logging
import feedparser
import ssl
import xml.etree.ElementTree as ET

# Import Playwright scraper module (optional dependency)
from playwright_scraper import scrape_with_playwright, is_playwright_available

# Workaround for SSL certificate verify failed on some systems
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SOURCES = [
    {
        "name": "Anthropic Engineering",
        "type": "anthropic",  # Custom robust scraper for Anthropic
        "url": "https://www.anthropic.com/engineering",
        "base_url": "https://www.anthropic.com"
    },
    {
        "name": "Google Developers (AI)",
        "type": "feed",
        "url": "https://developers.googleblog.com/feeds/posts/default?alt=atom&category=AI",
        "sitemap_url": "https://developers.googleblog.com/sitemap.xml"
    },
    {
        "name": "Uber Engineering",
        "type": "playwright",  # Requires headless browser (JS-rendered site)
        "url": "https://www.uber.com/en-IN/blog/engineering/",
        "base_url": "https://www.uber.com"
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


def fetch_title_from_page(url):
    """
    Fetches article title using stable meta tags (og:title) or <h1>.
    These are SEO-critical and rarely change, unlike CSS class names.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Priority 1: og:title meta tag (most stable, SEO-critical)
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title and og_title.get('content'):
            return og_title.get('content').strip()
        
        # Priority 2: twitter:title meta tag
        twitter_title = soup.select_one('meta[name="twitter:title"]')
        if twitter_title and twitter_title.get('content'):
            return twitter_title.get('content').strip()
        
        # Priority 3: <h1> element (semantic HTML, stable)
        h1 = soup.select_one('h1')
        if h1:
            return h1.get_text(strip=True)
        
        # Priority 4: <title> tag (remove site suffix if present)
        title_tag = soup.select_one('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Remove common suffixes like " | Site Name" or " \ Site Name"
            for sep in [' | ', ' \\ ', ' - ', ' – ']:
                if sep in title:
                    title = title.split(sep)[0].strip()
            return title
        
        return None
    except Exception as e:
        logging.warning(f"Failed to fetch title from {url}: {e}")
        return None


def scrape_anthropic_engineering(source, cutoff_date):
    """
    Robust scraper for Anthropic Engineering blog.
    
    Strategy (in order of reliability):
    1. Find all <article> elements (semantic HTML - very stable)
    2. Find links within articles that point to /engineering/ paths
    3. Extract title from heading elements (h2, h3) or fetch from detail page og:title
    4. Extract date from text patterns (e.g., "Nov 24, 2025") or fetch from detail page
    
    This avoids relying on CSS class names which change frequently.
    """
    articles = []
    source_name = source.get('name', 'Anthropic Engineering')
    base_url = source.get('base_url', 'https://www.anthropic.com')
    page_url = source.get('url', 'https://www.anthropic.com/engineering')
    
    try:
        response = requests.get(page_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Strategy 1: Find all <article> elements (semantic HTML)
        article_elements = soup.select('article')
        logging.info(f"Found {len(article_elements)} <article> elements on {source_name}")
        
        seen_urls = set()
        
        for article_elem in article_elements:
            # Find links to engineering articles
            links = article_elem.select('a[href*="/engineering/"]')
            
            for link in links:
                href = link.get('href', '')
                
                # Skip the main engineering page link
                if href.rstrip('/') in ['/engineering', '/engineering/']:
                    continue
                    
                # Build full URL
                if href.startswith('/'):
                    full_url = f"{base_url}{href}"
                else:
                    full_url = href
                
                # Deduplicate
                clean_url = full_url.split('?')[0].rstrip('/')
                if clean_url in seen_urls:
                    continue
                seen_urls.add(clean_url)
                
                # Extract title - try heading in the link first
                title = None
                title_elem = link.select_one('h1, h2, h3, h4')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                
                # Extract date - look for date pattern in link text
                # Common formats: "Nov 24, 2025", "November 24, 2025"
                link_text = link.get_text()
                date_match = re.search(
                    r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})',
                    link_text,
                    re.IGNORECASE
                )
                
                pub_date = None
                date_str = None
                if date_match:
                    date_str = date_match.group(1)
                    try:
                        pub_date = parser.parse(date_str)
                        if pub_date.tzinfo is None:
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                    except Exception:
                        pass
                
                # If no title or date, fetch from detail page
                if not title or not pub_date:
                    logging.debug(f"Fetching detail page for: {clean_url}")
                    try:
                        detail_resp = requests.get(clean_url, timeout=10)
                        detail_resp.raise_for_status()
                        detail_soup = BeautifulSoup(detail_resp.content, 'html.parser')
                        
                        # Get title from og:title (most reliable)
                        if not title:
                            title = fetch_title_from_page(clean_url)
                        
                        # Get date from detail page - look for date patterns
                        if not pub_date:
                            # Try meta tag first
                            date_meta = detail_soup.select_one('meta[property="article:published_time"]')
                            if date_meta and date_meta.get('content'):
                                try:
                                    pub_date = parser.parse(date_meta.get('content'))
                                    if pub_date.tzinfo is None:
                                        pub_date = pub_date.replace(tzinfo=timezone.utc)
                                    date_str = pub_date.strftime("%b %d, %Y")
                                except Exception:
                                    pass
                            
                            # Try finding text with "Published" or date pattern
                            if not pub_date:
                                page_text = detail_soup.get_text()
                                published_match = re.search(
                                    r'Published\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})',
                                    page_text,
                                    re.IGNORECASE
                                )
                                if published_match:
                                    date_str = published_match.group(1)
                                    try:
                                        pub_date = parser.parse(date_str)
                                        if pub_date.tzinfo is None:
                                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                                    except Exception:
                                        pass
                    except Exception as e:
                        logging.debug(f"Could not fetch detail page {clean_url}: {e}")
                
                # Skip if we still don't have required data
                if not title:
                    logging.debug(f"Skipping article without title: {clean_url}")
                    continue
                if not pub_date:
                    logging.debug(f"Skipping article without date: {title}")
                    continue
                
                # Check if within cutoff
                if pub_date.date() >= cutoff_date:
                    logging.info(f"New article found on {source_name}: {title} ({date_str})")
                    articles.append({
                        'source': source_name,
                        'title': title,
                        'date': date_str if date_str else pub_date.strftime("%Y-%m-%d"),
                        'url': clean_url,
                        'timestamp': pub_date.isoformat()
                    })
                        
    except Exception as e:
        logging.error(f"Error scraping {source_name}: {e}")
    
    return articles

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
        
        if source.get('type') == 'anthropic':
            # Custom robust scraper for Anthropic (uses semantic HTML + meta tags)
            try:
                anthropic_articles = scrape_anthropic_engineering(source, cutoff_date)
                all_new_articles.extend(anthropic_articles)
            except Exception as e:
                logging.error(f"Anthropic scraping failed: {e}")
            continue
        
        elif source.get('type') == 'playwright':
            # Playwright-based scraping for JS-rendered sites
            if not is_playwright_available():
                logging.warning(f"Skipping {source['name']}: Playwright not installed")
                continue
            
            try:
                playwright_articles = scrape_with_playwright(source, cutoff_date)
                all_new_articles.extend(playwright_articles)
            except Exception as e:
                logging.error(f"Playwright scraping failed for {source['name']}: {e}")
            continue
        
        elif source.get('type') == 'feed':
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

                    # Date - use the date_selector from config
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
                            # Try to find date in detail page - look for element with "date" in class
                            detail_date_tag = detail_soup.select_one('[class*="date"]')
                            if detail_date_tag:
                                date_str = detail_date_tag.get_text(strip=True).replace('Published', '').strip()
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
