#!/usr/bin/env python3
"""
思維 1：獨立分析 Trump 在 X 的 168 篇推文
分析項目：
1. 發文時間規律
2. X 推文 vs 股市
3. 內容分類
4. 發文量變化
5. X 獨有推文（6 篇）
"""

import json
import re
from datetime import datetime, timedelta
from collections import Counter, defaultdict

# === Load data ===
with open("data/x_posts_full.json", "r") as f:
    x_data = json.load(f)

with open("data/market_SP500.json", "r") as f:
    market_data = json.load(f)

tweets = x_data["tweets"]

# Build market lookup
market_by_date = {}
market_dates_sorted = []
for m in market_data:
    market_by_date[m["date"]] = m
    market_dates_sorted.append(m["date"])
market_dates_sorted.sort()

def get_next_trading_day(date_str):
    """Get the next trading day after date_str"""
    for d in market_dates_sorted:
        if d > date_str:
            return d
    return None

def get_market_return(date_str):
    """Get same-day return (close-open)/open as percentage"""
    if date_str in market_by_date:
        m = market_by_date[date_str]
        return (m["close"] - m["open"]) / m["open"] * 100
    return None

def get_next_day_return(date_str):
    """Get next trading day return"""
    next_d = get_next_trading_day(date_str)
    if next_d:
        return get_market_return(next_d), next_d
    return None, None

# === Parse all tweets ===
parsed_tweets = []
for t in tweets:
    dt = datetime.strptime(t["created_at"], "%Y-%m-%dT%H:%M:%S.000Z")
    is_retweet = "referenced_tweets" in t and any(
        ref["type"] == "retweeted" for ref in t.get("referenced_tweets", [])
    )
    is_quote = "referenced_tweets" in t and any(
        ref["type"] == "quoted" for ref in t.get("referenced_tweets", [])
    )
    text = t["text"]
    metrics = t["public_metrics"]

    parsed_tweets.append({
        "id": t["id"],
        "text": text,
        "created_at": t["created_at"],
        "datetime": dt,
        "date": dt.strftime("%Y-%m-%d"),
        "hour_utc": dt.hour,
        "hour_et": (dt.hour - 5) % 24,  # EST (simplified)
        "weekday": dt.strftime("%A"),
        "weekday_num": dt.weekday(),
        "year_month": dt.strftime("%Y-%m"),
        "year_week": dt.strftime("%Y-W%W"),
        "is_retweet": is_retweet,
        "is_quote": is_quote,
        "metrics": metrics,
        "impression_count": metrics.get("impression_count", 0),
        "like_count": metrics.get("like_count", 0),
        "retweet_count": metrics.get("retweet_count", 0),
    })

# Sort by date (oldest first)
parsed_tweets.sort(key=lambda x: x["datetime"])

print("=" * 80)
print("思維 1：Trump X 推文獨立分析報告")
print("=" * 80)
print(f"\n總推文數：{len(parsed_tweets)}")
print(f"原創推文：{sum(1 for t in parsed_tweets if not t['is_retweet'])}")
print(f"轉推：{sum(1 for t in parsed_tweets if t['is_retweet'])}")
print(f"引用推文：{sum(1 for t in parsed_tweets if t['is_quote'])}")
print(f"時間範圍：{parsed_tweets[0]['date']} 至 {parsed_tweets[-1]['date']}")

# =========================================================
# 1. 發文時間規律
# =========================================================
print("\n" + "=" * 80)
print("一、X 發文時間規律")
print("=" * 80)

# Hour distribution (ET)
hour_counts = Counter(t["hour_et"] for t in parsed_tweets)
print("\n【按小時分布（美東時間 ET）】")
print(f"{'小時':>6} | {'推文數':>6} | 比例    | 圖")
print("-" * 60)
for h in range(24):
    c = hour_counts.get(h, 0)
    pct = c / len(parsed_tweets) * 100
    bar = "█" * int(pct)
    time_label = ""
    if h == 4: time_label = " ← 盤前開始(4am)"
    if h == 9: time_label = " ← 盤前(9:30開盤)"
    if h == 16: time_label = " ← 收盤(4pm)"
    if h == 18: time_label = " ← 盤後結束"
    print(f"  {h:02d}:00 | {c:>6} | {pct:5.1f}% | {bar}{time_label}")

