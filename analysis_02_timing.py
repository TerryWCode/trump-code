#!/usr/bin/env python3
"""
Trump Code Analysis #2 - Posting Time Patterns
When does he post? What happens before and after frequency changes?
"""

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from utils import est_hour

BASE = Path(__file__).parent
DATA = BASE / "data"


def main():
    with open(BASE / "clean_president.json", 'r', encoding='utf-8') as f:
        posts = json.load(f)

    originals = [p for p in posts if p['has_text'] and not p['is_retweet']]

    print("=" * 70)
    print("⏰ Analysis #2: Posting Time Patterns")
    print(f"   Analysis Target: Original posts since inauguration - {len(originals)} posts")
    print("=" * 70)

    # --- 1. Hourly Distribution (UTC → EST conversion, Trump is on East Coast) ---
    hour_dist = Counter()
    hour_by_month = defaultdict(Counter)

    for p in originals:
        est_h, _ = est_hour(p['created_at'])
        hour_dist[est_h] += 1
        month = p['created_at'][:7]
        hour_by_month[month][est_h] += 1

    print(f"\n🕐 Posting Time Distribution (Eastern Time EST):")
    print("-" * 60)
    max_count = max(hour_dist.values())
    for h in range(24):
        count = hour_dist.get(h, 0)
        bar = '█' * int(count / max_count * 40) if max_count > 0 else ''
        period = "🌙" if h < 6 else ("☀️" if h < 12 else ("🌅" if h < 18 else "🌙"))
        print(f"  {h:02d}:00 {period} {count:4d} {bar}")

    # Late night posts (12am-5am EST)
    night_posts = [p for p in originals if est_hour(p['created_at'])[0] < 5]
    print(f"\n🌙 Late Night Posts (12am-5am EST): {len(night_posts)} posts ({len(night_posts)/len(originals)*100:.1f}%)")
    if night_posts:
        print("   Latest 5 late night posts:")
        for p in night_posts[:5]:
            est_h, est_m = est_hour(p['created_at'])
            print(f"   {p['created_at'][:16]} (EST {est_h}:{est_m:02d}) | {p['content'][:80]}...")

    # --- 2. Daily Post Volume ---
    print(f"\n📅 Daily Post Volume Distribution:")
    print("-" * 60)
    daily = Counter()
    for p in originals:
        daily[p['created_at'][:10]] += 1

    counts = sorted(daily.values())
    avg_daily = sum(counts) / len(counts)
    # P4-1: Empty value protection + P3-8: Use statistics.median for median
    median_count = median(counts) if counts else 0
    print(f"  Average per day: {avg_daily:.1f} posts")
    if counts:
        print(f"  Minimum: {counts[0]} posts")
        print(f"  Maximum: {counts[-1]} posts")
    print(f"  Median: {median_count} posts")

    # Top 10 most active days
    print(f"\n🔥 Top 10 Most Active Days:")
    for date, count in daily.most_common(10):
        # Look at first post that day for topic
        day_posts = [p for p in originals if p['created_at'][:10] == date]
        topic = day_posts[0]['content'][:60] if day_posts else ''
        bar = '█' * count
        print(f"  {date} | {count:3d} posts | {bar} | {topic}...")

    # Silent days (0 posts or very few)
    print(f"\n🤫 Silent Days (≤2 posts):")
    all_dates = sorted(daily.keys())
    quiet_days = [(d, daily[d]) for d in all_dates if daily[d] <= 2]
    print(f"  Total {len(quiet_days)} days")
    for d, c in quiet_days[-10:]:
        print(f"  {d} | {c} posts")

    # --- 3. Weekday Distribution ---
    print(f"\n📊 Weekday Distribution:")
    print("-" * 60)
    weekday_dist = Counter()
    weekday_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for p in originals:
        dt = datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))
        weekday_dist[dt.weekday()] += 1

    for wd in range(7):
        count = weekday_dist.get(wd, 0)
        bar = '█' * int(count / max(weekday_dist.values()) * 30)
        print(f"  {weekday_names[wd]} | {count:4d} {bar}")

    # --- 4. Post Interval Analysis ---
    print(f"\n⏱️ Post Interval Analysis:")
    print("-" * 60)
    intervals = []
    sorted_posts = sorted(originals, key=lambda p: p['created_at'])
    for i in range(1, len(sorted_posts)):
        dt1 = datetime.fromisoformat(sorted_posts[i-1]['created_at'].replace('Z', '+00:00'))
        dt2 = datetime.fromisoformat(sorted_posts[i]['created_at'].replace('Z', '+00:00'))
        diff_minutes = (dt2 - dt1).total_seconds() / 60
        intervals.append({
            'minutes': diff_minutes,
            'date': sorted_posts[i]['created_at'][:16],
            'content': sorted_posts[i]['content'][:60]
        })

    intervals_min = sorted([i['minutes'] for i in intervals])
    # P4-1: Empty value protection
    if not intervals_min:
        print("  No interval data")
        return

    print(f"  Shortest interval: {intervals_min[0]:.0f} minutes")
    print(f"  Longest interval: {intervals_min[-1]:.0f} minutes ({intervals_min[-1]/60:.1f} hours)")
    print(f"  Average interval: {sum(intervals_min)/len(intervals_min):.0f} minutes")
    # P3-8: Use statistics.median
    print(f"  Median interval: {median(intervals_min):.0f} minutes")

    # Rapid fire (multiple posts within 5 minutes)
    bursts = [i for i in intervals if i['minutes'] < 5]
    print(f"\n🔥 Rapid Fire (consecutive posts within 5 minutes): {len(bursts)} times")

    # First post after long silence (silence > 12 hours)
    long_silence = [i for i in intervals if i['minutes'] > 720]
    print(f"\n😶 First Post After Long Silence (>12 hours): {len(long_silence)} times")
    for item in long_silence[:10]:
        hours = item['minutes'] / 60
        print(f"  Silent {hours:.1f}h → {item['date']} | {item['content']}...")

    # --- 5. Post Volume Trend (Weekly) ---
    print(f"\n📈 Weekly Post Volume Trend:")
    print("-" * 60)
    weekly = defaultdict(int)
    for p in originals:
        dt = datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))
        # ISO week
        year, week, _ = dt.isocalendar()
        key = f"{year}-W{week:02d}"
        weekly[key] += 1

    weeks = sorted(weekly.keys())
    for w in weeks[-16:]:  # Latest 16 weeks
        count = weekly[w]
        bar = '█' * (count // 2)
        print(f"  {w} | {count:3d} {bar}")

    # Save results
    results = {
        'hourly_distribution_est': dict(hour_dist),
        'daily_counts': dict(daily.most_common()),
        'weekday_distribution': {weekday_names[k]: v for k, v in weekday_dist.items()},
        'night_posts_count': len(night_posts),
        'burst_count': len(bursts),
        'long_silence_count': len(long_silence),
        'avg_daily': round(avg_daily, 1),
        'avg_interval_minutes': round(sum(intervals_min)/len(intervals_min), 0),
    }
    with open(DATA / 'results_02_timing.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Detailed results saved to results_02_timing.json")


if __name__ == '__main__':
    main()


