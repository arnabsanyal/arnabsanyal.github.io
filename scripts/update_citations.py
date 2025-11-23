#!/usr/bin/env python3
"""
Script to automatically update Google Scholar citation count in content.yml

This script directly scrapes Google Scholar using ScraperAPI to bypass
IP blocking issues in CI/CD environments like GitHub Actions.
"""

import os
import re
import sys
import time
import random
import requests
from bs4 import BeautifulSoup

# Google Scholar ID
SCHOLAR_ID = "D9ebkwoAAAAJ"
CONTENT_FILE = "data/content.yml"
INDEX_FILE = "index.html"
MAX_RETRIES = 5

# Google Scholar profile URL
SCHOLAR_URL = f"https://scholar.google.com/citations?user={SCHOLAR_ID}&hl=en"


def get_citation_count_direct(scholar_id):
    """
    Fetch citation count by directly scraping Google Scholar profile page.
    Uses ScraperAPI if available to bypass IP blocking.

    Args:
        scholar_id: Google Scholar author ID

    Returns:
        int: Total citation count
    """
    scraper_api_key = os.getenv('SCRAPER_API_KEY')
    scholar_url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"Attempt {attempt}/{MAX_RETRIES}: Fetching citation data...")

            # Add random delay to avoid rate limiting
            if attempt > 1:
                wait_time = random.randint(10, 30) * attempt
                print(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                time.sleep(random.randint(2, 5))

            # Build the request URL
            if scraper_api_key:
                # Use ScraperAPI to bypass blocking
                api_url = "https://api.scraperapi.com"
                params = {
                    "api_key": scraper_api_key,
                    "url": scholar_url,
                    "render": "false",  # Don't need JS rendering
                }
                print(f"Using ScraperAPI proxy...")
                response = requests.get(api_url, params=params, timeout=60)
            else:
                # Direct request (works locally, may fail on CI/CD)
                print("No SCRAPER_API_KEY found, making direct request...")
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                }
                response = requests.get(scholar_url, headers=headers, timeout=30)

            response.raise_for_status()

            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Method 1: Find the citation count in the stats table
            # The citation count is in a table with id "gsc_rsb_st"
            stats_table = soup.find('table', {'id': 'gsc_rsb_st'})
            if stats_table:
                rows = stats_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        header = cells[0].get_text(strip=True).lower()
                        if 'citations' in header:
                            # First value is "All", second is "Since year"
                            citation_text = cells[1].get_text(strip=True)
                            citations = int(citation_text.replace(',', ''))
                            print(f"✓ Successfully fetched citation count: {citations}")
                            return citations

            # Method 2: Look for the citation count in gsc_rsb_std class
            citation_cells = soup.find_all('td', {'class': 'gsc_rsb_std'})
            if citation_cells and len(citation_cells) >= 1:
                citation_text = citation_cells[0].get_text(strip=True)
                citations = int(citation_text.replace(',', ''))
                print(f"✓ Successfully fetched citation count: {citations}")
                return citations

            # Method 3: Try regex as fallback
            match = re.search(r'Citations.*?(\d+(?:,\d+)?)', response.text, re.IGNORECASE | re.DOTALL)
            if match:
                citations = int(match.group(1).replace(',', ''))
                print(f"✓ Successfully fetched citation count: {citations}")
                return citations

            # If we got here, we couldn't find the citation count
            print(f"✗ Could not parse citation count from page")
            print(f"Response length: {len(response.text)} characters")

            # Check if we got a CAPTCHA or block page
            if "CAPTCHA" in response.text or "unusual traffic" in response.text.lower():
                print("✗ Google Scholar returned a CAPTCHA/block page")
                raise Exception("Blocked by Google Scholar (CAPTCHA)")

            raise Exception("Could not find citation count in page")

        except requests.exceptions.RequestException as e:
            print(f"✗ Attempt {attempt} failed (network error): {e}")
        except Exception as e:
            print(f"✗ Attempt {attempt} failed: {e}")

        if attempt < MAX_RETRIES:
            print("Retrying...")
        else:
            print(f"✗ All {MAX_RETRIES} attempts failed")
            sys.exit(1)


