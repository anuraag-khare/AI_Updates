# Blog Scraper with Notifications

A Python tool that scrapes the [Anthropic Engineering Blog](https://www.anthropic.com/engineering) and [Google Developers Blog (AI)](https://developers.googleblog.com/search/?technology_categories=AI) for new articles and sends notifications via Telegram.

## Features
- **Multi-Source Scraping**:
    - **Anthropic Engineering**: HTML scraping.
    - **Google Developers (AI)**: Hybrid RSS + Sitemap scraping (to handle client-side rendering and missing feed dates).
- **Smart Freshness Check**: Checks for articles published in the last 24 hours.
- **Instant Notifications**: Sends Telegram alerts with article title, source, and link.
- **Stateless**: Time-based check allows for easy, state-free deployment.

## Setup

1.  **Install Dependencies**:
    ```bash
    uv sync
    # OR
    pip install -r requirements.txt
    ```

2.  **Configure Telegram**:
    - Create a bot via [@BotFather](https://t.me/BotFather) to get your `TELEGRAM_BOT_TOKEN`.
    - Run the helper script to get your `TELEGRAM_CHAT_ID`:
        ```bash
        uv run get_chat_id.py
        ```
    - Create a `.env` file:
        ```bash
        TELEGRAM_BOT_TOKEN=your_token
        TELEGRAM_CHAT_ID=your_chat_id
        ```

3.  **Run Locally**:
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
4.  Create a file `.github/workflows/daily_scrape.yml`:

    ```yaml
    name: Daily Scrape
    on:
      schedule:
        - cron: '0 9 * * *' # Runs every day at 09:00 UTC
      workflow_dispatch: # Allows manual trigger

    jobs:
      scrape:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v3
          - name: Set up Python
            uses: actions/setup-python@v4
            with:
              python-version: '3.10'
          - name: Install dependencies
            run: |
              pip install -r requirements.txt
          - name: Run Scraper
            env:
              TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
              TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
            run: python main.py
    ```

### Option 2: Google Cloud Functions (Free Tier)
Google Cloud offers 2 million free invocations per month.

1.  Create a Google Cloud Project.
2.  Enable the **Cloud Functions** and **Cloud Build** APIs.
3.  Deploy the function:
    ```bash
    gcloud functions deploy anthropic-scraper \
      --runtime python310 \
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
