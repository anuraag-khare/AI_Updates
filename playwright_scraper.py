"""
Playwright-based scraper for JavaScript-rendered websites.
This module handles sites that require a headless browser to render content.
"""

import logging
import re
from datetime import datetime, timezone
from dateutil import parser

# Playwright is optional - only import when needed
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


def is_playwright_available():
    """Check if Playwright is installed and available."""
    return PLAYWRIGHT_AVAILABLE


def parse_uber_date(date_str):
    """
    Parse Uber Engineering blog date format.
    Examples: "6 January / Global", "15 December / Global"
    Returns a datetime object or None if parsing fails.
    """
    if not date_str:
        return None
    
    # Remove the region suffix (e.g., "/ Global")
    date_part = date_str.split('/')[0].strip()
    
    # Add current year if not present (Uber format doesn't include year)
    if not re.search(r'\d{4}', date_part):
        current_year = datetime.now().year
        date_part = f"{date_part} {current_year}"
    
    try:
        pub_date = parser.parse(date_part)
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        return pub_date
    except Exception as e:
        logging.warning(f"Could not parse Uber date '{date_str}': {e}")
        return None


def scrape_uber_engineering(source_config, cutoff_date):
    """
    Scrape Uber Engineering blog using Playwright.
    
    Args:
        source_config: Dict with source configuration
        cutoff_date: datetime.date object for filtering articles
        
    Returns:
        List of article dicts with keys: source, title, date, url, timestamp
    """
    if not PLAYWRIGHT_AVAILABLE:
        logging.error("Playwright is not installed. Run: pip install playwright && playwright install chromium")
        return []
    
    articles = []
    url = source_config.get('url', 'https://www.uber.com/en-IN/blog/engineering/')
    base_url = source_config.get('base_url', 'https://www.uber.com')
    source_name = source_config.get('name', 'Uber Engineering')
    
    logging.info(f"Scraping {source_name} with Playwright...")
    
    try:
        with sync_playwright() as p:
            # Launch browser in headless mode
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            # Navigate to the blog page
            page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for article cards to load
            page.wait_for_selector('a[href*="/blog/"]', timeout=10000)
            
            # Find all article cards - they are links containing blog posts
            # Uber's structure: cards with title, category tags, and date
            article_cards = page.query_selector_all('a[href*="/blog/"]')
            
            seen_urls = set()
            
            for card in article_cards:
                try:
                    href = card.get_attribute('href')
                    if not href:
                        continue
                    
                    # Skip category/navigation links
                    if '/blog/engineering/' in href and href.endswith('engineering/'):
                        continue
                    if '/blog/engineering' == href.rstrip('/'):
                        continue
                    
                    # Build full URL
                    if href.startswith('/'):
                        full_url = f"{base_url}{href}"
                    else:
                        full_url = href
                    
                    # Remove query params for deduplication
                    clean_url = full_url.split('?')[0]
                    if clean_url in seen_urls:
                        continue
                    seen_urls.add(clean_url)
                    
                    # Get title from the card (usually h2 or h3)
                    title_elem = card.query_selector('h2, h3')
                    if not title_elem:
                        continue
                    title = title_elem.inner_text().strip()
                    if not title:
                        continue
                    
                    # Get date - it's in a div/span after the title, format: "6 January / Global"
                    # Try to find text that matches the date pattern
                    card_text = card.inner_text()
                    
                    # Look for date pattern: "DD Month / Region"
                    date_match = re.search(
                        r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s*/\s*\w+)',
                        card_text,
                        re.IGNORECASE
                    )
                    
                    if not date_match:
                        logging.debug(f"No date found for article: {title}")
                        continue
                    
                    date_str = date_match.group(1)
                    pub_date = parse_uber_date(date_str)
                    
                    if not pub_date:
                        continue
                    
                    # Check if article is within cutoff
                    if pub_date.date() >= cutoff_date:
                        logging.info(f"New article found on {source_name}: {title} ({date_str})")
                        articles.append({
                            'source': source_name,
                            'title': title,
                            'date': pub_date.strftime("%Y-%m-%d"),
                            'url': clean_url,
                            'timestamp': pub_date.isoformat()
                        })
                    else:
                        logging.debug(f"Skipping old article: {title} ({date_str})")
                        
                except Exception as e:
                    logging.warning(f"Error parsing article card: {e}")
                    continue
            
            browser.close()
            
    except Exception as e:
        logging.error(f"Playwright scraping error for {source_name}: {e}")
        return []
    
    logging.info(f"Found {len(articles)} new articles from {source_name}")
    return articles


def scrape_with_playwright(source_config, cutoff_date):
    """
    Generic Playwright scraper dispatcher.
    Routes to specific scrapers based on source name/type.
    
    Args:
        source_config: Dict with source configuration
        cutoff_date: datetime.date object for filtering articles
        
    Returns:
        List of article dicts
    """
    source_name = source_config.get('name', '')
    
    if 'uber' in source_name.lower():
        return scrape_uber_engineering(source_config, cutoff_date)
    
    # Add more site-specific scrapers here as needed
    logging.warning(f"No Playwright scraper implemented for: {source_name}")
    return []