def update_yaml_file(file_path, new_count):
    """
    Update the citation count in the YAML file using regex replacement.
    This preserves the original file formatting, comments, and quote styles.
    If the file doesn't exist, it will be skipped.

    Args:
        file_path: Path to content.yml
        new_count: New citation count to write
    """
    # Check if file exists - skip if not
    if not os.path.exists(file_path):
        print(f"⚠ {file_path} not found, skipping...")
        return

    try:
        # Read the file as plain text to preserve formatting
        with open(file_path, 'r') as f:
            content = f.read()

        # Find and replace the citation count for GOOGLE SCHOLAR CITATIONS
        # Pattern matches: name: 'GOOGLE SCHOLAR CITATIONS' followed by image: ... then count: 'XX'
        # We need to find the count value in the funfact entry for Google Scholar Citations
        pattern = r"(- name:\s*['\"]?GOOGLE SCHOLAR CITATIONS['\"]?\s*\n\s*image:[^\n]*\n\s*count:\s*['\"])(\d+)(['\"])"

        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            old_count = match.group(2)
            new_content = re.sub(pattern, rf"\g<1>{new_count}\g<3>", content, flags=re.IGNORECASE)

            # Write back to file
            with open(file_path, 'w') as f:
                f.write(new_content)

            print(f"✓ Updated citation count: {old_count} -> {new_count}")
            print(f"✓ Successfully updated {file_path}")
        else:
            # Try alternative pattern (different field order)
            pattern2 = r"(name:\s*['\"]?GOOGLE SCHOLAR CITATIONS['\"]?[\s\S]*?count:\s*['\"])(\d+)(['\"])"
            match2 = re.search(pattern2, content, re.IGNORECASE)
            if match2:
                old_count = match2.group(2)
                new_content = re.sub(pattern2, rf"\g<1>{new_count}\g<3>", content, count=1, flags=re.IGNORECASE)

                with open(file_path, 'w') as f:
                    f.write(new_content)

                print(f"✓ Updated citation count: {old_count} -> {new_count}")
                print(f"✓ Successfully updated {file_path}")
            else:
                print(f"⚠ Could not find GOOGLE SCHOLAR CITATIONS entry in {file_path}, skipping...")

    except Exception as e:
        print(f"⚠ Error updating YAML file: {e}, skipping...")


def update_index_html(file_path, new_count):
    """
    Update the citation count in the index.html file.
    Finds the data-count attribute for GOOGLE SCHOLAR CITATIONS and updates it.

    Args:
        file_path: Path to index.html
        new_count: New citation count to write
    """
    try:
        # Read the file as plain text
        with open(file_path, 'r') as f:
            content = f.read()

        # Pattern to find the Google Scholar Citations data-count
        # Matches: <img ... alt="GOOGLE SCHOLAR CITATIONS" />
        #          <p class="fact-counter count" data-count="XX">0</p>
        #          <p>GOOGLE SCHOLAR CITATIONS</p>
        pattern = r'(<img[^>]*alt="GOOGLE SCHOLAR CITATIONS"[^>]*/>\s*<p[^>]*data-count=")(\d+)("[^>]*>)'

        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            old_count = match.group(2)
            new_content = re.sub(pattern, rf'\g<1>{new_count}\g<3>', content, flags=re.IGNORECASE)

            # Write back to file
            with open(file_path, 'w') as f:
                f.write(new_content)

            print(f"✓ Updated index.html data-count: {old_count} -> {new_count}")
            print(f"✓ Successfully updated {file_path}")
        else:
            print(f"⚠ Could not find GOOGLE SCHOLAR CITATIONS data-count in {file_path}")

    except Exception as e:
        print(f"✗ Error updating index.html: {e}")
        sys.exit(1)


def main():
    """Main function"""
    # Change to repository root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    os.chdir(repo_root)

    print("=== Updating Google Scholar Citations ===")
    print(f"Scholar ID: {SCHOLAR_ID}")
    print(f"Scholar URL: {SCHOLAR_URL}")

    # Check for API key
    if os.getenv('SCRAPER_API_KEY'):
        print("ScraperAPI key found - will use proxy")
    else:
        print("No ScraperAPI key - using direct request (may fail on CI/CD)")

    # Fetch citation count
    citation_count = get_citation_count_direct(SCHOLAR_ID)

    # Update YAML file
    update_yaml_file(CONTENT_FILE, citation_count)

    # Update index.html
    update_index_html(INDEX_FILE, citation_count)

    print("=== Update Complete ===")


if __name__ == "__main__":
    main()
