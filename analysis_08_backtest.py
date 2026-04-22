#!/usr/bin/env python3
"""
Trump Code Analysis #8 - Backtest Validation
Run historical data through 5 rules, see profit and win rate for each
Control group: Same period Buy & Hold S&P500
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from utils import est_hour

BASE = Path(__file__).parent


def main():
    with open(BASE / "clean_president.json", 'r', encoding='utf-8') as f:
        posts = json.load(f)

    DATA = BASE / "data"

    with open(DATA / "market_SP500.json", 'r', encoding='utf-8') as f:
        sp500 = json.load(f)

    with open(DATA / "market_NASDAQ.json", 'r', encoding='utf-8') as f:
        nasdaq = json.load(f)

    sp_by_date = {r['date']: r for r in sp500}
    nq_by_date = {r['date']: r for r in nasdaq}

    originals = sorted(
        [p for p in posts if p['has_text'] and not p['is_retweet']],
        key=lambda p: p['created_at']
    )

    # === Utility Functions ===

    def classify_post(content):
        cl = content.lower()
        signals = set()
        if any(w in cl for w in ['tariff', 'tariffs', 'duty', 'duties', 'reciprocal']):
            signals.add('TARIFF')
        if any(w in cl for w in ['deal', 'agreement', 'negotiate', 'talks', 'signed']):
            signals.add('DEAL')
        if any(w in cl for w in ['pause', 'delay', 'exempt', 'exception', 'reduce', 'suspend', 'postpone']):
            signals.add('RELIEF')
        if any(w in cl for w in ['stock market', 'all time high', 'record high', 'dow', 'nasdaq', 'market up']):
            signals.add('MARKET_BRAG')
        if any(w in cl for w in ['china', 'chinese', 'beijing']):
            signals.add('CHINA')
        if any(w in cl for w in ['immediately', 'effective', 'hereby', 'i have directed', 'executive order', 'just signed']):
            signals.add('ACTION')
        return signals

    def market_session(utc_str):
        h, m = est_hour(utc_str)
        if h < 9 or (h == 9 and m < 30):
            return 'PRE_MARKET'
        elif h < 16:
            return 'MARKET_OPEN'
        elif h < 20:
            return 'AFTER_HOURS'
        else:
            return 'OVERNIGHT'

    def next_trading_day(date_str, market=None):
        if market is None:
            market = sp_by_date
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        for i in range(1, 6):
            d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
            if d in market:
                return d
        return None

    def trading_day_offset(date_str, offset, market=None):
        """Get date N trading days later"""
        if market is None:
            market = sp_by_date
        d = date_str
        for _ in range(abs(offset)):
            d = next_trading_day(d, market) if offset > 0 else None
            if not d:
                return None
        return d


    # === Daily Signal Aggregation ===

    daily_signals = defaultdict(lambda: {
        'tariff': 0, 'deal': 0, 'relief': 0, 'market_brag': 0,
        'action': 0, 'china': 0, 'posts': 0,
        'pre_tariff': 0, 'pre_deal': 0, 'pre_relief': 0,
        'open_tariff': 0, 'open_deal': 0,
        # pre_close_* = pre-market + market hours (until 16:00), excluding after-hours/overnight posts
        # Used to correct look-ahead bias: signals only use information available before market close
        'pre_close_tariff': 0, 'pre_close_deal': 0, 'pre_close_relief': 0,
        'pre_close_market_brag': 0, 'pre_close_action': 0,
    })

    for p in originals:
        date = p['created_at'][:10]
        signals = classify_post(p['content'])
        session = market_session(p['created_at'])
        d = daily_signals[date]
        d['posts'] += 1

        for sig in signals:
            d[sig.lower()] = d.get(sig.lower(), 0) + 1
            if session == 'PRE_MARKET':
                d[f'pre_{sig.lower()}'] = d.get(f'pre_{sig.lower()}', 0) + 1
                d[f'pre_close_{sig.lower()}'] = d.get(f'pre_close_{sig.lower()}', 0) + 1
            elif session == 'MARKET_OPEN':
                d[f'open_{sig.lower()}'] = d.get(f'open_{sig.lower()}', 0) + 1
                d[f'pre_close_{sig.lower()}'] = d.get(f'pre_close_{sig.lower()}', 0) + 1
            # AFTER_HOURS / OVERNIGHT not counted in pre_close_*


    print("=" * 90)
    print("📊 Trump Code Backtest - 5 Rules Historical Validation")
    print("=" * 90)

    # === Buy & Hold Baseline ===
    first_day = sp500[0]
    last_day = sp500[-1]
    bh_return = (last_day['close'] - first_day['open']) / first_day['open'] * 100
    print(f"\n📈 Baseline: Buy & Hold S&P500")
    print(f"   Period: {first_day['date']} ~ {last_day['date']}")
    print(f"   Starting (open): {first_day['open']:,.2f} → Ending (close): {last_day['close']:,.2f}")
    print(f"   Return: {bh_return:+.2f}%")
    print(f"   Trading Days: {len(sp500)} days")
    print(f"\n   ⚠️  Look-ahead Bias Correction: Signal triggers only use PRE_MARKET + MARKET_OPEN posts")
    print(f"      AFTER_HOURS/OVERNIGHT posts not counted in signals to eliminate look-ahead bias")


    # === Backtest Framework ===

    class Trade:
        def __init__(self, rule, date, direction, entry_price, reason):
            self.rule = rule
            self.entry_date = date
            self.direction = direction  # 'LONG' or 'SHORT'
            self.entry_price = entry_price
            self.reason = reason
            self.exit_date = None
            self.exit_price = None
            self.return_pct = None
            self.hold_days = None

        def close(self, exit_date, exit_price):
            self.exit_date = exit_date
            self.exit_price = exit_price
            if self.direction == 'LONG':
                self.return_pct = (exit_price - self.entry_price) / self.entry_price * 100
            else:
                self.return_pct = (self.entry_price - exit_price) / self.entry_price * 100
            d1 = datetime.strptime(self.entry_date, '%Y-%m-%d')
            d2 = datetime.strptime(self.exit_date, '%Y-%m-%d')
            self.hold_days = (d2 - d1).days


    def run_rule(rule_name, trigger_fn, direction, hold_days_target, market=None):
        """Generic backtest executor"""
        if market is None:
            market = sp_by_date
        trades = []
        sorted_dates = sorted(daily_signals.keys())

        for i, date in enumerate(sorted_dates):
            if date not in market:
                # Weekend/holiday → use next trading day
                td = next_trading_day(date, market)
                if not td:
                    continue
            else:
                td = date

            # Check trigger condition
            # today_pre_close: only contains pre-market + market hours signals, excluding after-hours posts (corrects look-ahead bias)
            sig = daily_signals[date]
            pre_close_view = {k.replace('pre_close_', ''): v for k, v in sig.items() if k.startswith('pre_close_')}
            context = {
                'date': date,
                'today': daily_signals[date],
                'today_pre_close': pre_close_view,  # No look-ahead bias version
                'prev_3': [daily_signals[sorted_dates[j]] for j in range(max(0,i-3), i)],
                'prev_7': [daily_signals[sorted_dates[j]] for j in range(max(0,i-7), i)],
            }

            if trigger_fn(context):
                # Buy at next trading day open
                entry_day = next_trading_day(td, market)
                if not entry_day or entry_day not in market:
                    continue

                entry_price = market[entry_day]['open']

                # Sell after holding N trading days
                exit_day = entry_day
                for _ in range(hold_days_target):
                    nd = next_trading_day(exit_day, market)
                    if nd:
                        exit_day = nd
                    else:
                        break

                if exit_day not in market:
                    continue

                exit_price = market[exit_day]['close']

                trade = Trade(rule_name, entry_day, direction, entry_price,
                             f"{date} signal")
                trade.close(exit_day, exit_price)
                trades.append(trade)

        return trades


    def print_rule_results(rule_name, trades, description):
        """Print backtest results for a single rule"""
        if not trades:
            print(f"\n  ❌ {rule_name}: No triggers")
            return None  # P4-1: Explicitly return None

        wins = [t for t in trades if t.return_pct > 0]
        losses = [t for t in trades if t.return_pct <= 0]
        returns = [t.return_pct for t in trades]

        total_return = sum(returns)
        avg_return = total_return / len(returns)
        win_rate = len(wins) / len(trades) * 100
        avg_win = sum(t.return_pct for t in wins) / len(wins) if wins else 0
        # P4-1: avg_loss divide by zero protection (return 0 if losses is empty)
        avg_loss = sum(t.return_pct for t in losses) / len(losses) if losses else 0
        max_win = max(returns)
        max_loss = min(returns)
        avg_hold = sum(t.hold_days for t in trades) / len(trades)

        # Assume $10,000 investment each time
        capital = 10000
        cumulative = capital
        peak = capital
        max_drawdown = 0
        for t in trades:
            cumulative *= (1 + t.return_pct / 100)
            peak = max(peak, cumulative)
            dd = (peak - cumulative) / peak * 100
            max_drawdown = max(max_drawdown, dd)

        final_value = cumulative

        print(f"\n  {'='*85}")
        print(f"  📋 Rule: {rule_name}")
        print(f"  📝 {description}")
        print(f"  {'='*85}")
        print(f"  Trade Count:      {len(trades):5d}")
        print(f"  Win Rate:         {win_rate:5.1f}%  ({len(wins)} wins {len(losses)} losses)")
        print(f"  Average Return:   {avg_return:+.3f}% / trade")
        print(f"  Total Return:     {total_return:+.2f}%")
        print(f"  Average Hold:     {avg_hold:.1f} days")
        print(f"  Average Win:      {avg_win:+.3f}%")
        print(f"  Average Loss:     {avg_loss:+.3f}%")
        print(f"  Max Single Win:   {max_win:+.2f}%")
        print(f"  Max Single Loss:  {max_loss:+.2f}%")
        # P4-1: avg_loss == 0 return 999 (no losses, infinite profit/loss ratio)
        profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 999
        print(f"  Profit/Loss Ratio: {profit_loss_ratio:.2f}")
        print(f"  Max Drawdown:     {max_drawdown:.2f}%")
        print(f"  $10K →            ${final_value:,.0f}  ({(final_value/capital-1)*100:+.1f}%)")

        # Display each trade
        print(f"\n  📋 Trade Details:")
        print(f"  {'Entry':12s} | {'Exit':12s} | {'Entry Price':>10s} | {'Exit Price':>10s} | {'Return':>8s} | {'Cumulative':>10s}")
        cum = capital
        for t in trades:
            cum *= (1 + t.return_pct / 100)
            arrow = "✅" if t.return_pct > 0 else "❌"
            print(f"  {t.entry_date:12s} | {t.exit_date:12s} | {t.entry_price:>10,.2f} | {t.exit_price:>10,.2f} | {t.return_pct:+.2f}% {arrow} | ${cum:>9,.0f}")

        return {
            'trades': len(trades),
            'win_rate': round(win_rate, 1),
            'avg_return': round(avg_return, 3),
            'total_return': round(total_return, 2),
            'max_drawdown': round(max_drawdown, 2),
            'final_value': round(final_value, 0),
        }


    # ============================================================
    # Rule 1: Pre-market RELIEF signal → Buy at open, hold 1 day
    # ============================================================
    def rule1_trigger(ctx):
        # Use pre_close version (pre-market + market hours only), avoid look-ahead bias
        return ctx['today'].get('pre_relief', 0) >= 1  # pre_relief is already pre-market signal

    trades_r1 = run_rule('R1', rule1_trigger, 'LONG', 1)
    r1 = print_rule_results(
        "Rule 1: Pre-market RELIEF → Buy 1 day",
        trades_r1,
        "When he says 'pause/exempt/suspend' before market open → Buy at next trading day open, sell at close"
    )


    # ============================================================
    # Rule 2: Market hours TARIFF mention → Hedge (short 1 day)
    # ============================================================
    def rule2_trigger(ctx):
        return ctx['today'].get('open_tariff', 0) >= 2  # Mentioned tariff ≥2 times during market hours

    trades_r2 = run_rule('R2', rule2_trigger, 'SHORT', 1)
    r2 = print_rule_results(
        "Rule 2: Market hours TARIFF×2 → Short 1 day",
        trades_r2,
        "When he mentions tariff ≥2 times during trading hours → Short at next trading day open, cover at close"
    )


    # ============================================================
    # Rule 3: 3 consecutive days TARIFF → DEAL appears → Buy 2 days
    # ============================================================
    def rule3_trigger(ctx):
        prev = ctx['prev_3']
        if len(prev) < 3:
            return False
        tariff_streak = all(d['tariff'] >= 1 for d in prev)
        # Only use pre-market + market hours deal signals (avoid look-ahead bias)
        deal_today = ctx['today_pre_close'].get('deal', 0) >= 1
        return tariff_streak and deal_today

    trades_r3 = run_rule('R3', rule3_trigger, 'LONG', 2)
    r3 = print_rule_results(
        "Rule 3: 3-day TARIFF streak then DEAL → Buy 2 days",
        trades_r3,
        "After 3 consecutive days of tariff mentions, DEAL signal appears → Buy the turning point, hold 2 trading days"
    )


    # ============================================================
    # Rule 4: Three signals together (TARIFF+DEAL+RELIEF same day) → Buy 3 days
    # ============================================================
    def rule4_trigger(ctx):
        # Use pre-market + market hours signals, avoid look-ahead bias
        t = ctx['today_pre_close']
        return t.get('tariff', 0) >= 1 and t.get('deal', 0) >= 1 and t.get('relief', 0) >= 1

    trades_r4 = run_rule('R4', rule4_trigger, 'LONG', 3)
    r4 = print_rule_results(
        "Rule 4: TARIFF+DEAL+RELIEF together → Buy 3 days",
        trades_r4,
        "Same day has all three signals: tariff+deal+relief → Buy the bottom, hold 3 trading days"
    )


    # ============================================================
    # Rule 5: He actively brags about stock market → Sell signal (short 1 day)
    # ============================================================
    def rule5_trigger(ctx):
        # Use pre-market + market hours signals, avoid look-ahead bias
        return ctx['today_pre_close'].get('market_brag', 0) >= 2  # Brags about market ≥2 times a day

    trades_r5 = run_rule('R5', rule5_trigger, 'SHORT', 1)
    r5 = print_rule_results(
        "Rule 5: Market bragging×2 → Short 1 day",
        trades_r5,
        "When he mentions stock market/all-time high ≥2 times in one day → Short-term top, short next day for 1 day"
    )


    # ============================================================
    # Bonus Rule: High volume day (≥30 posts) + TARIFF → Buy 2 days
    # ============================================================
    def rule6_trigger(ctx):
        # posts uses all-day, tariff uses pre-market + market hours (avoid look-ahead bias)
        t = ctx['today']
        t_pc = ctx['today_pre_close']
        return t['posts'] >= 30 and t_pc.get('tariff', 0) >= 3

    trades_r6 = run_rule('R6', rule6_trigger, 'LONG', 2)
    r6 = print_rule_results(
        "Rule 6: High volume (≥30 posts) + dense tariff → Buy 2 days",
        trades_r6,
        "One day with ≥30 posts and tariff mentioned ≥3 times → Market panic extreme, bounce imminent"
    )


    # ============================================================
    # Bonus Rule: Pre-market ACTION → Buy 1 day
    # ============================================================
    def rule7_trigger(ctx):
        return ctx['today'].get('pre_action', 0) >= 1

    for p in originals:
        date = p['created_at'][:10]
        signals = classify_post(p['content'])
        session = market_session(p['created_at'])
        if session == 'PRE_MARKET' and 'ACTION' in signals:
            daily_signals[date]['pre_action'] = daily_signals[date].get('pre_action', 0) + 1

    trades_r7 = run_rule('R7', rule7_trigger, 'LONG', 1)
    r7 = print_rule_results(
        "Rule 7: Pre-market ACTION (signing/order) → Buy 1 day",
        trades_r7,
        "When he announces signing/executive order before market open → Buy at open, sell at close same day"
    )


    # ============================================================
    # Combined Strategy: Rules 1+3+4+6 running simultaneously
    # ============================================================
    print(f"\n{'='*90}")
    print("🏆 Combined Strategy Backtest: Rules 1+3+4+6 Running Simultaneously")
    print("   Each rule triggers independently, no duplicate entries (only one entry per day)")
    print("=" * 90)

    all_trades = []
    used_dates = set()

    for trades, priority in [(trades_r4, 4), (trades_r1, 1), (trades_r6, 6), (trades_r3, 3)]:
        for t in trades:
            if t.entry_date not in used_dates:
                all_trades.append(t)
                used_dates.add(t.entry_date)

    all_trades.sort(key=lambda t: t.entry_date)

    if all_trades:
        capital = 10000
        cumulative = capital
        peak = capital
        max_dd = 0
        wins = sum(1 for t in all_trades if t.return_pct > 0)

        for t in all_trades:
            cumulative *= (1 + t.return_pct / 100)
            peak = max(peak, cumulative)
            dd = (peak - cumulative) / peak * 100
            max_dd = max(max_dd, dd)

        total_ret = sum(t.return_pct for t in all_trades)
        avg_ret = total_ret / len(all_trades)

        print(f"  Trade Count:      {len(all_trades)}")
        print(f"  Win Rate:         {wins/len(all_trades)*100:.1f}%")
        print(f"  Average Return:   {avg_ret:+.3f}% / trade")
        print(f"  Total Return:     {total_ret:+.2f}%")
        print(f"  Max Drawdown:     {max_dd:.2f}%")
        print(f"  $10K →            ${cumulative:,.0f}")
        print(f"  vs Buy&Hold:      {bh_return:+.2f}%")


    # ============================================================
    # Summary
    # ============================================================
    print(f"\n{'='*90}")
    print("📊 Trump Code Backtest Summary")
    print("=" * 90)
    print(f"  {'Rule':40s} | {'Count':>4s} | {'Win%':>5s} | {'Avg':>8s} | {'$10K→':>10s}")
    print(f"  {'-'*40}-+-{'-'*4}-+-{'-'*5}-+-{'-'*8}-+-{'-'*10}")

    all_results = [
        ('R1: Pre-market RELIEF→Buy 1 day', r1),
        ('R2: Market hours TARIFF×2→Short 1 day', r2),
        ('R3: 3-day TARIFF then DEAL→Buy 2 days', r3),
        ('R4: Three signals together→Buy 3 days', r4),
        ('R5: Market bragging×2→Short 1 day', r5),
        ('R6: High volume + dense tariff→Buy 2 days', r6),
        ('R7: Pre-market ACTION→Buy 1 day', r7),
    ]

    for name, result in all_results:
        if result:
            print(f"  {name:40s} | {result['trades']:4d} | {result['win_rate']:4.1f}% | {result['avg_return']:+.3f}% | ${result['final_value']:>9,.0f}")
        else:
            print(f"  {name:40s} | {'N/A':>4s} |  {'N/A':>4s} |   {'N/A':>6s} |    {'N/A':>6s}")

    print(f"  {'-'*40}-+-{'-'*4}-+-{'-'*5}-+-{'-'*8}-+-{'-'*10}")
    print(f"  {'Buy & Hold S&P500 (Control)':40s} | {len(sp500):4d} | {'N/A':>5s} | {'N/A':>8s} | ${10000*(1+bh_return/100):>9,.0f}")

    # Save results
    summary = {'buy_hold_return': round(bh_return, 2)}
    for name, result in all_results:
        if result:
            summary[name] = result

    with open(DATA / 'results_08_backtest.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Detailed results saved to results_08_backtest.json")


if __name__ == '__main__':
    main()
