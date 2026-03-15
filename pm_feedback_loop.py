#!/usr/bin/env python3
"""
川普密碼 — 預測市場回饋迴路（Prediction Market Feedback Loop）

問題：我們掃到套利機會後，有沒有追蹤結果？結果有沒有拉回來學習？
答案：這個模組就是做這件事。

流程：
  1. 每天掃到的套利機會 → 記錄當時的價格和信號
  2. 隔天（或結算後）→ 回去查 Polymarket 的新價格
  3. 計算：我們的信號方向對不對？價格有沒有往我們預測的方向動？
  4. 把結果拉回學習引擎 → 調整信號→市場映射的信心度

這樣閉環才完整：
  信號 → 預測 → 掃市場 → 記錄 → 追蹤結果 → 學習 → 調整 → 下一輪
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).parent
DATA = BASE / "data"

PM_HISTORY_FILE = DATA / "pm_prediction_history.json"    # 預測市場的預測紀錄
PM_FEEDBACK_FILE = DATA / "pm_feedback_results.json"     # 驗證後的結果
PM_SCAN_FILE = DATA / "prediction_market_scan.json"      # 每日掃描結果

TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def log(msg: str) -> None:
    print(f"[PM回饋] {msg}", flush=True)


# =====================================================================
# ① 記錄：把今天的套利機會存起來追蹤
# =====================================================================

def record_opportunities() -> int:
    """
    從今天的掃描結果中，把有價值的機會存到追蹤清單。
    回傳新增幾筆。
    """
    if not PM_SCAN_FILE.exists():
        return 0

    with open(PM_SCAN_FILE, encoding='utf-8') as f:
        scan = json.load(f)

    opportunities = scan.get('opportunities', [])
    if not opportunities:
        return 0

    # 載入歷史
    history: list[dict] = []
    if PM_HISTORY_FILE.exists():
        with open(PM_HISTORY_FILE, encoding='utf-8') as f:
            history = json.load(f)

    # 記錄新的機會
    new_count = 0
    for opp in opportunities:
        record = {
            'recorded_date': TODAY,
            'recorded_at': NOW,
            'market_name': opp.get('market_name', '?'),
            'token_id': opp.get('token_id', '?'),
            'signal_direction': opp.get('expected_direction', '?'),
            'signal_strength': opp.get('signal_strength', 0),
            'opportunity_score': opp.get('opportunity_score', 0),
            'price_at_signal': opp.get('current_price', 0),
            'matched_signals': opp.get('matched_signals', []),

            # 追蹤欄位（後續回來填）
            'price_after_1d': None,
            'price_after_3d': None,
            'price_after_7d': None,
            'price_change_1d': None,
            'price_change_3d': None,
            'direction_correct': None,  # 價格有沒有往我們預測的方向動
            'profit_if_traded': None,   # 如果真的下單的獲利（美分）
            'status': 'TRACKING',       # TRACKING → VERIFIED → EXPIRED
            'verified_at': None,
        }
        history.append(record)
        new_count += 1

    with open(PM_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    if new_count:
        log(f"✅ 記錄了 {new_count} 個套利機會，開始追蹤")

    return new_count


# =====================================================================
# ② 追蹤：回去查價格變化
# =====================================================================

def check_tracked_predictions() -> dict[str, Any]:
    """
    對所有 TRACKING 狀態的預測，回去查最新價格。
    計算價格變化，判斷方向是否正確。

    回傳統計摘要。
    """
    if not PM_HISTORY_FILE.exists():
        return {'checked': 0}

    with open(PM_HISTORY_FILE, encoding='utf-8') as f:
        history = json.load(f)

    tracking = [h for h in history if h.get('status') == 'TRACKING']
    if not tracking:
        return {'checked': 0, 'tracking': 0}

    log(f"檢查 {len(tracking)} 個追蹤中的預測市場機會...")

    # 嘗試用 Polymarket API 查最新價格
    try:
        from polymarket_client import get_market_price, PolymarketAPIError
        api_available = True
    except ImportError:
        api_available = False

    verified_count = 0
    correct_count = 0

    for record in tracking:
        token_id = record.get('token_id', '')
        recorded_date = record.get('recorded_date', '')
        price_at_signal = record.get('price_at_signal', 0)

        if not token_id or not recorded_date:
            continue

        # 計算經過幾天
        try:
            rec_dt = datetime.strptime(recorded_date, '%Y-%m-%d')
            today_dt = datetime.strptime(TODAY, '%Y-%m-%d')
            days_elapsed = (today_dt - rec_dt).days
        except ValueError:
            continue

        if days_elapsed < 1:
            continue  # 還沒過一天，不查

        # 查最新價格
        current_price = None
        if api_available and token_id != '?' and not token_id.startswith('token_'):
            try:
                price_data = get_market_price(token_id)
                current_price = float(price_data.get('price', 0))
            except (PolymarketAPIError, ValueError, TypeError):
                pass

        if current_price is None:
            # 如果 API 查不到，超過 7 天就標 EXPIRED
            if days_elapsed > 7:
                record['status'] = 'EXPIRED'
                record['verified_at'] = NOW
            continue

        # 填入價格變化
        price_change = current_price - price_at_signal
        direction = record.get('signal_direction', 'LONG')

        if days_elapsed >= 1 and record.get('price_after_1d') is None:
            record['price_after_1d'] = round(current_price, 4)
            record['price_change_1d'] = round(price_change, 4)

        if days_elapsed >= 3 and record.get('price_after_3d') is None:
            record['price_after_3d'] = round(current_price, 4)
            record['price_change_3d'] = round(price_change, 4)

        if days_elapsed >= 7:
            record['price_after_7d'] = round(current_price, 4)

        # 判斷方向是否正確
        if direction == 'LONG':
            record['direction_correct'] = price_change > 0
        elif direction == 'SHORT':
            record['direction_correct'] = price_change < 0
        else:
            record['direction_correct'] = None

        # 計算獲利（美分，1 share = $1）
        if direction == 'LONG':
            record['profit_if_traded'] = round(price_change * 100, 1)  # 美分
        elif direction == 'SHORT':
            record['profit_if_traded'] = round(-price_change * 100, 1)

        # 3 天後標為 VERIFIED
        if days_elapsed >= 3:
            record['status'] = 'VERIFIED'
            record['verified_at'] = NOW
            verified_count += 1
            if record.get('direction_correct'):
                correct_count += 1

    # 存檔
    with open(PM_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    # 統計
    all_verified = [h for h in history if h.get('status') == 'VERIFIED']
    all_correct = [h for h in all_verified if h.get('direction_correct')]

    result = {
        'checked': len(tracking),
        'newly_verified': verified_count,
        'newly_correct': correct_count,
        'total_verified': len(all_verified),
        'total_correct': len(all_correct),
        'hit_rate': round(len(all_correct) / len(all_verified) * 100, 1) if all_verified else 0,
        'avg_profit': round(
            sum(h.get('profit_if_traded', 0) for h in all_verified) / len(all_verified), 1
        ) if all_verified else 0,
    }

    if verified_count:
        log(f"✅ 新驗證 {verified_count} 筆 | 正確 {correct_count} 筆")
    log(f"   累計: {result['total_verified']} 筆驗證 | "
        f"命中率 {result['hit_rate']:.1f}% | "
        f"平均獲利 {result['avg_profit']:+.1f}¢/share")

    return result


# =====================================================================
# ③ 回饋：把結果餵回學習引擎
# =====================================================================

def generate_feedback() -> dict[str, Any]:
    """
    從已驗證的預測市場結果，產出回饋報告。
    學習引擎和 Opus 讀這個來調整信號→市場映射。
    """
    if not PM_HISTORY_FILE.exists():
        return {'error': 'no history'}

    with open(PM_HISTORY_FILE, encoding='utf-8') as f:
        history = json.load(f)

    verified = [h for h in history if h.get('status') == 'VERIFIED']
    if not verified:
        return {'error': 'no verified predictions'}

    # 按信號類型分組統計
    from collections import defaultdict
    by_signal: dict[str, dict] = defaultdict(lambda: {
        'correct': 0, 'wrong': 0, 'total': 0, 'profits': [],
    })

    for h in verified:
        for sig in h.get('matched_signals', ['UNKNOWN']):
            by_signal[sig]['total'] += 1
            by_signal[sig]['profits'].append(h.get('profit_if_traded', 0))
            if h.get('direction_correct'):
                by_signal[sig]['correct'] += 1
            else:
                by_signal[sig]['wrong'] += 1

    # 產出回饋
    feedback = {
        'date': TODAY,
        'generated_at': NOW,
        'total_verified': len(verified),
        'overall_hit_rate': round(
            sum(1 for h in verified if h.get('direction_correct')) / len(verified) * 100, 1
        ),
        'signal_effectiveness': {
            sig: {
                'hit_rate': round(s['correct'] / s['total'] * 100, 1) if s['total'] > 0 else 0,
                'avg_profit': round(sum(s['profits']) / len(s['profits']), 1) if s['profits'] else 0,
                'total_trades': s['total'],
                'recommendation': (
                    'BOOST' if s['correct'] / max(s['total'], 1) > 0.6
                    else ('REDUCE' if s['correct'] / max(s['total'], 1) < 0.4
                          else 'HOLD')
                ),
            }
            for sig, s in sorted(by_signal.items())
        },
        'best_signal': max(
            by_signal.items(),
            key=lambda x: x[1]['correct'] / max(x[1]['total'], 1),
            default=('NONE', {'correct': 0, 'total': 0}),
        )[0],
        'worst_signal': min(
            by_signal.items(),
            key=lambda x: x[1]['correct'] / max(x[1]['total'], 1),
            default=('NONE', {'correct': 0, 'total': 0}),
        )[0],
    }

    with open(PM_FEEDBACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(feedback, f, ensure_ascii=False, indent=2)

    log(f"📊 回饋報告已產出:")
    log(f"   整體命中率: {feedback['overall_hit_rate']:.1f}%")
    log(f"   最強信號: {feedback['best_signal']}")
    log(f"   最弱信號: {feedback['worst_signal']}")

    return feedback


# =====================================================================
# ④ 主流程（被 daily_pipeline 呼叫）
# =====================================================================

def run_pm_feedback() -> dict[str, Any]:
    """
    完整的預測市場回饋循環：
      1. 記錄今天的新機會
      2. 追蹤過去機會的價格變化
      3. 產出回饋報告
    """
    log("=" * 50)
    log(f"預測市場回饋迴路 — {TODAY}")
    log("=" * 50)

    # 1. 記錄新機會
    new = record_opportunities()

    # 2. 追蹤過去的
    tracking_result = check_tracked_predictions()

    # 3. 產出回饋
    feedback = {}
    if tracking_result.get('total_verified', 0) > 0:
        feedback = generate_feedback()

    # 4. 自動調整信號信心度（根據 PM 驗證結果）
    if feedback and feedback.get('signal_effectiveness'):
        auto_adjust_confidence(feedback)

    log("=" * 50)
    log("✅ 回饋迴路完成")
    log("=" * 50)

    return {
        'new_recorded': new,
        'tracking': tracking_result,
        'feedback': feedback,
    }


def auto_adjust_confidence(feedback: dict[str, Any]) -> None:
    """
    根據預測市場的驗證結果，自動微調信號信心度。

    規則：
      - PM 命中率 > 60% 的信號 → 信心度 +0.03（小步上調）
      - PM 命中率 < 40% 的信號 → 信心度 -0.03
      - 中間的不動
      - 至少 3 筆驗證才調（避免噪音）
      - 調幅小（每天最多 ±0.03），保守避免過度反應
    """
    sc_file = DATA / "signal_confidence.json"
    if not sc_file.exists():
        return

    with open(sc_file, encoding='utf-8') as f:
        conf = json.load(f)

    effectiveness = feedback.get('signal_effectiveness', {})
    adjusted = False

    for sig, stats in effectiveness.items():
        if sig not in conf:
            continue
        if stats.get('total_trades', 0) < 3:
            continue  # 樣本太少

        hit_rate = stats.get('hit_rate', 50)
        old_val = conf[sig]

        if hit_rate > 60:
            new_val = min(0.95, old_val + 0.03)
        elif hit_rate < 40:
            new_val = max(0.20, old_val - 0.03)
        else:
            continue

        if abs(new_val - old_val) > 0.001:
            conf[sig] = round(new_val, 3)
            arrow = "⬆️" if new_val > old_val else "⬇️"
            log(f"   {arrow} [PM回饋] {sig}: {old_val:.2f} → {new_val:.2f} "
                f"（PM命中率 {hit_rate:.0f}%）")
            adjusted = True

    if adjusted:
        with open(sc_file, 'w', encoding='utf-8') as f:
            json.dump(conf, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    result = run_pm_feedback()
    print(json.dumps(result, ensure_ascii=False, indent=2))
