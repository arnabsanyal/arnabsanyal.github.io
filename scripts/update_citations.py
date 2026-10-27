#!/usr/bin/env python3
"""
Script to automatically update the fun-fact counters on the site

Updates these counters in index.html:
  - GOOGLE SCHOLAR CITATIONS: total citations on the Google Scholar profile
  - STACK EXCHANGE OUTREACH:  "reached" on the Stack Overflow profile

Google Scholar blocks datacenter IPs (GitHub Actions, scraping proxies), so
this is meant to run from a home machine such as a NAS. It uses only the
Python standard library, so it runs on a stock Synology DSM 7 install.
It runs weekly, Mondays at 00:00, from Synology Task Scheduler.

Two modes:
  python3 update_citations.py
      Update index.html in a local checkout of the repository.
  GITHUB_TOKEN=... python3 update_citations.py --push
      Update index.html on GitHub directly through the REST API; no clone or
      git install needed. The token needs Contents: read/write on this repo.

If one source fails the others are still updated, and the script exits
non-zero so the scheduler reports the failure.
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
SCHOLAR_URL = f"https://scholar.google.com/citations?user={SCHOLAR_ID}&hl=en"

# Stack Overflow profile
STACKOVERFLOW_URL = "https://stackoverflow.com/users/senior-mle?tab=profile"

INDEX_FILE = "index.html"
MAX_RETRIES = 3

# GitHub repository updated in --push mode
GITHUB_REPO = "arnabsanyal/arnabsanyal.github.io"
GITHUB_BRANCH = "master"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class BlockedError(Exception):
    """The site returned a CAPTCHA / rate-limit page; retrying won't help."""


def fetch_page(url):
    """
    Fetch a page with browser-like headers, retrying transient failures.

    Returns:
        str: Page HTML
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"Attempt {attempt}/{MAX_RETRIES}: Fetching {url}")
            if attempt > 1:
                wait_time = random.randint(10, 30) * attempt
                print(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)

            request = urllib.request.Request(url, headers=BROWSER_HEADERS)
            with urllib.request.urlopen(request, timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")

            if "captcha" in html.lower() or "unusual traffic" in html.lower():
                raise BlockedError("Blocked (CAPTCHA page)")
            return html

        except urllib.error.HTTPError as e:
            # Retrying from the same IP only makes a block last longer
            if e.code == 429:
                raise BlockedError("Rate limited (HTTP 429)")
            print(f"✗ Attempt {attempt} failed: HTTP {e.code} {e.reason}")
        except urllib.error.URLError as e:
            print(f"✗ Attempt {attempt} failed: {e.reason}")

    raise RuntimeError(f"All {MAX_RETRIES} attempts failed")


def fetch_scholar_citations():
    """Total citation count from the Google Scholar profile page."""
    html = fetch_page(SCHOLAR_URL)
    # The first "gsc_rsb_std" cell of the stats table is "Citations / All"
    match = re.search(r'class="gsc_rsb_std">([\d,]+)<', html)
    if not match:
        raise ValueError(f"Could not find citation count in page ({len(html)} characters)")
    return int(match.group(1).replace(",", ""))


def parse_abbreviated(text):
    """Turn Stack Overflow's abbreviated numbers ("4,521", "298k", "1.2m") into ints."""
    match = re.fullmatch(r"([\d.,]+)\s*([km]?)", text.strip().lower())
    if not match:
        raise ValueError(f"Unrecognised number: {text!r}")
    multiplier = {"": 1, "k": 1000, "m": 1000000}[match.group(2)]
    return round(float(match.group(1).replace(",", "")) * multiplier)


def fetch_stackoverflow_reach():
    """People "reached" from the Stack Overflow profile page (rounded, e.g. 298k)."""
    html = fetch_page(STACKOVERFLOW_URL)
    # <div class="fs-body3 fc-black-600">298k</div> reached
    match = re.search(r'<div class="fs-body3[^"]*">\s*([\d.,]+\s*[kKmM]?)\s*</div>\s*reached\b', html)
    if not match:
        raise ValueError(f"Could not find reached count in page ({len(html)} characters)")
    return parse_abbreviated(match.group(1))


