#!/usr/bin/env python3
"""
Script to automatically update the Google Scholar citation count on the site

Google Scholar blocks datacenter IPs (GitHub Actions, scraping proxies), so
this is meant to run from a home machine such as a NAS. It uses only the
Python standard library, so it runs on a stock Synology DSM 7 install.

Two modes:
  python3 update_citations.py
      Update index.html in a local checkout of the repository.
  GITHUB_TOKEN=... python3 update_citations.py --push
      Update index.html on GitHub directly through the REST API; no clone or
      git install needed. The token needs Contents: read/write on this repo.
"""

import base64
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request

# Google Scholar ID
SCHOLAR_ID = "D9ebkwoAAAAJ"
INDEX_FILE = "index.html"
MAX_RETRIES = 3

# Google Scholar profile URL
SCHOLAR_URL = f"https://scholar.google.com/citations?user={SCHOLAR_ID}&hl=en"

# GitHub repository updated in --push mode
GITHUB_REPO = "arnabsanyal/arnabsanyal.github.io"
GITHUB_BRANCH = "master"
COMMIT_MESSAGE = "🤖 Auto-update Google Scholar citation count"

# Matches: <img ... alt="GOOGLE SCHOLAR CITATIONS" />
#          <p class="fact-counter count" data-count="XX">0</p>
COUNT_PATTERN = re.compile(
    r'(<img[^>]*alt="GOOGLE SCHOLAR CITATIONS"[^>]*/>\s*<p[^>]*data-count=")(\d+)("[^>]*>)',
    re.IGNORECASE,
)


class BlockedError(Exception):
    """Google Scholar returned a CAPTCHA / unusual-traffic page."""


def fetch_citation_count():
    """
    Fetch the total citation count from the Google Scholar profile page.

    Returns:
        int: Total citation count
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"Attempt {attempt}/{MAX_RETRIES}: Fetching citation data...")
            if attempt > 1:
                wait_time = random.randint(10, 30) * attempt
                print(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)

            request = urllib.request.Request(SCHOLAR_URL, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")

            if "captcha" in html.lower() or "unusual traffic" in html.lower():
                raise BlockedError("Blocked by Google Scholar (CAPTCHA)")

            # The first "gsc_rsb_std" cell of the stats table is "Citations / All"
            match = re.search(r'class="gsc_rsb_std">([\d,]+)<', html)
            if not match:
                raise ValueError(f"Could not find citation count in page ({len(html)} characters)")

            citations = int(match.group(1).replace(",", ""))
            print(f"✓ Successfully fetched citation count: {citations}")
            return citations

        except BlockedError as e:
            # Retrying from the same IP only makes the block last longer
            print(f"✗ {e}")
            sys.exit(1)
        except urllib.error.HTTPError as e:
            print(f"✗ Attempt {attempt} failed: HTTP {e.code} {e.reason}")
            if e.code == 429:
                sys.exit(1)
        except Exception as e:
            print(f"✗ Attempt {attempt} failed: {e}")

    print(f"✗ All {MAX_RETRIES} attempts failed")
    sys.exit(1)


def replace_count(content, new_count):
    """
    Replace the GOOGLE SCHOLAR CITATIONS data-count in index.html content.

    Returns:
        tuple: (new_content, old_count), or (None, None) if not found
    """
    match = COUNT_PATTERN.search(content)
    if not match:
        return None, None
    new_content = COUNT_PATTERN.sub(rf"\g<1>{new_count}\g<3>", content, count=1)
    return new_content, int(match.group(2))


def update_local_file(file_path, new_count):
    """Update the citation count in a local index.html."""
    with open(file_path, "r") as f:
        content = f.read()

    new_content, old_count = replace_count(content, new_count)
    if new_content is None:
        print(f"✗ Could not find GOOGLE SCHOLAR CITATIONS data-count in {file_path}")
        sys.exit(1)
    if old_count == new_count:
        print(f"✓ Citation count unchanged ({new_count}), nothing to do")
        return

    with open(file_path, "w") as f:
        f.write(new_content)
    print(f"✓ Updated {file_path} data-count: {old_count} -> {new_count}")


def github_request(method, path, token, body=None):
    """Call the GitHub REST API and return the decoded JSON response."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}/{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "update-citations-script",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def update_github_file(file_path, new_count, token):
    """Update the citation count in index.html on GitHub via the contents API."""
    try:
        current = github_request("GET", f"contents/{file_path}?ref={GITHUB_BRANCH}", token)
        content = base64.b64decode(current["content"]).decode("utf-8")

        new_content, old_count = replace_count(content, new_count)
        if new_content is None:
            print(f"✗ Could not find GOOGLE SCHOLAR CITATIONS data-count in {file_path} on GitHub")
            sys.exit(1)
        if old_count == new_count:
            print(f"✓ Citation count unchanged ({new_count}), nothing to push")
            return

        github_request("PUT", f"contents/{file_path}", token, {
            "message": COMMIT_MESSAGE,
            "content": base64.b64encode(new_content.encode("utf-8")).decode("ascii"),
            "sha": current["sha"],
            "branch": GITHUB_BRANCH,
        })
        print(f"✓ Pushed {file_path} data-count: {old_count} -> {new_count} to {GITHUB_BRANCH}")

    except urllib.error.HTTPError as e:
        print(f"✗ GitHub API error: HTTP {e.code} {e.reason}: {e.read().decode(errors='replace')[:300]}")
        sys.exit(1)


def main():
    """Main function"""
    push = "--push" in sys.argv[1:]

    print("=== Updating Google Scholar Citations ===")
    print(f"Scholar ID: {SCHOLAR_ID}")
    print(f"Scholar URL: {SCHOLAR_URL}")

    token = os.getenv("GITHUB_TOKEN")
    if push and not token:
        print("✗ --push needs a GITHUB_TOKEN environment variable")
        sys.exit(1)

    citation_count = fetch_citation_count()

    if push:
        update_github_file(INDEX_FILE, citation_count, token)
    else:
        # Change to repository root directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(os.path.dirname(script_dir))
        update_local_file(INDEX_FILE, citation_count)

    print("=== Update Complete ===")


if __name__ == "__main__":
    main()
