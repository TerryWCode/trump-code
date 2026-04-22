#!/usr/bin/env python3
"""
Trump Code - Real-time Monitor + Multi-Model Prediction Engine
Fetches latest posts every 5 minutes, runs 12 prediction models, tracks which ones hit

Usage:
  python3 trump_monitor.py              # Real-time monitoring (continuous)
  python3 trump_monitor.py --backtest   # Backtest all prediction groups with historical data
  python3 trump_monitor.py --status     # View current hit rate of each prediction group
"""

import json
import csv
import logging
import re
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils import est_hour, market_session, emotion_score

BASE = Path(__file__).parent
ARCHIVE_URL = "https://ix.cnn.io/data/truth-social/truth_archive.csv"
DATA = BASE / "data"
PREDICTIONS_FILE = DATA / "predictions_log.json"
SCORES_FILE = DATA / "prediction_scores.json"
ALERTS_FILE = BASE / "alerts_log.json"
LAST_POST_FILE = BASE / "last_seen_post.txt"

# ============================================================
# Signal Classifier
# ============================================================

def classify_signals(content):
    """Classify a post into multiple signals"""
    cl = content.lower()
    signals = set()

    # Policy signals
    if any(w in cl for w in ['tariff', 'tariffs', 'duty', 'duties', 'reciprocal']):
        signals.add('TARIFF')
    if any(w in cl for w in ['deal', 'agreement', 'negotiate', 'talks', 'signed']):
        signals.add('DEAL')
    if any(w in cl for w in ['pause', 'delay', 'exempt', 'exception', 'suspend', 'postpone']):
        signals.add('RELIEF')
    if any(w in cl for w in ['immediately', 'effective', 'hereby', 'executive order', 'just signed', 'i have directed']):
        signals.add('ACTION')
    if any(w in cl for w in ['ban', 'block', 'restrict', 'sanction', 'punish']):
        signals.add('THREAT')

    # Sentiment signals
    if any(w in cl for w in ['stock market', 'all time high', 'record high', 'dow', 'nasdaq', 'market up']):
        signals.add('MARKET_BRAG')
    if any(w in cl for w in ['fake news', 'corrupt', 'fraud', 'witch hunt', 'disgrace', 'hoax']):
        signals.add('ATTACK')
    if any(w in cl for w in ['great', 'tremendous', 'incredible', 'historic', 'beautiful', 'amazing']):
        signals.add('POSITIVE')

    # Geopolitical signals
    if any(w in cl for w in ['china', 'chinese', 'beijing', 'xi jinping']):
        signals.add('CHINA')
    if any(w in cl for w in ['iran', 'iranian', 'tehran']):
        signals.add('IRAN')
    if any(w in cl for w in ['russia', 'russian', 'putin', 'ukraine', 'zelensky']):
        signals.add('RUSSIA')

    # New pattern tracking
    if 'save america act' in cl:
        signals.add('NEW_SAVE_ACT')
    if 'president djt' in cl:
        signals.add('SIG_DJT')
    if 'president of the united states' in cl:
        signals.add('SIG_POTUS')
    if 'thank you for your attention' in cl:
        signals.add('SIG_TYFA')

    return signals


# est_hour, market_session, emotion_score imported from utils.py


# ============================================================
# 12 Prediction Models
# ============================================================