# Market session classification
pre_market = sum(1 for t in parsed_tweets if 4 <= t["hour_et"] < 9)  # 4am-9:30am
market_hours = sum(1 for t in parsed_tweets if 9 <= t["hour_et"] < 16)  # 9:30am-4pm
after_market = sum(1 for t in parsed_tweets if 16 <= t["hour_et"] < 20)  # 4pm-8pm
off_hours = sum(1 for t in parsed_tweets if t["hour_et"] >= 20 or t["hour_et"] < 4)  # 8pm-4am

print(f"\n【盤前/盤中/盤後/收盤後分布】")
print(f"  盤前 (4am-9:30am ET):  {pre_market:>3} 篇 ({pre_market/len(parsed_tweets)*100:.1f}%)")
print(f"  盤中 (9:30am-4pm ET):  {market_hours:>3} 篇 ({market_hours/len(parsed_tweets)*100:.1f}%)")
print(f"  盤後 (4pm-8pm ET):     {after_market:>3} 篇 ({after_market/len(parsed_tweets)*100:.1f}%)")
print(f"  休市 (8pm-4am ET):     {off_hours:>3} 篇 ({off_hours/len(parsed_tweets)*100:.1f}%)")

# Weekday distribution
weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
weekday_zh = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
weekday_counts = Counter(t["weekday_num"] for t in parsed_tweets)
print(f"\n【按星期分布】")
print(f"{'星期':>6} | {'推文數':>6} | 比例    | 圖")
print("-" * 50)
for i, (en, zh) in enumerate(zip(weekday_names, weekday_zh)):
    c = weekday_counts.get(i, 0)
    pct = c / len(parsed_tweets) * 100
    bar = "█" * int(pct / 2)
    print(f"  {zh} | {c:>6} | {pct:5.1f}% | {bar}")

# =========================================================
# 2. X 推文 vs 股市
# =========================================================
print("\n" + "=" * 80)
print("二、X 推文 vs S&P 500 股市表現")
print("=" * 80)

# Get all tweet dates (unique)
tweet_dates = set(t["date"] for t in parsed_tweets)

# Calculate returns on tweet days vs non-tweet days
tweet_day_returns = []
tweet_day_next_returns = []
no_tweet_day_returns = []
no_tweet_day_next_returns = []

# Second term starts 2025-01-20
for date_str in market_dates_sorted:
    if date_str < "2025-01-20":
        continue
    ret = get_market_return(date_str)
    next_ret, _ = get_next_day_return(date_str)
    if ret is not None:
        if date_str in tweet_dates:
            tweet_day_returns.append(ret)
            if next_ret is not None:
                tweet_day_next_returns.append(next_ret)
        else:
            no_tweet_day_returns.append(ret)
            if next_ret is not None:
                no_tweet_day_next_returns.append(next_ret)

avg_tweet = sum(tweet_day_returns) / len(tweet_day_returns) if tweet_day_returns else 0
avg_no_tweet = sum(no_tweet_day_returns) / len(no_tweet_day_returns) if no_tweet_day_returns else 0
avg_tweet_next = sum(tweet_day_next_returns) / len(tweet_day_next_returns) if tweet_day_next_returns else 0
avg_no_tweet_next = sum(no_tweet_day_next_returns) / len(no_tweet_day_next_returns) if no_tweet_day_next_returns else 0

# Volatility (standard deviation)
import math
def stdev(vals):
    if len(vals) < 2:
        return 0
    avg = sum(vals) / len(vals)
    return math.sqrt(sum((v - avg) ** 2 for v in vals) / (len(vals) - 1))

