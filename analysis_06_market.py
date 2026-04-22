#!/usr/bin/env python3
"""
Trump Code Analysis #6 - Posts vs Stock Market Reaction
Core question: After he posts, how does the stock market move?
"""

import json
import re
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent


def main():
    # --- Load data ---
    with open(BASE / "clean_president.json", 'r', encoding='utf-8') as f:
        posts = json.load(f)

    DATA = BASE / "data"

    with open(DATA / "market_SP500.json", 'r', encoding='utf-8') as f:
        sp500 = json.load(f)

    with open(DATA / "market_VIX.json", 'r', encoding='utf-8') as f:
        vix = json.load(f)

    with open(DATA / "market_DOW.json", 'r', encoding='utf-8') as f:
        dow = json.load(f)

    with open(DATA / "market_NASDAQ.json", 'r', encoding='utf-8') as f:
        nasdaq = json.load(f)

    # Build date index
    sp500_by_date = {r['date']: r for r in sp500}
    vix_by_date = {r['date']: r for r in vix}
    dow_by_date = {r['date']: r for r in dow}
    nasdaq_by_date = {r['date']: r for r in nasdaq}

    originals = [p for p in posts if p['has_text'] and not p['is_retweet']]

    print("=" * 80)
    print("📈 Analysis #6: Trump Posts vs Stock Market Reaction")
    print(f"   Posts: {len(originals)} | S&P500: {len(sp500)} trading days")
    print("=" * 80)


    # === Utility Functions ===

    def get_next_trading_day(date_str, market_data):
        """Get the next trading day after a given date"""
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        for i in range(1, 5):  # Look up to 4 days ahead (over weekend)
            next_d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
            if next_d in market_data:
                return next_d
        return None

    def get_prev_trading_day(date_str, market_data):
        """Get the previous trading day before a given date"""
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        for i in range(1, 5):
            prev_d = (dt - timedelta(days=i)).strftime('%Y-%m-%d')
            if prev_d in market_data:
                return prev_d
        return None

    def day_return(date_str, market_data):
        """Calculate daily return % (close-to-close)"""
        if date_str not in market_data:
            return None
        # Find previous trading day
        sorted_dates = sorted(market_data.keys())
        try:
            idx = sorted_dates.index(date_str)
        except ValueError:
            return None
        if idx == 0:
            # First day has no previous day, fallback to open-to-close
            d = market_data[date_str]
            return (d['close'] - d['open']) / d['open'] * 100
        prev_date = sorted_dates[idx - 1]
        prev_close = market_data[prev_date]['close']
        today_close = market_data[date_str]['close']
        return (today_close - prev_close) / prev_close * 100

    def intraday_return(date_str, market_data):
        """Calculate intraday return % (open-to-close)"""
        if date_str not in market_data:
            return None
        d = market_data[date_str]
        return (d['close'] - d['open']) / d['open'] * 100

    def next_day_return(date_str, market_data):
        """Calculate next trading day return %"""
        next_d = get_next_trading_day(date_str, market_data)
        if not next_d:
            return None
        return day_return(next_d, market_data)

    def overnight_gap(date_str, market_data):
        """Calculate overnight gap (next trading day open vs today close)"""
        if date_str not in market_data:
            return None
        next_d = get_next_trading_day(date_str, market_data)
        if not next_d:
            return None
        today_close = market_data[date_str]['close']
        next_open = market_data[next_d]['open']
        return (next_open - today_close) / today_close * 100


    # === Daily Post Features ===
    daily_features = defaultdict(lambda: {
        'post_count': 0, 'total_length': 0, 'excl_count': 0,
        'caps_count': 0, 'has_tariff': False, 'has_china': False,
        'has_market': False, 'has_deal': False, 'has_fake': False,
        'has_iran': False, 'has_border': False, 'emotion_sum': 0,
        'night_posts': 0, 'contents': []
    })

    def welch_ttest(group1, group2):
        """Welch's t-test (no equal variance assumption), pure Python implementation"""
        n1, n2 = len(group1), len(group2)
        if n1 < 2 or n2 < 2:
            return {'t': None, 'significant': False, 'note': 'Insufficient sample'}
        mean1 = sum(group1) / n1
        mean2 = sum(group2) / n2
        var1 = sum((x - mean1) ** 2 for x in group1) / (n1 - 1)
        var2 = sum((x - mean2) ** 2 for x in group2) / (n2 - 1)
        se = math.sqrt(var1 / n1 + var2 / n2)
        if se == 0:
            return {'t': None, 'significant': False, 'note': 'Zero variance'}
        t = (mean1 - mean2) / se
        df = n1 + n2 - 2
        significant = abs(t) > 2.0 and df > 10
        return {
            't': round(t, 3),
            'df': df,
            'significant': significant,
            'mean_diff': round(mean1 - mean2, 4),
        }

    def emotion_score(content):
        score = 0
        text = content
        upper = sum(1 for c in text if c.isupper())
        total = sum(1 for c in text if c.isalpha())
        caps_ratio = upper / max(total, 1)
        score += caps_ratio * 30
        excl = text.count('!')
        excl_density = excl / max(len(text), 1) * 100
        score += min(excl_density * 10, 25)
        strong_words = ['never', 'always', 'worst', 'best', 'greatest', 'terrible',
                        'tremendous', 'massive', 'total', 'complete', 'disaster',
                        'incredible', 'amazing', 'fantastic', 'historic', 'beautiful']
        strong_count = sum(1 for w in strong_words if w in text.lower())
        word_count = len(re.findall(r'\b\w+\b', text.lower()))
        score += min(strong_count / max(word_count, 1) * 500, 25)
        caps_words = len(re.findall(r'\b[A-Z]{3,}\b', text))
        score += min(caps_words * 2, 20)
        return min(round(score, 1), 100)

    for p in originals:
        date = p['created_at'][:10]
        content_lower = p['content'].lower()
        d = daily_features[date]
        d['post_count'] += 1
        d['total_length'] += p['content_length']
        d['excl_count'] += p['content'].count('!')
        d['caps_count'] += len(re.findall(r'\b[A-Z]{3,}\b', p['content']))
        d['emotion_sum'] += emotion_score(p['content'])
        d['contents'].append(p['content'][:80])

        if any(w in content_lower for w in ['tariff', 'tariffs', 'duty', 'duties']):
            d['has_tariff'] = True
        if any(w in content_lower for w in ['china', 'chinese', 'beijing', 'xi jinping']):
            d['has_china'] = True
        if any(w in content_lower for w in ['stock market', 'dow', 'nasdaq', 's&p', 'wall street', 'market']):
            d['has_market'] = True
        if any(w in content_lower for w in ['deal', 'trade deal', 'agreement']):
            d['has_deal'] = True
        if any(w in content_lower for w in ['fake news', 'fake media', 'corrupt']):
            d['has_fake'] = True
        if any(w in content_lower for w in ['iran', 'iranian', 'tehran']):
            d['has_iran'] = True
        if any(w in content_lower for w in ['border', 'immigration', 'deport', 'illegal']):
            d['has_border'] = True

        # After-hours/pre-market posts (Eastern 16:00-09:30 = UTC 21:00-14:30)
        hour_utc = int(p['created_at'][11:13])
        if hour_utc >= 21 or hour_utc < 14:
            d['night_posts'] += 1


    # ============================================================
    # Baseline: Average return for all trading days
    # ============================================================
    all_trading_dates = sorted(sp500_by_date.keys())
    all_returns = [day_return(d, sp500_by_date) for d in all_trading_dates]
    all_returns = [r for r in all_returns if r is not None]
    baseline_mean = sum(all_returns) / len(all_returns) if all_returns else 0
    baseline_std = (sum((r - baseline_mean) ** 2 for r in all_returns) / max(len(all_returns) - 1, 1)) ** 0.5

    print(f"\n{'='*80}")
    print(f"📊 Baseline: All Trading Days ({len(all_returns)} days)")
    print(f"   Average Daily Return: {baseline_mean:+.4f}%")
    print(f"   Standard Deviation: {baseline_std:.4f}%")
    print("=" * 80)


    # ============================================================
    # Analysis 1: Post Volume vs Next Day Stock Market
    # ============================================================
    print(f"\n{'='*80}")
    print("📊 Analysis 1: Post Volume vs Next Day S&P500")
    print("=" * 80)

    # Group by post volume
    buckets = {'0-5 posts': (0, 5), '6-10 posts': (6, 10), '11-20 posts': (11, 20),
               '21-40 posts': (21, 40), '40+ posts': (41, 999)}

    for bucket_name, (lo, hi) in buckets.items():
        days = [d for d, f in daily_features.items()
                if lo <= f['post_count'] <= hi and d in sp500_by_date]
        if not days:
            continue

        next_returns = [next_day_return(d, sp500_by_date) for d in days]
        next_returns = [r for r in next_returns if r is not None]

        same_returns = [day_return(d, sp500_by_date) for d in days]
        same_returns = [r for r in same_returns if r is not None]

        if next_returns:
            avg_next = sum(next_returns) / len(next_returns)
            avg_same = sum(same_returns) / len(same_returns) if same_returns else 0
            pos = sum(1 for r in next_returns if r > 0)
            print(f"  {bucket_name:10s} | {len(days):3d} days | Same day avg {avg_same:+.2f}% | Next day avg {avg_next:+.2f}% | Next day up {pos}/{len(next_returns)} ({pos/len(next_returns)*100:.0f}%)")


    # ============================================================
    # Analysis 2: Tariff Posts vs Stock Market
    # ============================================================
    print(f"\n{'='*80}")
    print("📊 Analysis 2: 'Tariff' Post Days vs Non-Tariff Days S&P500")
    print("=" * 80)

    tariff_days = [d for d, f in daily_features.items() if f['has_tariff'] and d in sp500_by_date]
    non_tariff_days = [d for d, f in daily_features.items() if not f['has_tariff'] and d in sp500_by_date]

    tariff_same_rets = []
    tariff_next_rets = []
    non_tariff_same_rets = []
    non_tariff_next_rets = []

    for label, days in [('Mentioned Tariff', tariff_days), ('No Tariff', non_tariff_days)]:
        same_ret = [day_return(d, sp500_by_date) for d in days]
        same_ret = [r for r in same_ret if r is not None]
        next_ret = [next_day_return(d, sp500_by_date) for d in days]
        next_ret = [r for r in next_ret if r is not None]

        if same_ret and next_ret:
            avg_same = sum(same_ret) / len(same_ret)
            avg_next = sum(next_ret) / len(next_ret)
            pos_same = sum(1 for r in same_ret if r > 0)
            pos_next = sum(1 for r in next_ret if r > 0)
            print(f"  {label:15s} | {len(days):3d} days | Same day {avg_same:+.3f}% (up {pos_same}/{len(same_ret)}) | Next day {avg_next:+.3f}% (up {pos_next}/{len(next_ret)})")
            if label == 'Mentioned Tariff':
                tariff_same_rets = same_ret
                tariff_next_rets = next_ret
            else:
                non_tariff_same_rets = same_ret
                non_tariff_next_rets = next_ret

    # t-test: Tariff days vs Non-tariff days
    ttest_tariff_same = welch_ttest(tariff_same_rets, non_tariff_same_rets)
    ttest_tariff_next = welch_ttest(tariff_next_rets, non_tariff_next_rets)
    print(f"  [t-test same day] t={ttest_tariff_same['t']}, {'Significant' if ttest_tariff_same['significant'] else 'Not significant'} (df={ttest_tariff_same.get('df', 'N/A')})")
    print(f"  [t-test next day] t={ttest_tariff_next['t']}, {'Significant' if ttest_tariff_next['significant'] else 'Not significant'} (df={ttest_tariff_next.get('df', 'N/A')})")


    # ============================================================
    # Analysis 3: China Mentions vs Stock Market
    # ============================================================
    print(f"\n{'='*80}")
    print("📊 Analysis 3: 'China' Post Days vs Other Days S&P500")
    print("=" * 80)

    china_days = [d for d, f in daily_features.items() if f['has_china'] and d in sp500_by_date]
    non_china_days = [d for d, f in daily_features.items() if not f['has_china'] and d in sp500_by_date]

    for label, days in [('Mentioned China', china_days), ('No China', non_china_days)]:
        same_ret = [r for r in [day_return(d, sp500_by_date) for d in days] if r is not None]
        next_ret = [r for r in [next_day_return(d, sp500_by_date) for d in days] if r is not None]
        if same_ret and next_ret:
            print(f"  {label:15s} | {len(days):3d} days | Same day {sum(same_ret)/len(same_ret):+.3f}% | Next day {sum(next_ret)/len(next_ret):+.3f}%")


    # ============================================================
    # Analysis 4: Market Mentions vs Actual Market Performance
    # ============================================================
    print(f"\n{'='*80}")
    print("📊 Analysis 4: When He Mentions 'Stock Market' vs Actual Performance")
    print("=" * 80)

    market_days = [d for d, f in daily_features.items() if f['has_market'] and d in sp500_by_date]
    non_market_days = [d for d, f in daily_features.items() if not f['has_market'] and d in sp500_by_date]

    for label, days in [('Mentioned Market', market_days), ('No Market Mention', non_market_days)]:
        same_ret = [r for r in [day_return(d, sp500_by_date) for d in days] if r is not None]
        next_ret = [r for r in [next_day_return(d, sp500_by_date) for d in days] if r is not None]
        if same_ret and next_ret:
            avg_s = sum(same_ret)/len(same_ret)
            avg_n = sum(next_ret)/len(next_ret)
            print(f"  {label:20s} | {len(days):3d} days | Same day {avg_s:+.3f}% | Next day {avg_n:+.3f}%")

    # Does he mention markets on up days or down days?
    print(f"\n  Does he typically mention markets on up days or down days?")
    for d in sorted(market_days)[-15:]:
        ret = day_return(d, sp500_by_date)
        if ret is not None:
            arrow = "📈" if ret > 0 else "📉"
            sample = daily_features[d]['contents'][0][:60] if daily_features[d]['contents'] else ''
            print(f"    {d} | S&P {ret:+.2f}% {arrow} | {sample}...")


    # ============================================================
    # Analysis 5: Emotion Intensity vs Stock Market
    # ============================================================
    print(f"\n{'='*80}")
    print("📊 Analysis 5: Emotion Intensity vs S&P500")
    print("=" * 80)

    # Group by emotion
    emotion_buckets = []
    for date, feat in daily_features.items():
        if date in sp500_by_date and feat['post_count'] > 0:
            avg_emotion = feat['emotion_sum'] / feat['post_count']
            nr = next_day_return(date, sp500_by_date)
            sr = day_return(date, sp500_by_date)
            if nr is not None and sr is not None:
                emotion_buckets.append({
                    'date': date,
                    'emotion': avg_emotion,
                    'same_day': sr,
                    'next_day': nr,
                    'post_count': feat['post_count']
                })

    # Divide into 5 groups by emotion intensity
    emotion_buckets.sort(key=lambda x: x['emotion'])
    chunk = len(emotion_buckets) // 5

    for i in range(5):
        start = i * chunk
        end = start + chunk if i < 4 else len(emotion_buckets)
        group = emotion_buckets[start:end]

        avg_emo = sum(g['emotion'] for g in group) / len(group)
        avg_same = sum(g['same_day'] for g in group) / len(group)
        avg_next = sum(g['next_day'] for g in group) / len(group)
        labels = ['😌Very Calm', '🙂Calm', '😐Neutral', '😤Agitated', '🔥Very Agitated']

        print(f"  {labels[i]} | Emotion {avg_emo:5.1f} | {len(group):3d} days | Same day {avg_same:+.3f}% | Next day {avg_next:+.3f}%")


    # ============================================================
    # Analysis 6: After-Hours Posts vs Next Day Gap
    # ============================================================
    print(f"\n{'='*80}")
    print("📊 Analysis 6: After-Hours Posts vs Next Day Opening Gap")
    print("=" * 80)

    for date, feat in sorted(daily_features.items()):
        if feat['night_posts'] > 5 and date in sp500_by_date:
            gap = overnight_gap(date, sp500_by_date)
            if gap is not None:
                arrow = "⬆️" if gap > 0 else "⬇️"
                print(f"  {date} | After-hours {feat['night_posts']:2d} posts | Next day gap {gap:+.2f}% {arrow}")


    # ============================================================
    # Analysis 7: VIX Fear Index vs Posting Behavior
    # ============================================================
    print(f"\n{'='*80}")
    print("📊 Analysis 7: VIX Fear Index vs Posting Behavior")
    print("=" * 80)

    # High VIX days (>25) - how does he post
    high_vix_days = [d for d in vix_by_date if vix_by_date[d]['close'] > 25 and d in daily_features]
    low_vix_days = [d for d in vix_by_date if vix_by_date[d]['close'] < 15 and d in daily_features]
    normal_vix_days = [d for d in vix_by_date if 15 <= vix_by_date[d]['close'] <= 25 and d in daily_features]

    for label, days in [('VIX>25 Fear', high_vix_days), ('VIX 15-25 Normal', normal_vix_days), ('VIX<15 Calm', low_vix_days)]:
        if not days:
            print(f"  {label:17s} | 0 days")
            continue
        avg_posts = sum(daily_features[d]['post_count'] for d in days) / len(days)
        avg_emotion = sum(daily_features[d]['emotion_sum'] / max(daily_features[d]['post_count'], 1) for d in days) / len(days)
        tariff_pct = sum(1 for d in days if daily_features[d]['has_tariff']) / len(days) * 100
        print(f"  {label:17s} | {len(days):3d} days | Avg {avg_posts:.1f} posts/day | Emotion {avg_emotion:.1f} | Tariff mentions {tariff_pct:.0f}%")


    # ============================================================
    # Analysis 8: Biggest Market Moves - What did he post?
    # ============================================================
    print(f"\n{'='*80}")
    print("📊 Analysis 8: S&P500 Biggest Moves — What did he post that day/day before?")
    print("=" * 80)

    # Calculate daily moves
    daily_returns = []
    for d in sp500:
        ret = (d['close'] - d['open']) / d['open'] * 100
        daily_returns.append({'date': d['date'], 'return': ret, 'close': d['close']})

    daily_returns.sort(key=lambda x: x['return'])

    print(f"\n  📉 Biggest Drops Top 10:")
    for item in daily_returns[:10]:
        d = item['date']
        prev = get_prev_trading_day(d, sp500_by_date)

        # Previous day posts
        prev_posts = daily_features.get(prev, {})
        prev_count = prev_posts.get('post_count', 0) if prev_posts else 0
        prev_tariff = prev_posts.get('has_tariff', False) if prev_posts else False
        prev_china = prev_posts.get('has_china', False) if prev_posts else False

        # Same day posts
        today_posts = daily_features.get(d, {})
        today_count = today_posts.get('post_count', 0) if today_posts else 0

        tags = []
        if prev_tariff: tags.append('💣Tariff')
        if prev_china: tags.append('🇨🇳China')

        sample = ''
        if prev_posts and prev_posts.get('contents'):
            sample = prev_posts['contents'][0][:50]

        print(f"    {d} | S&P {item['return']:+.2f}% | Prev day {prev_count} posts Today {today_count} posts | {' '.join(tags)} | {sample}")

    print(f"\n  📈 Biggest Gains Top 10:")
    for item in daily_returns[-10:][::-1]:
        d = item['date']
        prev = get_prev_trading_day(d, sp500_by_date)

        prev_posts = daily_features.get(prev, {})
        prev_count = prev_posts.get('post_count', 0) if prev_posts else 0
        prev_tariff = prev_posts.get('has_tariff', False) if prev_posts else False
        prev_deal = prev_posts.get('has_deal', False) if prev_posts else False

        today_posts = daily_features.get(d, {})
        today_count = today_posts.get('post_count', 0) if today_posts else 0

        tags = []
        if prev_tariff: tags.append('💣Tariff')
        if prev_deal: tags.append('🤝Deal')

        sample = ''
        if prev_posts and prev_posts.get('contents'):
            sample = prev_posts['contents'][0][:50]

        print(f"    {d} | S&P {item['return']:+.2f}% | Prev day {prev_count} posts Today {today_count} posts | {' '.join(tags)} | {sample}")


    # ============================================================
    # Analysis 9: Tariff Post Timeline vs S&P500
    # ============================================================
    print(f"\n{'='*80}")
    print("📊 Analysis 9: Tariff Post Timeline vs S&P500 Trend")
    print("=" * 80)

    tariff_timeline = []
    for date in sorted(daily_features.keys()):
        if daily_features[date]['has_tariff'] and date in sp500_by_date:
            sp = sp500_by_date[date]
            ret = day_return(date, sp500_by_date)
            nret = next_day_return(date, sp500_by_date)
            tariff_timeline.append({
                'date': date,
                'posts': daily_features[date]['post_count'],
                'sp500_close': sp['close'],
                'day_return': ret,
                'next_return': nret,
            })

    print(f"  {'Date':12s} | {'Posts':>4s} | {'S&P500':>10s} | {'Same Day':>7s} | {'Next Day':>7s}")
    print(f"  {'-'*12}-+-{'-'*4}-+-{'-'*10}-+-{'-'*7}-+-{'-'*7}")
    for t in tariff_timeline:
        nr = f"{t['next_return']:+.2f}%" if t['next_return'] is not None else "  N/A"
        dr = f"{t['day_return']:+.2f}%" if t['day_return'] is not None else "  N/A"
        print(f"  {t['date']:12s} | {t['posts']:4d} | {t['sp500_close']:>10,.2f} | {dr:>7s} | {nr:>7s}")


    # ============================================================
    # Save Results Summary
    # ============================================================
    results = {
        'baseline': {
            'all_trading_days': len(all_returns),
            'mean_return': round(baseline_mean, 4),
            'std_return': round(baseline_std, 4),
        },
        'tariff_vs_market': {
            'tariff_days': len(tariff_days),
            'non_tariff_days': len(non_tariff_days),
            'ttest_same_day': ttest_tariff_same,
            'ttest_next_day': ttest_tariff_next,
        },
        'tariff_timeline': tariff_timeline,
        'biggest_drops': [{'date': d['date'], 'return': round(d['return'], 2)} for d in daily_returns[:10]],
        'biggest_gains': [{'date': d['date'], 'return': round(d['return'], 2)} for d in daily_returns[-10:]],
    }
    with open(DATA / 'results_06_market.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Detailed results saved to results_06_market.json")


if __name__ == '__main__':
    main()


