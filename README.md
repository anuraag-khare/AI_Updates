# Blog Scraper with Notifications

A Python tool that scrapes AI/Engineering blogs for new articles and sends notifications via Telegram.

**Monitored Sources:**
- [Anthropic Engineering Blog](https://www.anthropic.com/engineering)
- [Google Developers Blog (AI)](https://developers.googleblog.com/search/?technology_categories=AI)
- [Uber Engineering Blog](https://www.uber.com/en-IN/blog/engineering/)

## Features
- **Multi-Source Scraping** with robust, change-resistant strategies:
    - **Anthropic Engineering**: Semantic HTML scraping (uses `<article>` elements + date pattern matching — resilient to CSS class changes).
    - **Google Developers (AI)**: RSS feed + Sitemap fallback (handles missing feed dates).
    - **Uber Engineering**: Playwright-based scraping (headless browser for JS-rendered content).
- **Smart Freshness Check**: Checks for articles published since yesterday (date-based comparison, ignores time).
- **Instant Notifications**: Sends Telegram alerts with article title, source, and link.
- **Stateless**: Time-based check allows for easy, state-free deployment.

## Robustness Strategy

Web scraping is fragile because websites change their HTML structure frequently. This scraper mitigates that by prioritizing stable data sources:

| Priority | Data Source | Stability | Used For |
|----------|-------------|-----------|----------|
| 1 | RSS/Atom Feeds | ⭐⭐⭐⭐⭐ | Google Developers |
| 2 | Semantic HTML (`<article>`, `<h1>`) | ⭐⭐⭐⭐ | Anthropic (structure) |
| 3 | Text Pattern Matching | ⭐⭐⭐⭐ | Anthropic (dates like "Nov 24, 2025") |
| 4 | Meta Tags (`og:title`) | ⭐⭐⭐⭐ | Fallback for titles |
| 5 | CSS Selectors | ⭐ | Avoid (breaks often) |

**Why this works:**
- **RSS feeds** are standardized and stable
- **Semantic HTML** (`<article>`, `<h1>`) is part of HTML5 spec and rarely changes
- **Date patterns** like "Nov 24, 2025" are human-readable and stable
- **Meta tags** like `og:title` are SEO-critical (rarely change)
- **CSS class names** (especially with CSS Modules like `ArticleList-module-scss-module___tpu-a__cardLink`) change on every build — avoid!

**⚠️ Note on Sitemaps:** Sitemap `lastmod` dates indicate when a page was *last modified*, not when it was *originally published*. This scraper uses actual publication dates from the page content.

## Setup

1.  **Install Dependencies**:
    ```bash
    uv sync
    # OR
    pip install -r requirements.txt
    ```

2.  **Install Playwright Browser** (required for Uber Engineering):
    ```bash
    playwright install chromium
    ```

3.  **Configure Telegram**:
    - Create a bot via [@BotFather](https://t.me/BotFather) to get your `TELEGRAM_BOT_TOKEN`.
    - Run the helper script to get your `TELEGRAM_CHAT_ID`:
        ```bash
        uv run get_chat_id.py
        ```
    - Create a `.env` file with your actual credentials:
        ```bash
        TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
        TELEGRAM_CHAT_ID=987654321
        ```

4.  **Run Locally**:
    ```bash
    uv run main.py
    ```

## Free Hosting Options

Since this script only needs to run once a day, you can host it for free on several platforms.

### Option 1: GitHub Actions (Recommended - Easiest & Completely Free)
You can run this script as a scheduled workflow directly on GitHub. No cloud account required.

1.  Push this code to a GitHub repository.
2.  Go to **Settings > Secrets and variables > Actions**.
3.  Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as Repository Secrets.
4.  Configure run frequency in .github/workflows/daily_scrape.yml.

### Option 2: Google Cloud Functions (Free Tier)
Google Cloud offers 2 million free invocations per month.

1.  Create a Google Cloud Project.
2.  Enable the **Cloud Functions** and **Cloud Build** APIs.
3.  Deploy the function:
    ```bash
    gcloud functions deploy blog-scraper \
      --runtime python311 \
      --trigger-http \
      --entry-point main \
      --set-env-vars TELEGRAM_BOT_TOKEN=...,TELEGRAM_CHAT_ID=...
    ```
4.  Set up **Cloud Scheduler** to trigger the function URL once a day.

### Option 3: AWS Lambda (Free Tier)
AWS offers 400,000 GB-seconds of compute time per month forever.

1.  Zip the code and dependencies.
2.  Create a Lambda function (Python 3.x).
3.  Upload the zip.
4.  Set Environment Variables in the Configuration tab.
5.  Create an **EventBridge (CloudWatch Events)** rule to trigger the Lambda on a schedule (e.g., `rate(1 day)`).