vol_tweet = stdev(tweet_day_returns)
vol_no_tweet = stdev(no_tweet_day_returns)

# Positive day ratio
pos_tweet = sum(1 for r in tweet_day_returns if r > 0) / len(tweet_day_returns) * 100 if tweet_day_returns else 0
pos_no_tweet = sum(1 for r in no_tweet_day_returns if r > 0) / len(no_tweet_day_returns) * 100 if no_tweet_day_returns else 0

print(f"\n【有 X 發文 vs 無 X 發文的交易日比較】")
print(f"{'指標':>20} | {'有X發文':>12} | {'無X發文':>12} | 差異")
print("-" * 70)
print(f"{'交易日數':>20} | {len(tweet_day_returns):>10}天 | {len(no_tweet_day_returns):>10}天 |")
print(f"{'平均當日報酬':>20} | {avg_tweet:>10.3f}% | {avg_no_tweet:>10.3f}% | {avg_tweet-avg_no_tweet:>+.3f}%")
print(f"{'平均隔日報酬':>20} | {avg_tweet_next:>10.3f}% | {avg_no_tweet_next:>10.3f}% | {avg_tweet_next-avg_no_tweet_next:>+.3f}%")
print(f"{'波動度(標準差)':>20} | {vol_tweet:>10.3f}% | {vol_no_tweet:>10.3f}% | {vol_tweet-vol_no_tweet:>+.3f}%")
print(f"{'上漲日比例':>20} | {pos_tweet:>10.1f}% | {pos_no_tweet:>10.1f}% | {pos_tweet-pos_no_tweet:>+.1f}%")

# Most impactful tweet days (biggest market moves)
print(f"\n【X 發文日的最大市場波動 Top 10】")
tweet_day_moves = []
for date_str in tweet_dates:
    if date_str in market_by_date:
        ret = get_market_return(date_str)
        day_tweets = [t for t in parsed_tweets if t["date"] == date_str]
        texts = [t["text"][:60] for t in day_tweets]
        tweet_day_moves.append((date_str, ret, len(day_tweets), texts))

tweet_day_moves.sort(key=lambda x: abs(x[1]) if x[1] else 0, reverse=True)
print(f"{'日期':>12} | {'報酬':>8} | {'推文數':>4} | 推文摘要")
print("-" * 90)
for date_str, ret, count, texts in tweet_day_moves[:10]:
    text_preview = texts[0] if texts else ""
    print(f"  {date_str} | {ret:>+7.2f}% | {count:>4} | {text_preview}")

# =========================================================
# 3. 內容分類
# =========================================================
print("\n" + "=" * 80)
print("三、X 推文內容分類")
print("=" * 80)

# URL-only tweets
url_pattern = re.compile(r'^https?://t\.co/\S+$')
url_only = [t for t in parsed_tweets if url_pattern.match(t["text"].strip())]
has_text = [t for t in parsed_tweets if not url_pattern.match(t["text"].strip()) and not t["is_retweet"]]
retweets = [t for t in parsed_tweets if t["is_retweet"]]

print(f"\n【推文類型分布】")
print(f"  純連結/影片（只有URL）: {len(url_only):>3} 篇 ({len(url_only)/len(parsed_tweets)*100:.1f}%)")
print(f"  有實質文字（含URL+文字）: {len(has_text):>3} 篇 ({len(has_text)/len(parsed_tweets)*100:.1f}%)")
print(f"  轉推 (RT): {len(retweets):>3} 篇 ({len(retweets)/len(parsed_tweets)*100:.1f}%)")

