#!/usr/bin/env python3
"""
Trump Code Analysis #4 - People & Country Mentions Analysis
Who does he mention, what countries, frequency changes = bellwether
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"


def main():
    with open(BASE / "clean_president.json", 'r', encoding='utf-8') as f:
        posts = json.load(f)

    originals = [p for p in posts if p['has_text'] and not p['is_retweet']]

    print("=" * 70)
    print("🌍 Analysis #4: People & Country Mentions Analysis")
    print(f"   Analysis Target: Original posts since inauguration - {len(originals)} posts")
    print("=" * 70)

    # --- 1. Country/Region Mention Frequency ---
    # P3-7: Remove trailing space from 'EU' (avoid false matches), 'Korean' → 'South Korean'/'South Korea'
    # Remove 'Border' from Mexico (Border is a general border policy term, not specific to Mexico)
    countries = {
        'China': ['China', 'Chinese', 'Beijing', 'Xi', 'Jinping', 'CCP'],
        'Japan': ['Japan', 'Japanese', 'Tokyo', 'Kishida', 'Ishiba'],
        'Russia': ['Russia', 'Russian', 'Putin', 'Moscow', 'Kremlin'],
        'Ukraine': ['Ukraine', 'Ukrainian', 'Zelensky', 'Zelenskyy', 'Kiev', 'Kyiv'],
        'Iran': ['Iran', 'Iranian', 'Tehran', 'Khamenei'],
        'North Korea': ['North Korea', 'DPRK', 'Kim Jong', 'Pyongyang'],
        'Israel': ['Israel', 'Israeli', 'Netanyahu', 'Bibi', 'Gaza', 'Hamas', 'Hezbollah'],
        'Mexico': ['Mexico', 'Mexican', 'Cartels'],
        'Canada': ['Canada', 'Canadian', 'Trudeau', 'Ottawa'],
        'Europe/EU': ['Europe', 'European', 'EU', 'NATO', 'Brussels'],
        'UK': ['Britain', 'British', 'England', 'London', 'Starmer'],
        'India': ['India', 'Indian', 'Modi', 'Delhi'],
        'Taiwan': ['Taiwan', 'Taiwanese', 'Taipei'],
        'Saudi Arabia': ['Saudi', 'Arabia', 'Riyadh', 'MBS'],
        'South Korea': ['South Korea', 'South Korean', 'Seoul'],
    }

    country_counts = {}
    country_monthly = defaultdict(lambda: defaultdict(int))

    for country, keywords in countries.items():
        count = 0
        for p in originals:
            content = p['content']
            if any(kw.lower() in content.lower() for kw in keywords):
                count += 1
                month = p['created_at'][:7]
                country_monthly[country][month] += 1
        country_counts[country] = count

    print(f"\n🌐 Country/Region Mentions:")
    print("-" * 60)
    for country, count in sorted(country_counts.items(), key=lambda x: -x[1]):
        bar = '█' * (count // 3)
        print(f"  {country:15s} | {count:4d} posts {bar}")

    # Country mention monthly trend (Top 6 countries)
    top_countries = sorted(country_counts.items(), key=lambda x: -x[1])[:6]
    print(f"\n📈 Top 6 Countries Monthly Trend:")
    print("-" * 60)
    all_months = sorted(set(p['created_at'][:7] for p in originals))
    header = f"  {'Month':10s}"
    for c, _ in top_countries:
        header += f" {c[:6]:>7s}"
    print(header)

    for month in all_months:
        row = f"  {month:10s}"
        for c, _ in top_countries:
            val = country_monthly[c].get(month, 0)
            row += f" {val:7d}"
        print(row)

    # --- 2. People Mentions ---
    people = {
        'Biden': ['Biden', 'Joe Biden', 'Sleepy Joe'],
        'Obama': ['Obama', 'Barack'],
        'Pelosi': ['Pelosi', 'Nancy'],
        'Schumer': ['Schumer', 'Chuck Schumer'],
        'DeSantis': ['DeSantis', 'Ron DeSantis', 'DeSanctimonious'],
        'Elon Musk': ['Elon', 'Musk', 'Tesla', 'DOGE'],
        'Vivek': ['Vivek', 'Ramaswamy'],
        'Kamala': ['Kamala', 'Harris'],
        'Pence': ['Pence', 'Mike Pence'],
        'McConnell': ['McConnell', 'Mitch'],
        'RFK Jr': ['Kennedy', 'RFK'],
        'Vance': ['Vance', 'J.D.', 'JD Vance'],
        'Jack Smith': ['Jack Smith', 'Special Counsel'],
        'Putin': ['Putin', 'Vladimir'],
        'Xi Jinping': ['Xi Jinping', 'Xi '],
        'Zelensky': ['Zelensky', 'Zelenskyy'],
        'Kim Jong Un': ['Kim Jong'],
        'Netanyahu': ['Netanyahu', 'Bibi'],
    }

    people_counts = {}
    people_monthly = defaultdict(lambda: defaultdict(int))

    for person, keywords in people.items():
        count = 0
        for p in originals:
            content = p['content']
            if any(kw.lower() in content.lower() for kw in keywords):
                count += 1
                month = p['created_at'][:7]
                people_monthly[person][month] += 1
        people_counts[person] = count

    print(f"\n👤 People Mentions:")
    print("-" * 60)
    for person, count in sorted(people_counts.items(), key=lambda x: -x[1]):
        if count > 0:
            bar = '█' * min(count // 2, 40)
            print(f"  {person:15s} | {count:4d} posts {bar}")

    # --- 3. Nickname/Label Tracking ---
    print(f"\n🏷️ Trump Signature Nicknames Tracking:")
    print("-" * 60)

    nicknames = [
        'Sleepy Joe', 'Crooked', 'Crazy', 'Radical Left', 'Fake News',
        'RINO', 'Deep State', 'Witch Hunt', 'Enemy of the People',
        'Do Nothing', 'Low Energy', 'Lyin\'', 'Shifty', 'Nervous',
        'Deranged', 'Failing', 'Phony', 'Corrupt', 'Lunatic',
        'Incompetent', 'Stupid', 'DeSanctimonious', 'Comrade',
        'Laughing', 'Loco', 'Wacko', 'Liddle', 'Mini', 'Sloppy',
    ]

    nickname_counts = {}
    for nick in nicknames:
        count = sum(1 for p in originals if nick.lower() in p['content'].lower())
        if count > 0:
            nickname_counts[nick] = count

    for nick, count in sorted(nickname_counts.items(), key=lambda x: -x[1]):
        bar = '█' * min(count, 30)
        print(f"  {nick:25s} | {count:4d} {bar}")

    # --- 4. Policy Keywords ---
    print(f"\n📋 Policy Keyword Frequency:")
    print("-" * 60)

    topics = {
        'Tariff': ['tariff', 'tariffs', 'duty', 'duties'],
        'Border': ['border', 'wall', 'immigration', 'migrant', 'deportation', 'deport'],
        'Economy': ['economy', 'economic', 'inflation', 'gdp', 'recession', 'growth'],
        'Trade': ['trade', 'trade deal', 'trade deficit', 'export', 'import'],
        'Military': ['military', 'army', 'navy', 'troops', 'defense', 'defence'],
        'Energy': ['energy', 'oil', 'gas', 'drill', 'pipeline', 'opec'],
        'Tech': ['technology', 'tech', 'artificial intelligence', ' ai ', 'chips', 'semiconductor'],
        'Crime': ['crime', 'criminal', 'gang', 'ms-13', 'fentanyl', 'drugs'],
        'Election': ['election', 'vote', 'voter', 'ballot', 'poll'],
        'Tax': ['tax', 'taxes', 'irs', 'tax cut'],
        'Jobs': ['jobs', 'employment', 'unemployment', 'workers', 'hiring'],
        'Stock Market': ['stock market', 'dow', 'nasdaq', 'wall street', 's&p'],
    }

    topic_counts = {}
    topic_monthly = defaultdict(lambda: defaultdict(int))

    for topic, keywords in topics.items():
        count = 0
        for p in originals:
            cl = p['content'].lower()
            if any(kw in cl for kw in keywords):
                count += 1
                month = p['created_at'][:7]
                topic_monthly[topic][month] += 1
        topic_counts[topic] = count

    for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
        bar = '█' * (count // 3)
        print(f"  {topic:20s} | {count:4d} posts {bar}")

    # Topic monthly trend
    print(f"\n📈 Topic Monthly Trend (Top 6):")
    print("-" * 60)
    top_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:6]
    header = f"  {'Month':10s}"
    for t, _ in top_topics:
        header += f" {t[:8]:>9s}"
    print(header)

    for month in all_months:
        row = f"  {month:10s}"
        for t, _ in top_topics:
            val = topic_monthly[t].get(month, 0)
            row += f" {val:9d}"
        print(row)

    # Save results
    results = {
        'country_counts': country_counts,
        'country_monthly': {k: dict(v) for k, v in country_monthly.items()},
        'people_counts': people_counts,
        'people_monthly': {k: dict(v) for k, v in people_monthly.items()},
        'nickname_counts': nickname_counts,
        'topic_counts': topic_counts,
        'topic_monthly': {k: dict(v) for k, v in topic_monthly.items()},
    }
    with open(DATA / 'results_04_entities.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Detailed results saved to results_04_entities.json")


if __name__ == '__main__':
    main()