class PredictionEngine:
    """Run multiple prediction models simultaneously"""

    def __init__(self):
        self.models = {
            # --- Group A: Single-Signal Models ---
            'A1_tariff_bearish': {
                'name': 'Intraday tariff→next day drop',
                'desc': 'TARIFF signal appears ≥2 times during trading hours → predict S&P closes lower next day',
                'direction': 'SHORT',
                'hold': 1,
                'trigger': self._trigger_a1,
            },
            'A2_deal_bullish': {
                'name': 'DEAL appears→next day rise',
                'desc': 'DEAL signal appears without TARIFF → predict S&P closes higher next day',
                'direction': 'LONG',
                'hold': 1,
                'trigger': self._trigger_a2,
            },
            'A3_relief_rocket': {
                'name': 'Pre-market RELIEF→same day surge',
                'desc': 'Pause/exemption appears pre-market → predict S&P surges today',
                'direction': 'LONG',
                'hold': 0,  # 0 = same day
                'trigger': self._trigger_a3,
            },

            # --- Group B: Multi-Signal Combination Models ---
            'B1_triple_signal': {
                'name': 'Triple signal→buy 3 days',
                'desc': 'TARIFF+DEAL+RELIEF same day → bottom signal, rise within 3 days',
                'direction': 'LONG',
                'hold': 3,
                'trigger': self._trigger_b1,
            },
            'B2_tariff_to_deal': {
                'name': '3 days tariff→Deal appears→reversal',
                'desc': '3 consecutive days TARIFF then DEAL appears → reversal buy',
                'direction': 'LONG',
                'hold': 2,
                'trigger': self._trigger_b2,
            },
            'B3_action_pre': {
                'name': 'Pre-market ACTION+positive sentiment→rise',
                'desc': 'Pre-market executive order + positive sentiment → bullish',
                'direction': 'LONG',
                'hold': 1,
                'trigger': self._trigger_b3,
            },

            # --- Group C: Behavioral Anomaly Models ---
            'C1_burst_silence': {
                'name': 'Positive burst→silence→long',
                'desc': '≥5 posts in 1 hour then silence ≥3 hours, and positive > negative during burst → long',
                'direction': 'LONG',
                'hold': 1,
                'trigger': self._trigger_c1,
            },
            'C2_brag_top': {
                'name': 'Market bragging→short-term top',
                'desc': 'Market bragging ≥3 times a day → short-term peak',
                'direction': 'SHORT',
                'hold': 2,
                'trigger': self._trigger_c2,
            },
            'C3_night_alert': {
                'name': 'Late-night tariff post→opening gap',
                'desc': 'Late-night/early-morning tariff mention → next day opening gap',
                'direction': 'SHORT',
                'hold': 1,
                'trigger': self._trigger_c3,
            },

            # --- Group D: Pattern Change Detection Models ---
            'D1_new_phrase': {
                'name': 'New slogan appears→volatility increase',
                'desc': 'New policy phrase not seen in past 30 days → volatility rises',
                'direction': 'VOLATILE',
                'hold': 3,
                'trigger': self._trigger_d1,
            },
            'D2_sig_change': {
                'name': 'Signature switch→official statement',
                'desc': 'Uses POTUS-level signature → major policy about to land',
                'direction': 'VOLATILE',
                'hold': 2,
                'trigger': self._trigger_d2,
            },
            'D3_volume_spike': {
                'name': 'Post volume spike→panic bottom',
                'desc': 'Daily post count > past 7 days avg×2 → panic extreme',
                'direction': 'LONG',
                'hold': 3,
                'trigger': self._trigger_d3,
            },
        }

        # Cumulative scores for each model
        self.scores = self._load_scores()
        # Historical context
        self.context = {
            'prev_days': [],    # Summary of past 7 days
            'recent_phrases': set(),  # Phrases seen in past 30 days
        }
        # Triggered (model_id, date) combinations for deduplication
        self._triggered_set = set()
        # Initialize triggered records from existing trades
        for mid, s in self.scores.items():
            for t in s.get('trades', []):
                if t.get('date'):
                    self._triggered_set.add((mid, t['date']))

    def _load_scores(self):
        if SCORES_FILE.exists():
            with open(SCORES_FILE, encoding='utf-8') as f:
                return json.load(f)
        return {m: {'predictions': 0, 'correct': 0, 'wrong': 0, 'pending': 0,
                     'total_return': 0, 'trades': []}
                for m in self.models}

    def save_scores(self):
        with open(SCORES_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.scores, f, ensure_ascii=False, indent=2)

    # --- Trigger Conditions ---

    def _trigger_a1(self, day_summary):
        """Intraday TARIFF ≥2"""
        return day_summary.get('open_tariff', 0) >= 2

    def _trigger_a2(self, day_summary):
        """DEAL appears and TARIFF=0"""
        return day_summary.get('deal', 0) >= 1 and day_summary.get('tariff', 0) == 0

    def _trigger_a3(self, day_summary):
        """Pre-market RELIEF"""
        return day_summary.get('pre_relief', 0) >= 1

    def _trigger_b1(self, day_summary):
        """Triple signal fires"""
        return (day_summary.get('tariff', 0) >= 1 and
                day_summary.get('deal', 0) >= 1 and
                day_summary.get('relief', 0) >= 1)

    def _trigger_b2(self, day_summary):
        """3 consecutive days TARIFF then DEAL appears"""
        prev = self.context.get('prev_days', [])
        if len(prev) < 3:
            return False
        streak = all(d.get('tariff', 0) >= 1 for d in prev[-3:])
        return streak and day_summary.get('deal', 0) >= 1

    def _trigger_b3(self, day_summary):
        """Pre-market ACTION + positive"""
        return (day_summary.get('pre_action', 0) >= 1 and
                day_summary.get('positive', 0) >= 2)

    def _trigger_c1(self, day_summary):
        """Burst then silence (with sentiment filter)
        2026-03-15 fix: if negative sentiment (attack/threat/tariff) during burst
        exceeds positive sentiment (positive/deal/relief/market_brag), silence is
        digesting bad news, should not go long. Only triggers when positive > negative.
        """
        if not day_summary.get('burst_then_silence', False):
            return False
        # Sentiment filter: silence after negative burst ≠ bullish
        attack_count = day_summary.get('burst_attack_count', 0)
        positive_count = day_summary.get('burst_positive_count', 0)
        if attack_count > positive_count:
            return False
        return True

    def _trigger_c2(self, day_summary):
        """Market bragging ≥3"""
        return day_summary.get('market_brag', 0) >= 3

    def _trigger_c3(self, day_summary):
        """Late-night tariff"""
        return day_summary.get('night_tariff', 0) >= 1

    def _trigger_d1(self, day_summary):
        """New slogan appears"""
        return day_summary.get('new_phrase_detected', False)

    def _trigger_d2(self, day_summary):
        """POTUS-level signature"""
        return day_summary.get('sig_potus', 0) >= 1

    def _trigger_d3(self, day_summary):
        """Post volume spike"""
        prev = self.context.get('prev_days', [])
        if len(prev) < 7:
            return False
        avg = sum(d.get('post_count', 0) for d in prev[-7:]) / 7
        return avg > 0 and day_summary.get('post_count', 0) > avg * 2

    def run_predictions(self, day_summary, date):
        """Run all models on today's data, generate predictions"""
        predictions = []

        for model_id, model in self.models.items():
            try:
                if model['trigger'](day_summary):
                    # Finding #4: Check if this model was already triggered today (date deduplication)
                    if (model_id, date) in self._triggered_set:
                        continue  # Already triggered today, skip

                    if model_id not in self.scores:
                        self.scores[model_id] = {
                            'predictions': 0, 'correct': 0, 'wrong': 0,
                            'pending': 0, 'total_return': 0, 'trades': []
                        }

                    pred = {
                        'model_id': model_id,
                        'model_name': model['name'],
                        'date_signal': date,
                        'direction': model['direction'],
                        'hold_days': model['hold'],
                        'status': 'PENDING',
                        'created_at': datetime.now(timezone.utc).isoformat(),
                        'day_summary': {k: v for k, v in day_summary.items()
                                       if not isinstance(v, (set, list))},
                    }
                    predictions.append(pred)

                    # Update score + record as triggered
                    self.scores[model_id]['predictions'] += 1
                    self.scores[model_id]['pending'] += 1
                    self._triggered_set.add((model_id, date))

            except Exception as e:
                logging.exception(f"Model {model_id} failed: {e}")

        return predictions