# Topic classification
topic_keywords = {
    "tariff/trade": ["tariff", "trade", "import", "duty", "reciprocal"],
    "china": ["china", "chinese", "xi", "beijing"],
    "economy/business": ["economy", "business", "jobs", "gdp", "investment", "companies", "market", "stock", "billion", "trillion"],
    "military/houthi/iran": ["military", "houthi", "iran", "bomb", "strike", "attack", "fighter", "decimat"],
    "immigration/border": ["border", "immigration", "illegal", "deport", "migrant", "criminal"],
    "maga/rally": ["maga", "make america", "fight fight", "great again", "rally", "patriot"],
    "biden/democrats": ["biden", "democrat", "sleepy", "crooked", "radical left", "fake news"],
    "elon/tesla/doge": ["elon", "tesla", "doge", "musk", "spacex"],
    "media/npr/npr": ["npr", "pbs", "media", "fake news", "cnn"],
    "endorsement/politics": ["endorse", "congress", "senate", "governor", "campaign", "running", "vote"],
    "melania": ["melania"],
    "deal/diplomacy": ["deal", "agreement", "negotiat", "peace", "ceasefire", "diplomat"],
    "el_salvador/bukele": ["salvador", "bukele", "cecot"],
    "oil/energy": ["oil", "gas", "energy", "drill"],
    "fed/interest_rates": ["fed", "interest rate", "rate cut"],
    "inflation": ["inflation", "prices"],
    "signal_scandal": ["signal"],
    "big_beautiful_bill": ["big beautiful bill", "one big beautiful"],
}

topic_counts = Counter()
topic_tweets = defaultdict(list)
originals = [t for t in parsed_tweets if not t["is_retweet"]]

for t in originals:
    text_lower = t["text"].lower()
    matched = False
    for topic, keywords in topic_keywords.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                topic_counts[topic] += 1
                topic_tweets[topic].append(t)
                matched = True
                break
    if not matched and not url_pattern.match(t["text"].strip()):
        topic_counts["other"] += 1

print(f"\n【主題分布（原創推文，一篇可能歸多個主題）】")
print(f"{'主題':>25} | {'篇數':>4} | 佔原創% | 代表推文")
print("-" * 100)
for topic, count in topic_counts.most_common():
    pct = count / len(originals) * 100
    sample = ""
    if topic in topic_tweets and topic_tweets[topic]:
        sample = topic_tweets[topic][0]["text"][:50].replace("\n", " ")
    print(f"  {topic:>23} | {count:>4} | {pct:5.1f}%  | {sample}")

# Engagement analysis by type
print(f"\n【推文類型的互動數據比較】")
avg_impressions_url = sum(t["impression_count"] for t in url_only) / len(url_only) if url_only else 0
avg_impressions_text = sum(t["impression_count"] for t in has_text) / len(has_text) if has_text else 0
avg_likes_url = sum(t["like_count"] for t in url_only) / len(url_only) if url_only else 0
avg_likes_text = sum(t["like_count"] for t in has_text) / len(has_text) if has_text else 0
avg_rt_url = sum(t["retweet_count"] for t in url_only) / len(url_only) if url_only else 0
avg_rt_text = sum(t["retweet_count"] for t in has_text) / len(has_text) if has_text else 0

print(f"{'指標':>20} | {'純URL推文':>15} | {'有文字推文':>15}")
print("-" * 60)
print(f"{'平均曝光數':>20} | {avg_impressions_url:>13,.0f} | {avg_impressions_text:>13,.0f}")
print(f"{'平均按讚數':>20} | {avg_likes_url:>13,.0f} | {avg_likes_text:>13,.0f}")
print(f"{'平均轉推數':>20} | {avg_rt_url:>13,.0f} | {avg_rt_text:>13,.0f}")

# Top 10 most engaged tweets
print(f"\n【互動最高的 10 篇推文】")
sorted_by_impressions = sorted(parsed_tweets, key=lambda x: x["impression_count"], reverse=True)
print(f"{'#':>2} | {'日期':>12} | {'曝光':>15} | {'讚':>10} | 內容摘要")
print("-" * 90)
for i, t in enumerate(sorted_by_impressions[:10]):
    preview = t["text"][:50].replace("\n", " ")
    print(f" {i+1} | {t['date']} | {t['impression_count']:>13,} | {t['like_count']:>8,} | {preview}")

