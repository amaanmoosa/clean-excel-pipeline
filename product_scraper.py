"""
product_scraper_bs4.py
──────────────────────
Scrapes product names & prices from books.toscrape.com
using Requests + BeautifulSoup. Outputs a clean CSV.

Target: https://books.toscrape.com  (legal scraping sandbox)
"""

import csv
import time
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ── Configuration ──────────────────────────────────────────────
BASE_URL = "https://books.toscrape.com/"
OUTPUT_FILE = "products.csv"
MAX_PAGES = 3                     # Limit pages to be respectful
REQUEST_DELAY = 1.5               # Seconds between requests
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

# ── Logging Setup ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def fetch_page(url: str) -> BeautifulSoup | None:
    """Fetch a URL and return a parsed BeautifulSoup object."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()          # Raise on 4xx / 5xx
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        logger.error("Failed to fetch %s → %s", url, e)
        return None


def parse_products(soup: BeautifulSoup) -> list[dict]:
    """Extract product name, price, availability & URL from a page."""
    products = []
    articles = soup.select("article.product_pod")

    for article in articles:
        # ── Product Name ───────────────────────────────────
        title_tag = article.select_one("h3 a")
        name = title_tag["title"] if title_tag else "N/A"

        # ── Price ──────────────────────────────────────────
        price_tag = article.select_one("p.price_color")
        price = price_tag.get_text(strip=True) if price_tag else "N/A"

        # ── Availability ───────────────────────────────────
        avail_tag = article.select_one("p.instock.availability")
        availability = (
            avail_tag.get_text(strip=True) if avail_tag else "N/A"
        )

        # ── Product Link ───────────────────────────────────
        link = urljoin(BASE_URL, title_tag["href"]) if title_tag else ""

        products.append({
            "product_name": name,
            "price": price,
            "availability": availability,
            "product_url": link,
        })

    return products


def get_next_page_url(soup: BeautifulSoup, current_url: str) -> str | None:
    """Return the URL of the 'next' page, or None if on the last page."""
    next_btn = soup.select_one("li.next a")
    if next_btn:
        return urljoin(current_url, next_btn["href"])
    return None


def save_to_csv(products: list[dict], filepath: str) -> None:
    """Write the product list to a neatly structured CSV file."""
    if not products:
        logger.warning("No products to save.")
        return

    fieldnames = ["product_name", "price", "availability", "product_url"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)

    logger.info("✅  Saved %d products → %s", len(products), filepath)


def main():
    all_products: list[dict] = []
    current_url = BASE_URL

    for page_num in range(1, MAX_PAGES + 1):
        logger.info("📄  Scraping page %d: %s", page_num, current_url)

        soup = fetch_page(current_url)
        if soup is None:
            break

        page_products = parse_products(soup)
        all_products.extend(page_products)
        logger.info("   ↳ Found %d products on this page.", len(page_products))

        # ── Respectful delay ───────────────────────────────
        time.sleep(REQUEST_DELAY)

        # ── Pagination ─────────────────────────────────────
        next_url = get_next_page_url(soup, current_url)
        if next_url is None:
            logger.info("🏁  No more pages.")
            break
        current_url = next_url

    save_to_csv(all_products, OUTPUT_FILE)


if __name__ == "__main__":
    main()