# (label used in index.html, fetch function)
STATS = [
    ("GOOGLE SCHOLAR CITATIONS", fetch_scholar_citations),
    ("STACK EXCHANGE OUTREACH", fetch_stackoverflow_reach),
]


def replace_count(content, label, new_count):
    """
    Replace the count of the stat whose image alt text is `label`: both the
    data-count attribute and the visible number (shown without JavaScript).
    Matches: <img ... alt="LABEL" />
             <p class="stat-value" data-count="XX">X,XXX</p>

    Returns:
        tuple: (new_content, old_count), or (None, None) if not found
    """
    pattern = re.compile(
        rf'(<img[^>]*alt="{re.escape(label)}"[^>]*/>\s*<p[^>]*data-count=")(\d+)("[^>]*>)[^<]*',
        re.IGNORECASE,
    )
    match = pattern.search(content)
    if not match:
        return None, None
    new_content = pattern.sub(rf"\g<1>{new_count}\g<3>{new_count:,}", content, count=1)
    return new_content, int(match.group(2))


def apply_counts(content, counts):
    """
    Apply every fetched count to the index.html content.

    Returns:
        tuple: (new_content, list of "LABEL: old -> new" changes)
    """
    changes = []
    for label, new_count in counts.items():
        new_content, old_count = replace_count(content, label, new_count)
        if new_content is None:
            raise ValueError(f"Could not find {label} data-count in {INDEX_FILE}")
        if old_count != new_count:
            content = new_content
            changes.append(f"{label}: {old_count} -> {new_count}")
        else:
            print(f"✓ {label} unchanged ({new_count})")
    return content, changes


def update_local_file(file_path, counts):
    """Update the counters in a local index.html."""
    with open(file_path, "r") as f:
        content = f.read()

    new_content, changes = apply_counts(content, counts)
    if not changes:
        print("✓ Nothing to update")
        return

    with open(file_path, "w") as f:
        f.write(new_content)
    for change in changes:
        print(f"✓ Updated {change}")


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


def update_github_file(file_path, counts, token):
    """Update the counters in index.html on GitHub via the contents API."""
    try:
        current = github_request("GET", f"contents/{file_path}?ref={GITHUB_BRANCH}", token)
        content = base64.b64decode(current["content"]).decode("utf-8")

        new_content, changes = apply_counts(content, counts)
        if not changes:
            print("✓ Nothing to push")
            return

        github_request("PUT", f"contents/{file_path}", token, {
            "message": "🤖 Auto-update site stats\n\n" + "\n".join(changes),
            "content": base64.b64encode(new_content.encode("utf-8")).decode("ascii"),
            "sha": current["sha"],
            "branch": GITHUB_BRANCH,
        })
        for change in changes:
            print(f"✓ Pushed {change}")

    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub API error: HTTP {e.code} {e.reason}: "
                           f"{e.read().decode(errors='replace')[:300]}")


def main():
    """Main function"""
    push = "--push" in sys.argv[1:]

    print("=== Updating site stats ===")

    token = os.getenv("GITHUB_TOKEN")
    if push and not token:
        print("✗ --push needs a GITHUB_TOKEN environment variable")
        sys.exit(1)

    counts, failed = {}, []
    for label, fetch in STATS:
        try:
            counts[label] = fetch()
            print(f"✓ {label}: {counts[label]}")
        except Exception as e:
            print(f"✗ {label}: {e}")
            failed.append(label)

    if counts:
        try:
            if push:
                update_github_file(INDEX_FILE, counts, token)
            else:
                # Change to repository root directory
                script_dir = os.path.dirname(os.path.abspath(__file__))
                os.chdir(os.path.dirname(script_dir))
                update_local_file(INDEX_FILE, counts)
        except Exception as e:
            print(f"✗ {e}")
            sys.exit(1)

    if failed:
        print(f"✗ Failed to fetch: {', '.join(failed)}")
        sys.exit(1)
    print("=== Update Complete ===")


if __name__ == "__main__":
    main()