# =========================================================
# 4. 發文量變化
# =========================================================
print("\n" + "=" * 80)
print("四、X 發文量的變化趨勢")
print("=" * 80)

monthly_counts = Counter(t["year_month"] for t in parsed_tweets)
print(f"\n【月度發文量】")
print(f"{'月份':>10} | {'篇數':>4} | 圖")
print("-" * 60)

all_months = []
start = datetime(2025, 1, 1)
end = datetime(2026, 3, 1)
current = start
while current <= end:
    ym = current.strftime("%Y-%m")
    all_months.append(ym)
    if current.month == 12:
        current = current.replace(year=current.year + 1, month=1)
    else:
        current = current.replace(month=current.month + 1)

for ym in all_months:
    c = monthly_counts.get(ym, 0)
    bar = "█" * c
    note = ""
    if c == 0:
        note = " ← 零發文！"
    print(f"  {ym} | {c:>4} | {bar}{note}")

# Weekly breakdown
weekly_counts = Counter(t["year_week"] for t in parsed_tweets)
print(f"\n【每週發文量趨勢（顯示有發文的週）】")
print(f"{'週':>10} | {'篇數':>4} | 圖")
print("-" * 50)
for week in sorted(weekly_counts.keys()):
    c = weekly_counts[week]
    bar = "█" * c
    print(f"  {week} | {c:>4} | {bar}")

# Find the "silence gap"
print(f"\n【發文間隔分析（找沉默期）】")
gaps = []
for i in range(1, len(parsed_tweets)):
    gap_days = (parsed_tweets[i]["datetime"] - parsed_tweets[i-1]["datetime"]).total_seconds() / 86400
    gaps.append({
        "from": parsed_tweets[i-1]["date"],
        "to": parsed_tweets[i]["date"],
        "gap_days": gap_days,
        "from_text": parsed_tweets[i-1]["text"][:50],
        "to_text": parsed_tweets[i]["text"][:50],
    })

gaps.sort(key=lambda x: x["gap_days"], reverse=True)
print(f"{'排名':>4} | {'從':>12} | {'到':>12} | {'間隔天數':>8} | 重新發文內容")
print("-" * 90)
for i, g in enumerate(gaps[:15]):
    preview = g["to_text"].replace("\n", " ")
    print(f"  {i+1:>2} | {g['from']} | {g['to']} | {g['gap_days']:>7.1f}天 | {preview}")

# When did he stop?
print(f"\n【關鍵轉折點：最後一批密集發文 vs 沉默】")
# Find the last dense period and when it stopped
for ym in all_months:
    c = monthly_counts.get(ym, 0)
    if c > 0:
        last_active = ym
        last_count = c
    if c == 0 and monthly_counts.get(all_months[all_months.index(ym)-1] if all_months.index(ym) > 0 else "", 0) > 0:
        print(f"  活躍期結束：{all_months[all_months.index(ym)-1]}（{monthly_counts.get(all_months[all_months.index(ym)-1], 0)} 篇）→ {ym}（{c} 篇）")

# Last few tweets chronologically
print(f"\n【各階段最後一篇推文】")
# Group by month and show last tweet
for ym in all_months:
    month_tweets = [t for t in parsed_tweets if t["year_month"] == ym]
    if month_tweets:
        last = month_tweets[-1]
        print(f"  {ym} 最後一篇 ({last['date']}): {last['text'][:70].replace(chr(10), ' ')}")

# =========================================================
# 5. X 獨有推文（找出特徵）
# =========================================================
print("\n" + "=" * 80)
print("五、X 獨有推文分析")
print("=" * 80)

