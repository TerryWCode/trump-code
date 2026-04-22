#!/usr/bin/env python3
"""
Trump Code CLI - Query signals and arbitrage opportunities

Installation:
  git clone https://github.com/sstklen/trump-code.git
  cd trump-code
  pip install -r requirements.txt

Usage:
  python trump_code_cli.py signals          # View today's signals
  python trump_code_cli.py models           # View model rankings
  python trump_code_cli.py predict          # View today's prediction
  python trump_code_cli.py arbitrage        # Prediction market arbitrage opportunities
  python trump_code_cli.py history          # Historical accuracy
  python trump_code_cli.py report           # Full daily report
  python trump_code_cli.py json             # Output all as JSON
  python trump_code_cli.py health           # System health

API Usage (JSON output):
  python trump_code_cli.py json | jq '.signals'
  python trump_code_cli.py json | jq '.prediction'
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"


def _load(filename: str) -> dict | list | None:
    """安全載入 JSON 檔案。"""
    path = DATA / filename
    if not path.exists():
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def cmd_signals():
    """查看今日信號"""
    report = _load('daily_report.json')
    ai = _load('opus_analysis.json')

    if not report:
        print("尚無今日報告。請先跑 daily_pipeline.py")
        return

    date = report.get('date', '?')
    signals = report.get('signals_detected', [])
    posts = report.get('posts_today', 0)

    print(f"{'='*50}")
    print(f"  川普密碼 — {date}")
    print(f"{'='*50}")
    print(f"  推文數: {posts}")
    print(f"  偵測信號: {', '.join(signals) if signals else '無'}")
    print()

    if ai and not ai.get('stale'):
        missed = ai.get('missed_signals', {})
        if missed:
            print(f"  🤖 Opus 補充: {missed.get('finding', '')[:100]}")
            print()


def cmd_models():
    """模型排行"""
    report = _load('opus_briefing.json')
    ai = _load('opus_analysis.json')

    if not report or 'model_performance' not in report:
        print("尚無模型數據。")
        return

    perf = report['model_performance']
    sorted_models = sorted(perf.items(), key=lambda x: -x[1].get('win_rate', 0))

    print(f"{'='*70}")
    print(f"  川普密碼 — 模型排行榜")
    print(f"{'='*70}")
    print(f"  {'排名':<4s} {'模型':<30s} {'命中率':>6s} {'報酬':>8s} {'交易數':>6s}")
    print(f"  {'-'*4} {'-'*30} {'-'*6} {'-'*8} {'-'*6}")

    for i, (mid, s) in enumerate(sorted_models, 1):
        name = s.get('name', mid)[:28]
        icon = "⭐" if s['win_rate'] >= 70 else ("⚠️" if s['win_rate'] < 50 else "  ")
        print(f"  {icon}{i:<3d} {name:<30s} {s['win_rate']:5.1f}% {s['avg_return']:+7.3f}% {s['total_trades']:5d}")

    # Opus 建議
    if ai:
        adj = ai.get('models_to_adjust', {})
        boost = adj.get('boost', [])
        eliminate = adj.get('eliminate', [])
        if boost:
            print(f"\n  🤖 Opus 建議加權: {', '.join(m['model'] for m in boost)}")
        if eliminate:
            print(f"  🤖 Opus 建議淘汰: {', '.join(m['model'] for m in eliminate)}")


def cmd_predict():
    """今日預測方向"""
    report = _load('daily_report.json')

    if not report:
        print("尚無預測。")
        return

    direction = report.get('direction_summary', {})
    consensus = direction.get('consensus', 'NEUTRAL')
    long_n = direction.get('LONG', 0)
    short_n = direction.get('SHORT', 0)

    icon = {"BULLISH": "📈", "BEARISH": "📉", "NEUTRAL": "➡️"}.get(consensus, "?")

    print(f"{'='*40}")
    print(f"  今日預測方向")
    print(f"{'='*40}")
    print(f"  {icon} 共識: {consensus}")
    print(f"  做多模型: {long_n} 個")
    print(f"  做空模型: {short_n} 個")
    print()
    print(f"  ⚠️ 這不是投資建議。歷史規律不保證未來表現。")


def cmd_arbitrage():
    """預測市場套利機會"""
    pm = _load('prediction_market_scan.json')

    if not pm:
        print("尚無預測市場掃描。")
        return

    opportunities = pm.get('opportunities', [])
    print(f"{'='*60}")
    print(f"  預測市場套利掃描 — {pm.get('date', '?')}")
    print(f"{'='*60}")
    print(f"  掃描市場數: {pm.get('total_scanned', 0)}")
    print(f"  有價值機會: {len(opportunities)}")

    if opportunities:
        print()
        for i, o in enumerate(opportunities, 1):
            print(f"  {i}. {o.get('market_name', '?')[:50]}")
            print(f"     分數: {o.get('opportunity_score', 0):.3f} | "
                  f"方向: {o.get('expected_direction', '?')} | "
                  f"價格: {o.get('current_price', 0):.1%}")
    else:
        print("\n  目前無套利機會。")


def cmd_history():
    """歷史命中率"""
    report = _load('daily_report.json')

    if not report:
        print("尚無歷史數據。")
        return

    hit = report.get('historical_hit_rate', {})
    print(f"{'='*40}")
    print(f"  歷史命中率")
    print(f"{'='*40}")
    print(f"  已驗證: {hit.get('verified', 0)} 筆")
    print(f"  正確: {hit.get('correct', 0)} 筆")
    print(f"  命中率: {hit.get('rate', 0):.1f}%")


def cmd_health():
    """系統健康度"""
    ai = _load('opus_analysis.json')
    learning = _load('learning_report.json')
    evo = _load('evolution_log.json')

    print(f"{'='*50}")
    print(f"  系統健康度")
    print(f"{'='*50}")

    if ai:
        health = ai.get('overall_system_health', '?')
        icon = {"healthy": "🟢", "needs_attention": "🟡", "degrading": "🔴"}.get(health, "⚪")
        print(f"  {icon} 狀態: {health}")
        print(f"  📋 重點: {ai.get('priority_action', '?')[:80]}")

        if ai.get('pattern_shift_detected'):
            print(f"  ⚠️ 模式變化: {ai.get('pattern_shift_details', '?')[:100]}")

    if learning:
        adj = learning.get('adjustments', {}).get('summary', {})
        print(f"\n  學習引擎: {adj.get('promoted',0)} 升 / {adj.get('demoted',0)} 降 / {adj.get('eliminated',0)} 淘汰")

    if evo and isinstance(evo, list) and evo:
        last = evo[-1]
        print(f"  進化引擎: +{last.get('total_new',0)} 新規則 | 總計 {last.get('total_rules_after',0)} 條")


def cmd_report():
    """完整日報"""
    report = _load('daily_report.json')
    if not report:
        print("尚無日報。")
        return
    print(report.get('summary', {}).get('zh', '無'))


def cmd_json():
    """全部 JSON 輸出（給程式接）"""
    output = {
        'report': _load('daily_report.json'),
        'signals': _load('ai_signals.json'),
        'models': (_load('opus_briefing.json') or {}).get('model_performance'),
        'arbitrage': _load('prediction_market_scan.json'),
        'opus_analysis': _load('opus_analysis.json'),
        'signal_confidence': _load('signal_confidence.json'),
        'learning': (_load('learning_report.json') or {}).get('adjustments', {}).get('summary'),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# === 入口 ===
COMMANDS = {
    'signals': cmd_signals,
    'models': cmd_models,
    'predict': cmd_predict,
    'arbitrage': cmd_arbitrage,
    'history': cmd_history,
    'health': cmd_health,
    'report': cmd_report,
    'json': cmd_json,
}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help', 'help'):
        print("Trump Code CLI")
        print("=" * 50)
        print()
        print("Usage: python trump_code_cli.py <command>")
        print()
        print("Commands:")
        print("  signals    Today's signals")
        print("  models     Model rankings")
        print("  predict    Prediction direction")
        print("  arbitrage  Arbitrage opportunities")
        print("  history    Historical accuracy")
        print("  health     System health")
        print("  report     Full daily report")
        print("  json       Full JSON output")
        print()
        print("API Usage:")
        print("  python trump_code_cli.py json | jq '.signals'")
        print()
        print("WARNING: This is not investment advice.")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(COMMANDS.keys())}")
        sys.exit(1)
