#!/usr/bin/env python3
"""
Simple Trump Post Fetcher - Gets latest posts from Truth Social
Runs once and updates trump_posts_all.json with new posts

Usage:
  python fetch_new_posts.py              # Fetch once and exit
  python fetch_new_posts.py --loop       # Keep running, fetch every 5 minutes
"""

import json
import sys
import time
import urllib.request
import csv
import ssl
from datetime import datetime, timezone
from pathlib import Path

# Disable SSL verification (for demo purposes)
ssl._create_default_https_context = ssl._create_unverified_context

BASE = Path(__file__).parent
DATA = BASE / "data"
POSTS_FILE = DATA / "trump_posts_all.json"
ARCHIVE_URL = "https://ix.cnn.io/data/truth-social/truth_archive.csv"
LOOP_MODE = "--loop" in sys.argv


def log(msg):
    """Print timestamped message"""
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] {msg}")


def fetch_latest_from_archive(limit=50):
    """Fetch latest posts from CNN Truth Social archive"""
    log(f"Fetching from {ARCHIVE_URL}...")

    try:
        req = urllib.request.Request(ARCHIVE_URL, headers={
            'User-Agent': 'TrumpAnalyzer/1.0'
        })

        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read().decode('utf-8')

        # Parse CSV
        lines = data.strip().split('\n')
        reader = csv.DictReader(lines)

        posts = []
        for row in reader:
            post = {
                'id': row.get('id', ''),
                'created_at': row.get('created_at', ''),
                'content': row.get('content', ''),
                'url': row.get('url', ''),
                'source': 'truth_social_archive',
                'is_retweet': row.get('is_retweet', 'false').lower() == 'true'
            }
            posts.append(post)

            if len(posts) >= limit:
                break

        log(f"Fetched {len(posts)} posts from archive")
        return posts

    except Exception as e:
        log(f"ERROR fetching archive: {e}")
        return []


def load_existing_posts():
    """Load existing posts from data file"""
    if not POSTS_FILE.exists():
        log("No existing posts file found")
        return {'posts': [], 'total': 0}

    try:
        with open(POSTS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, dict) and 'posts' in data:
            log(f"Loaded {len(data['posts'])} existing posts")
            return data
        elif isinstance(data, list):
            log(f"Loaded {len(data)} existing posts (old format)")
            return {'posts': data, 'total': len(data)}
        else:
            log("Invalid data format")
            return {'posts': [], 'total': 0}

    except Exception as e:
        log(f"ERROR loading existing posts: {e}")
        return {'posts': [], 'total': 0}


def merge_and_save_posts(new_posts):
    """Merge new posts with existing and save"""

    # Load existing
    data = load_existing_posts()
    existing_posts = data.get('posts', [])

    # Create set of existing IDs for deduplication
    existing_ids = {p.get('id') for p in existing_posts if p.get('id')}

    # Add new posts that don't exist
    added = 0
    for post in new_posts:
        post_id = post.get('id')
        if post_id and post_id not in existing_ids:
            existing_posts.insert(0, post)  # Add to beginning (newest first)
            existing_ids.add(post_id)
            added += 1

    # Sort by date (newest first)
    existing_posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    # Save
    data['posts'] = existing_posts
    data['total'] = len(existing_posts)
    data['last_updated'] = datetime.now(timezone.utc).isoformat()

    try:
        with open(POSTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        log(f"Saved {added} new posts (total: {len(existing_posts)})")

        if added > 0:
            latest = existing_posts[0]
            log(f"Latest post: {latest.get('created_at', '?')} - {latest.get('content', '')[:80]}...")

        return added

    except Exception as e:
        log(f"ERROR saving posts: {e}")
        return 0


def main():
    """Main function"""
    log("=" * 60)
    log("Trump Post Fetcher")
    log("=" * 60)

    if LOOP_MODE:
        log("Running in LOOP mode (fetches every 5 minutes)")
        log("Press Ctrl+C to stop\n")

        try:
            while True:
                new_posts = fetch_latest_from_archive(limit=50)
                if new_posts:
                    added = merge_and_save_posts(new_posts)
                    if added == 0:
                        log("No new posts found")

                log("Waiting 5 minutes...\n")
                time.sleep(300)  # 5 minutes

        except KeyboardInterrupt:
            log("\nStopped by user")

    else:
        log("Running ONCE mode (fetch and exit)\n")
        new_posts = fetch_latest_from_archive(limit=50)

        if new_posts:
            added = merge_and_save_posts(new_posts)
            log(f"\nDone! Added {added} new posts")
        else:
            log("\nNo posts fetched")


if __name__ == '__main__':
    main()