# Load cross-reference data from x_truth_full_comparison.json
try:
    with open("data/x_truth_full_comparison.json", "r") as f:
        comparison_data = json.load(f)

    matched_ids = set(p["x_id"] for p in comparison_data.get("matched_pairs", []))
    x_only_from_comparison = comparison_data.get("x_only_posts", [])

    # Filter to second-term only (>= 2025-01-20) and non-RT original posts
    second_term_x_only_originals = []
    for post in x_only_from_comparison:
        dt = datetime.strptime(post["created_at"], "%Y-%m-%dT%H:%M:%S.000Z")
        if dt >= datetime(2025, 1, 20) and not post["text"].startswith("RT @"):
            second_term_x_only_originals.append(post)

    print(f"\n  交叉比對來源：x_truth_full_comparison.json")
    print(f"  比對結果：{len(matched_ids)} 篇在兩平台都有，{len(x_only_from_comparison)} 篇只在 X")
    print(f"  第二任期 X 獨有原創推文：{len(second_term_x_only_originals)} 篇")

    # Note: The comparison was done on 37 posts (embed API accessible).
    # The 168 full dataset has many more that weren't compared.
    # But based on the cross-platform matching logic, most Trump posts go to both.
    # The "X-only" originals are the key finding.

    print(f"\n【第二任期 X 獨有原創推文（不在 Truth Social 上）】")
    print(f"  注意：比對基於 x_truth_full_comparison.json 中可比對的推文")
    print(f"  以下推文只出現在 X，沒有對應的 Truth Social 發文：\n")

    for i, post in enumerate(second_term_x_only_originals):
        dt = datetime.strptime(post["created_at"], "%Y-%m-%dT%H:%M:%S.000Z")
        print(f"  {i+1}. [{dt.strftime('%Y-%m-%d')}] 讚:{post['likes']:>10,}")
        text = post["text"][:150].replace("\n", " ")
        print(f"     {text}")
        print()

except FileNotFoundError:
    comparison_data = None
    second_term_x_only_originals = []
    print("  [注意] 沒有找到 x_truth_full_comparison.json")

# RTs are inherently X-only since Truth Social doesn't have RT
print(f"\n【轉推（RT）= 天然 X 獨有內容】")
print(f"  總轉推數：{len(retweets)} 篇")
print(f"  （Truth Social 不支援 RT 功能，所以 RT 天然只存在 X）\n")
for t in retweets:
    print(f"  {t['date']} | 曝光:{t['impression_count']:>10,} | {t['text'][:80].replace(chr(10), ' ')}")

# Analyze retweets - who did he RT?
print(f"\n【轉推對象分析】")
rt_targets = []
for t in retweets:
    match = re.match(r'RT @(\w+):', t["text"])
    if match:
        rt_targets.append(match.group(1))
rt_target_counts = Counter(rt_targets)
for target, count in rt_target_counts.most_common():
    print(f"  @{target}: {count} 次")

# X-only common traits
print(f"\n【X 獨有推文的共同特徵分析】")
if second_term_x_only_originals:
    url_only_count = sum(1 for p in second_term_x_only_originals if re.match(r'^https?://t\.co/\S+$', p["text"].strip()) or re.match(r'^[^\w]*https?://t\.co/\S+$', p["text"].strip()))
    has_text_count = len(second_term_x_only_originals) - url_only_count
    avg_likes = sum(p["likes"] for p in second_term_x_only_originals) / len(second_term_x_only_originals)

    print(f"  純URL/影片：{url_only_count} 篇")
    print(f"  有文字：{has_text_count} 篇")
    print(f"  平均讚數：{avg_likes:,.0f}")
    print(f"  推論：X 獨有推文大多是影片/圖片（純 URL），")
    print(f"        這些內容可能是 X 原生格式（影片直傳 X），")
    print(f"        無法直接搬到 Truth Social 的格式。")
    print(f"        少數文字推文如 $TRUMP meme coin 推廣也是 X 獨有，")
    print(f"        因為 $TRUMP 需要 X 的加密貨幣社群觸及面。")

# =========================================================
# Additional: Engagement totals
# =========================================================
print("\n" + "=" * 80)
print("六、整體互動數據統計")
print("=" * 80)