# ============================================================
# Data Fetching
# ============================================================

def fetch_latest_posts(limit=50):
    """Fetch latest posts from CNN Archive"""
    try:
        req = urllib.request.Request(ARCHIVE_URL)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode('utf-8')

        reader = csv.DictReader(content.splitlines())
        rows = list(reader)

        # Only take latest N posts with text, non-RT
        results = []
        for row in rows[:limit * 3]:
            if row['content'].strip() and not row['content'].strip().startswith('RT @'):
                results.append({
                    'id': row['id'],
                    'created_at': row['created_at'],
                    'content': row['content'],
                    'url': row.get('url', ''),
                })
            if len(results) >= limit:
                break

        return results

    except Exception as e:
        print(f"  ⚠️ Fetch failed: {e}")
        return []


def summarize_day(day_posts):
    """Aggregate a day's posts into day_summary"""
    summary = defaultdict(int)
    summary['post_count'] = len(day_posts)
    summary['contents'] = []

    intervals = []
    burst_then_silence = False

    for i, p in enumerate(day_posts):
        content = p['content']
        signals = classify_signals(content)
        session = market_session(p['created_at'])
        h, m = est_hour(p['created_at'])

        for sig in signals:
            summary[sig.lower()] += 1
            if session == 'PRE_MARKET':
                summary[f'pre_{sig.lower()}'] += 1
            elif session == 'MARKET_OPEN':
                summary[f'open_{sig.lower()}'] += 1

        # 深夜推文
        if h < 5 or h >= 23:
            if 'TARIFF' in signals:
                summary['night_tariff'] += 1

        summary['emotion_sum'] += emotion_score(content)
        summary['contents'].append(content[:80])

        # 計算間隔
        if i > 0:
            dt1 = datetime.fromisoformat(day_posts[i-1]['created_at'].replace('Z', '+00:00'))
            dt2 = datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))
            gap = (dt2 - dt1).total_seconds() / 60
            intervals.append(gap)

    # Detect burst→silence
    # 2026-03-15 fix: Also record positive/negative sentiment counts during burst for C1 filtering
    if intervals:
        burst_count = sum(1 for g in intervals if g < 5)
        silence = max(intervals) if intervals else 0
        if burst_count >= 3 and silence >= 180:
            summary['burst_then_silence'] = True
            # Count positive/negative signals during burst period (consecutive posts < 5 min apart)
            burst_attack = 0
            burst_positive = 0
            for idx_iv, gap in enumerate(intervals):
                if gap < 5:
                    # intervals[i] corresponds to gap between day_posts[i] and day_posts[i+1]
                    # Count both posts in burst
                    for pidx in (idx_iv, idx_iv + 1):
                        if pidx < len(day_posts):
                            sigs = classify_signals(day_posts[pidx]['content'])
                            if 'ATTACK' in sigs or 'THREAT' in sigs or 'TARIFF' in sigs:
                                burst_attack += 1
                            if 'POSITIVE' in sigs or 'DEAL' in sigs or 'RELIEF' in sigs or 'MARKET_BRAG' in sigs:
                                burst_positive += 1
            summary['burst_attack_count'] = burst_attack
            summary['burst_positive_count'] = burst_positive

    # Signature detection
    for p in day_posts:
        c = p['content']
        if 'PRESIDENT OF THE UNITED STATES' in c:
            summary['sig_potus'] += 1
        if 'President DJT' in c:
            summary['sig_djt'] += 1

    summary['avg_emotion'] = summary['emotion_sum'] / max(len(day_posts), 1)

    return dict(summary)


