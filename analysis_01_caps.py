#!/usr/bin/env python3
"""
Trump Code Analysis #1 - CAPS Pattern Analysis
Trump deliberately capitalizes certain words. Extract and analyze them for patterns.
"""

import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"


def main():
    with open(BASE / "clean_president.json", 'r', encoding='utf-8') as f:
        posts = json.load(f)

    # Only look at original posts with text (not retweets)
    originals = [p for p in posts if p['has_text'] and not p['is_retweet']]

    print("=" * 70)
    print("Analysis #1: CAPS Pattern")
    print(f"   Analyzing: {len(originals)} original posts since inauguration")
    print("=" * 70)

    # --- 1. Extract all deliberately capitalized words (exclude common ones like I, A, OK) ---
    common_caps = {'I', 'A', 'OK', 'II', 'III', 'IV', 'V', 'US', 'AM', 'PM',
                   'RT', 'TV', 'DC', 'NY', 'TX', 'FL', 'CA', 'OH', 'GA',
                   'GOP', 'USA', 'CEO', 'FBI', 'CIA', 'DOJ', 'DHS', 'ICE',
                   'NATO', 'UN', 'EU', 'UK', 'GDP', 'GPA', 'PhD', 'MD',
                   'LLC', 'INC', 'CO', 'JR', 'SR', 'DR', 'MR', 'MRS', 'MS',
                   'THE', 'AND', 'FOR', 'BUT', 'NOT', 'ARE', 'HAS', 'HAD',
                   'HIS', 'HER', 'OUR', 'WAS', 'DID', 'LNG', 'TN', 'AI',
                   'OF', 'IN', 'TO', 'ON', 'AT', 'BY', 'AN', 'OR', 'IF',
                   'IT', 'IS', 'BE', 'DO', 'NO', 'SO', 'UP', 'AS', 'WE',
                   'MY', 'HE', 'ME', 'ID', 'VS', 'DJ', 'DJT', 'P'}

    all_caps_words = Counter()
    caps_by_post = []  # (date, [list of CAPS words])
    caps_timeline = []  # time series

    for p in originals:
        content = p['content']
        # Find all CAPS words (2+ chars, exclude common ones)
        words = re.findall(r'\b([A-Z]{2,})\b', content)
        deliberate = [w for w in words if w not in common_caps and len(w) >= 3]

        if deliberate:
            all_caps_words.update(deliberate)
            caps_by_post.append({
                'date': p['created_at'][:10],
                'caps': deliberate,
                'first_letters': ''.join([w[0] for w in deliberate]),
                'content_preview': content[:100]
            })
            caps_timeline.append({
                'date': p['created_at'][:10],
                'count': len(deliberate),
                'words': deliberate
            })

    print(f"\nTotal deliberate CAPS words found: {sum(all_caps_words.values())}")
    print(f"   Unique words: {len(all_caps_words)} types")
    print(f"   Posts with CAPS: {len(caps_by_post)} / {len(originals)} posts")

    print(f"\nTop 50 most common CAPS words:")
    print("-" * 50)
    for word, count in all_caps_words.most_common(50):
        bar = '█' * min(count, 40)
        print(f"  {word:25s} {count:4d} {bar}")

    # --- 2. First letter patterns (string together first letters) ---
    print(f"\nFirst Letter Patterns (from CAPS words in each post):")
    print("-" * 50)
    # Last 30 posts with CAPS
    for item in caps_by_post[:30]:
        print(f"  {item['date']} | First letters: {item['first_letters']:20s} | CAPS words: {', '.join(item['caps'][:5])}")

    # --- 3. CAPS usage frequency over time ---
    print(f"\nMonthly CAPS usage density:")
    print("-" * 50)
    monthly = {}
    for item in caps_timeline:
        month = item['date'][:7]
        if month not in monthly:
            monthly[month] = {'count': 0, 'posts': 0}
        monthly[month]['count'] += item['count']
        monthly[month]['posts'] += 1

    # Calculate total original posts per month
    monthly_total = {}
    for p in originals:
        m = p['created_at'][:7]
        monthly_total[m] = monthly_total.get(m, 0) + 1

    for month in sorted(monthly.keys()):
        total = monthly_total.get(month, 1)
        avg = monthly[month]['count'] / monthly[month]['posts']
        density = monthly[month]['posts'] / total * 100
        bar = '█' * int(avg * 2)
        print(f"  {month} | {monthly[month]['posts']:3d} posts with CAPS / {total:3d} total ({density:.0f}%) | Avg {avg:.1f} per post {bar}")

    # --- 4. Sentiment classification of CAPS words ---
    print(f"\nCAPS word sentiment classification:")
    print("-" * 50)
    positive = ['GREAT', 'MASSIVE', 'TREMENDOUS', 'BEAUTIFUL', 'INCREDIBLE',
                'AMAZING', 'WONDERFUL', 'HISTORIC', 'PERFECT', 'FANTASTIC',
                'MAGNIFICENT', 'EXTRAORDINARY', 'SPECTACULAR', 'BRILLIANT',
                'WINNING', 'VICTORY', 'SUCCESS', 'LOVE', 'BEST', 'STRONG',
                'POWERFUL', 'PROUD', 'HAPPY', 'BLESSED', 'GREAT']
    negative = ['FAKE', 'CORRUPT', 'RADICAL', 'TERRIBLE', 'HORRIBLE',
                'WORST', 'FAILED', 'CROOKED', 'BROKEN', 'DISASTER',
                'DISGRACE', 'INCOMPETENT', 'PATHETIC', 'WEAK', 'STUPID',
                'RIGGED', 'WITCH', 'HOAX', 'SCAM', 'FRAUD', 'ENEMY',
                'ILLEGAL', 'EVIL', 'DANGEROUS', 'DESTROY']
    action = ['MAGA', 'AMERICA', 'FIRST', 'FIGHT', 'VOTE', 'WIN',
              'BUILD', 'SAVE', 'STOP', 'FIRE', 'BAN', 'TARIFF',
              'TARIFFS', 'DEAL', 'TRUMP', 'REVITALIZE']

    pos_count = sum(all_caps_words.get(w, 0) for w in positive)
    neg_count = sum(all_caps_words.get(w, 0) for w in negative)
    act_count = sum(all_caps_words.get(w, 0) for w in action)

    print(f"  Positive words (GREAT, WINNING...):  {pos_count:4d} times")
    print(f"  Negative words (FAKE, CORRUPT...):   {neg_count:4d} times")
    print(f"  Action words (MAGA, TARIFFS...):     {act_count:4d} times")
    print(f"  Positive/Negative ratio:             {pos_count/max(neg_count,1):.1f}:1")

    # --- 5. Arrange all CAPS words chronologically for hidden messages ---
    print(f"\nLast 7 days of CAPS words (chronological):")
    print("-" * 50)
    recent_days = sorted(set(item['date'] for item in caps_by_post))[-7:]
    for day in recent_days:
        day_caps = []
        for item in caps_by_post:
            if item['date'] == day:
                day_caps.extend(item['caps'])
        print(f"  {day}: {' '.join(day_caps[:20])}")

    # Save results
    results = {
        'top_caps_words': dict(all_caps_words.most_common(100)),
        'caps_by_post': caps_by_post[:100],
        'monthly_density': {m: {'caps_posts': v['posts'], 'total_posts': monthly_total.get(m, 0),
                                'total_caps': v['count']}
                           for m, v in monthly.items()},
        'sentiment': {'positive': pos_count, 'negative': neg_count, 'action': act_count},
    }
    with open(DATA / 'results_01_caps.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDetailed results saved to results_01_caps.json")


if __name__ == '__main__':
    main()