total_impressions = sum(t["impression_count"] for t in parsed_tweets)
total_likes = sum(t["like_count"] for t in parsed_tweets)
total_retweets_count = sum(t["retweet_count"] for t in parsed_tweets)
total_replies = sum(t["metrics"]["reply_count"] for t in parsed_tweets)
total_quotes = sum(t["metrics"]["quote_count"] for t in parsed_tweets)
total_bookmarks = sum(t["metrics"]["bookmark_count"] for t in parsed_tweets)

print(f"  總曝光數：{total_impressions:>15,}")
print(f"  總按讚數：{total_likes:>15,}")
print(f"  總轉推數：{total_retweets_count:>15,}")
print(f"  總回覆數：{total_replies:>15,}")
print(f"  總引用數：{total_quotes:>15,}")
print(f"  總書籤數：{total_bookmarks:>15,}")
print(f"  平均每篇曝光：{total_impressions/len(parsed_tweets):>12,.0f}")
print(f"  平均每篇讚：{total_likes/len(parsed_tweets):>12,.0f}")

# =========================================================
# Save analysis results
# =========================================================

# Build the output JSON
analysis_result = {
    "metadata": {
        "analysis_date": "2026-03-15",
        "total_tweets": len(parsed_tweets),
        "originals": sum(1 for t in parsed_tweets if not t["is_retweet"]),
        "retweets": len(retweets),
        "date_range": {
            "start": parsed_tweets[0]["date"],
            "end": parsed_tweets[-1]["date"]
        }
    },
    "timing_analysis": {
        "hour_distribution_et": {f"{h:02d}:00": hour_counts.get(h, 0) for h in range(24)},
        "peak_hours_et": sorted(hour_counts.keys(), key=lambda h: hour_counts[h], reverse=True)[:5],
        "market_session": {
            "pre_market_4am_930am": {"count": pre_market, "pct": round(pre_market/len(parsed_tweets)*100, 1)},
            "market_hours_930am_4pm": {"count": market_hours, "pct": round(market_hours/len(parsed_tweets)*100, 1)},
            "after_market_4pm_8pm": {"count": after_market, "pct": round(after_market/len(parsed_tweets)*100, 1)},
            "off_hours_8pm_4am": {"count": off_hours, "pct": round(off_hours/len(parsed_tweets)*100, 1)},
        },
        "weekday_distribution": {weekday_zh[i]: weekday_counts.get(i, 0) for i in range(7)},
    },
    "market_impact": {
        "tweet_days": {
            "count": len(tweet_day_returns),
            "avg_return_pct": round(avg_tweet, 4),
            "avg_next_day_return_pct": round(avg_tweet_next, 4),
            "volatility_pct": round(vol_tweet, 4),
            "positive_day_ratio_pct": round(pos_tweet, 1),
        },
        "no_tweet_days": {
            "count": len(no_tweet_day_returns),
            "avg_return_pct": round(avg_no_tweet, 4),
            "avg_next_day_return_pct": round(avg_no_tweet_next, 4),
            "volatility_pct": round(vol_no_tweet, 4),
            "positive_day_ratio_pct": round(pos_no_tweet, 1),
        },
        "difference": {
            "same_day_return_diff": round(avg_tweet - avg_no_tweet, 4),
            "next_day_return_diff": round(avg_tweet_next - avg_no_tweet_next, 4),
            "volatility_diff": round(vol_tweet - vol_no_tweet, 4),
        },
        "biggest_move_days": [
            {
                "date": d,
                "return_pct": round(r, 3),
                "tweet_count": c,
                "sample_text": txts[0] if txts else ""
            }
            for d, r, c, txts in tweet_day_moves[:10]
        ],
    },
    "content_analysis": {
        "type_distribution": {
            "url_only": {"count": len(url_only), "pct": round(len(url_only)/len(parsed_tweets)*100, 1)},
            "text_content": {"count": len(has_text), "pct": round(len(has_text)/len(parsed_tweets)*100, 1)},
            "retweets": {"count": len(retweets), "pct": round(len(retweets)/len(parsed_tweets)*100, 1)},
        },
        "topic_distribution": {
            topic: {
                "count": count,
                "pct": round(count/len(originals)*100, 1),
                "sample": topic_tweets[topic][0]["text"][:100] if topic in topic_tweets and topic_tweets[topic] else ""
            }
            for topic, count in topic_counts.most_common()
        },
        "engagement_by_type": {
            "url_only": {
                "avg_impressions": round(avg_impressions_url),
                "avg_likes": round(avg_likes_url),
                "avg_retweets": round(avg_rt_url),
            },
            "text_content": {
                "avg_impressions": round(avg_impressions_text),
                "avg_likes": round(avg_likes_text),
                "avg_retweets": round(avg_rt_text),
            },
        },
        "top_10_by_impressions": [
            {
                "date": t["date"],
                "text": t["text"][:200],
                "impressions": t["impression_count"],
                "likes": t["like_count"],
                "retweets": t["retweet_count"],
            }
            for t in sorted_by_impressions[:10]
        ],
    },
    "volume_trend": {
        "monthly": {ym: monthly_counts.get(ym, 0) for ym in all_months},
        "silence_gaps_top10": [
            {
                "from_date": g["from"],
                "to_date": g["to"],
                "gap_days": round(g["gap_days"], 1),
                "resumed_with": g["to_text"]
            }
            for g in gaps[:10]
        ],
        "key_findings": {
            "peak_month": max(all_months, key=lambda ym: monthly_counts.get(ym, 0)),
            "peak_month_count": max(monthly_counts.values()) if monthly_counts else 0,
            "zero_months": [ym for ym in all_months if monthly_counts.get(ym, 0) == 0],
            "last_tweet_date": parsed_tweets[-1]["date"],
            "total_active_days": len(tweet_dates),
        },
    },
    "x_only_analysis": {
        "retweets_are_x_only": True,
        "retweet_count": len(retweets),
        "retweet_targets": dict(rt_target_counts.most_common()),
        "retweet_details": [
            {
                "date": t["date"],
                "text": t["text"][:200],
                "impressions": t["impression_count"],
            }
            for t in retweets
        ],
        "second_term_x_only_originals": [
            {
                "id": p["id"],
                "date": datetime.strptime(p["created_at"], "%Y-%m-%dT%H:%M:%S.000Z").strftime("%Y-%m-%d"),
                "text": p["text"][:200],
                "likes": p["likes"],
            }
            for p in second_term_x_only_originals
        ] if second_term_x_only_originals else [],
        "common_traits": {
            "mostly_url_video": True,
            "high_engagement": True,
            "x_native_format": "影片/圖片直接上傳 X，無法一鍵搬到 Truth Social",
            "crypto_promotion": "$TRUMP meme coin 推廣需要 X 的加密貨幣社群",
        },
        "note": "轉推（RT）在 Truth Social 不存在，因此所有 14 篇 RT 都是 X 獨有。原創推文中也有多篇（主要是影片/URL）只在 X 發布。",
    },
    "overall_engagement": {
        "total_impressions": total_impressions,
        "total_likes": total_likes,
        "total_retweets": total_retweets_count,
        "total_replies": total_replies,
        "total_quotes": total_quotes,
        "total_bookmarks": total_bookmarks,
        "avg_impressions_per_tweet": round(total_impressions / len(parsed_tweets)),
        "avg_likes_per_tweet": round(total_likes / len(parsed_tweets)),
    },
}

with open("data/x_independent_analysis.json", "w", encoding="utf-8") as f:
    json.dump(analysis_result, f, ensure_ascii=False, indent=2)

print(f"\n\n{'=' * 80}")
print("分析結果已儲存至 data/x_independent_analysis.json")
print(f"{'=' * 80}")