# ============================================================
# Backtest Mode
# ============================================================

def run_backtest():
    """Backtest all 12 prediction models with historical data"""
    print("=" * 90)
    print("🔬 Backtest Mode: Validate 12 prediction models with historical data")
    print("=" * 90)

    # Load data
    with open(BASE / "clean_president.json", encoding='utf-8') as f:
        posts = json.load(f)

    with open(DATA / "market_SP500.json", encoding='utf-8') as f:
        sp500 = json.load(f)

    sp_by_date = {r['date']: r for r in sp500}

    originals = sorted(
        [p for p in posts if p['has_text'] and not p['is_retweet']],
        key=lambda p: p['created_at']
    )

    # Group by day
    daily_posts = defaultdict(list)
    for p in originals:
        daily_posts[p['created_at'][:10]].append(p)

    engine = PredictionEngine()
    all_predictions = []
    sorted_dates = sorted(daily_posts.keys())

    for idx, date in enumerate(sorted_dates):
        day_summary = summarize_day(daily_posts[date])

        # Update context
        engine.context['prev_days'] = [
            summarize_day(daily_posts.get(sorted_dates[j], []))
            for j in range(max(0, idx-7), idx)
        ]

        # Run predictions
        preds = engine.run_predictions(day_summary, date)

        # Verify predictions
        for pred in preds:
            hold = pred['hold_days']
            direction = pred['direction']

            # Find entry/exit dates
            td = date
            if td not in sp_by_date:
                dt = datetime.strptime(td, '%Y-%m-%d')
                for i in range(1, 5):
                    d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
                    if d in sp_by_date:
                        td = d
                        break
                else:
                    continue

            if hold == 0:
                # Same day
                if td in sp_by_date:
                    sp = sp_by_date[td]
                    ret = (sp['close'] - sp['open']) / sp['open'] * 100
                else:
                    continue
            else:
                # N days later
                entry_day = td
                exit_day = entry_day
                for _ in range(hold):
                    dt = datetime.strptime(exit_day, '%Y-%m-%d')
                    for i in range(1, 6):
                        d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
                        if d in sp_by_date:
                            exit_day = d
                            break

                if exit_day not in sp_by_date or entry_day not in sp_by_date:
                    continue

                entry_p = sp_by_date[entry_day]['open']
                exit_p = sp_by_date[exit_day]['close']
                ret = (exit_p - entry_p) / entry_p * 100

            # Determine if prediction is correct
            if direction == 'LONG':
                correct = ret > 0
            elif direction == 'SHORT':
                correct = ret < 0
            elif direction == 'VOLATILE':
                correct = abs(ret) > 0.5  # Volatility exceeds 0.5%
            else:
                correct = False

            pred['actual_return'] = round(ret, 3)
            pred['correct'] = correct
            pred['status'] = 'VERIFIED'

            # Update scoring
            mid = pred['model_id']
            if mid in engine.scores:
                engine.scores[mid]['pending'] = max(0, engine.scores[mid].get('pending', 0) - 1)
                if correct:
                    engine.scores[mid]['correct'] += 1
                else:
                    engine.scores[mid]['wrong'] += 1
                engine.scores[mid]['total_return'] += ret
                engine.scores[mid]['trades'].append({
                    'date': date, 'return': round(ret, 3), 'correct': correct
                })

        all_predictions.extend(preds)

    # === Print Scorecard ===
    print(f"\n📊 12 Prediction Models Scorecard")
    print(f"{'='*90}")
    print(f"  {'Model':4s} {'Name':25s} | {'Pred':>4s} | {'Hit':>4s} | {'Rate':>6s} | {'Avg Return':>8s} | {'Total':>8s} | Verdict")
    print(f"  {'-'*4} {'-'*25}-+-{'-'*4}-+-{'-'*4}-+-{'-'*6}-+-{'-'*8}-+-{'-'*8}-+-{'-'*6}")

    rankings = []
    for mid, model in engine.models.items():
        s = engine.scores.get(mid, {})
        total = s.get('predictions', 0)
        correct = s.get('correct', 0)
        wrong = s.get('wrong', 0)
        total_ret = s.get('total_return', 0)

        if total == 0:
            continue

        hit_rate = correct / total * 100 if total > 0 else 0
        avg_ret = total_ret / total if total > 0 else 0

        # Verdict
        if hit_rate >= 60 and avg_ret > 0:
            verdict = "⭐Valid"
        elif hit_rate >= 55:
            verdict = "🟡Watch"
        elif hit_rate >= 50:
            verdict = "➡️Neutral"
        else:
            verdict = "❌Invalid"

        rankings.append((mid, model['name'], total, correct, hit_rate, avg_ret, total_ret, verdict))

    # Sort by hit rate
    rankings.sort(key=lambda x: (-x[4], -x[5]))

    for mid, name, total, correct, hit_rate, avg_ret, total_ret, verdict in rankings:
        print(f"  {mid:4s} {name:25s} | {total:4d} | {correct:4d} | {hit_rate:5.1f}% | {avg_ret:+.3f}% | {total_ret:+.2f}% | {verdict}")

    # Save files
    engine.save_scores()

    # Save all predictions
    with open(PREDICTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_predictions, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Predictions saved to {PREDICTIONS_FILE.name}")
    print(f"💾 Scores saved to {SCORES_FILE.name}")

    # === Best Combination ===
    print(f"\n{'='*90}")
    print("🏆 Best Combination Strategy: Only act when Top 3 models all confirm")
    print("=" * 90)

    top3 = [r[0] for r in rankings[:3]]
    print(f"  Top 3: {', '.join(top3)}")

    # Find days when all three models triggered
    pred_by_date = defaultdict(set)
    pred_ret_by_date = {}
    for p in all_predictions:
        if p.get('status') == 'VERIFIED':
            pred_by_date[p['date_signal']].add(p['model_id'])
            pred_ret_by_date[(p['date_signal'], p['model_id'])] = p.get('actual_return', 0)

    combo_days = []
    for date, models in pred_by_date.items():
        overlap = set(top3) & models
        if len(overlap) >= 2:  # At least 2 Top models agree
            rets = [pred_ret_by_date.get((date, m), 0) for m in overlap]
            avg_r = sum(rets) / len(rets) if rets else 0
            combo_days.append((date, len(overlap), avg_r, overlap))

    if combo_days:
        combo_days.sort(key=lambda x: x[0])
        wins = sum(1 for _, _, r, _ in combo_days if r > 0)
        total_r = sum(r for _, _, r, _ in combo_days)
        avg_combo = total_r / len(combo_days)

        print(f"  Days with simultaneous triggers: {len(combo_days)}")
        print(f"  Win rate: {wins/len(combo_days)*100:.1f}%")
        print(f"  Average return: {avg_combo:+.3f}%")
        print(f"\n  Details:")
        for date, n_models, ret, models in combo_days:
            arrow = "✅" if ret > 0 else "❌"
            print(f"    {date} | {n_models} models agree | {ret:+.3f}% {arrow} | {','.join(sorted(models))}")

    return engine


# ============================================================
# Real-time Monitor Mode
# ============================================================

def run_monitor():
    """Real-time monitoring (every 5 minutes)"""
    print("=" * 90)
    print("🔴 Trump Code Real-time Monitor — Starting")
    print(f"   Update frequency: Every 5 minutes")
    print(f"   Data source: CNN Truth Social Archive")
    print(f"   Prediction models: 12 running simultaneously")
    print("=" * 90)

    engine = PredictionEngine()

    # Read last seen post
    last_seen = ""
    if LAST_POST_FILE.exists():
        last_seen = LAST_POST_FILE.read_text().strip()

    cycle = 0
    while True:
        cycle += 1
        now = datetime.now(timezone.utc)
        est_h, est_m = est_hour(now.isoformat())

        print(f"\n{'─'*60}")
        print(f"  Cycle {cycle} | UTC {now.strftime('%H:%M')} | EST {est_h:02d}:{est_m:02d}")

        # Fetch latest posts
        new_posts = fetch_latest_posts(20)
        if not new_posts:
            print("  ⚠️ Fetch failed, retrying in 1 minute")
            time.sleep(60)
            continue

        latest_id = new_posts[0]['id']
        latest_time = new_posts[0]['created_at']

        # Check for new posts
        if latest_id == last_seen:
            print(f"  💤 No new posts (latest: {latest_time[:16]})")
            time.sleep(60)
            continue

        # New posts found!
        new_count = 0
        for p in new_posts:
            if p['id'] == last_seen:
                break
            new_count += 1

        print(f"  🆕 Found {new_count} new posts!")

        # Display new posts
        for p in new_posts[:new_count]:
            signals = classify_signals(p['content'])
            session = market_session(p['created_at'])
            emo = emotion_score(p['content'])
            h, m = est_hour(p['created_at'])

            signal_str = ' '.join(f"[{s}]" for s in sorted(signals)) if signals else '(No signal)'

            print(f"\n  📝 EST {h:02d}:{m:02d} | {session} | Sentiment:{emo:.0f}")
            print(f"     Signals: {signal_str}")
            print(f"     Content: {p['content'][:120]}...")

        # Group by today
        today = now.strftime('%Y-%m-%d')
        today_posts = [p for p in new_posts if p['created_at'][:10] == today]

        if today_posts:
            day_summary = summarize_day(today_posts)

            # Run predictions
            preds = engine.run_predictions(day_summary, today)

            if preds:
                print(f"\n  🎯 Triggered {len(preds)} prediction models:")
                for pred in preds:
                    dir_icon = {'LONG': '📈Long', 'SHORT': '📉Short', 'VOLATILE': '🌊Volatile'}
                    print(f"     [{pred['model_id']}] {pred['model_name']}")
                    print(f"       → {dir_icon.get(pred['direction'], '?')} | Hold {pred['hold_days']} days")
            else:
                print(f"\n  😴 No models triggered today")

        # Update latest ID
        last_seen = latest_id
        LAST_POST_FILE.write_text(latest_id)

        # Display cumulative scores
        print(f"\n  📊 Model Real-time Scores:")
        for mid, s in engine.scores.items():
            total = s['predictions']
            if total > 0:
                correct = s['correct']
                rate = correct / max(total - s['pending'], 1) * 100
                print(f"     {mid:20s} | {total} times | Hit rate {rate:.0f}%")

        engine.save_scores()

        print(f"\n  ⏳ Waiting 1 minute...")
        time.sleep(60)


# ============================================================
# Status View
# ============================================================

def show_status():
    """Display current scores of each model"""
    print("=" * 90)
    print("📊 Trump Code — Model Prediction Scores")
    print("=" * 90)

    if not SCORES_FILE.exists():
        print("  No scores yet, please run --backtest first")
        return

    with open(SCORES_FILE, encoding='utf-8') as f:
        scores = json.load(f)

    engine = PredictionEngine()

    print(f"\n  {'Model':25s} | {'Pred':>4s} | {'Hit':>4s} | {'Miss':>4s} | {'Rate':>6s} | {'Total Return':>8s}")
    print(f"  {'-'*25}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*6}-+-{'-'*8}")

    for mid, model in engine.models.items():
        s = scores.get(mid, {})
        total = s.get('predictions', 0)
        correct = s.get('correct', 0)
        wrong = s.get('wrong', 0)
        total_ret = s.get('total_return', 0)
        rate = correct / max(total - s.get('pending', 0), 1) * 100

        print(f"  {model['name']:25s} | {total:4d} | {correct:4d} | {wrong:4d} | {rate:5.1f}% | {total_ret:+.2f}%")


# ============================================================
# Main Program
# ============================================================

if __name__ == '__main__':
    if '--backtest' in sys.argv:
        run_backtest()
    elif '--status' in sys.argv:
        show_status()
    elif '--once' in sys.argv:
        # Run once (no loop)
        print("🔍 Single scan...")
        new_posts = fetch_latest_posts(30)
        if new_posts:
            today = new_posts[0]['created_at'][:10]
            today_posts = [p for p in new_posts if p['created_at'][:10] == today]
            day_summary = summarize_day(today_posts)

            engine = PredictionEngine()
            preds = engine.run_predictions(day_summary, today)

            print(f"\n📝 Today ({today}) {len(today_posts)} posts")
            print(f"🎯 Triggered {len(preds)} predictions:")
            for pred in preds:
                dir_icon = {'LONG': '📈Long', 'SHORT': '📉Short', 'VOLATILE': '🌊Volatile'}
                print(f"   [{pred['model_id']}] {pred['model_name']} → {dir_icon.get(pred['direction'], '?')}")

            # Display today's signals
            print(f"\n📊 Today's signals:")
            for k, v in sorted(day_summary.items()):
                if isinstance(v, (int, float)) and v > 0 and k != 'post_count':
                    print(f"   {k}: {v}")
    else:
        run_monitor()

