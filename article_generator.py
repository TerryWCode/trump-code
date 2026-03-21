#!/usr/bin/env python3
"""
川普密碼 — 三語文章生成器
吃當天的推文 + daily_report.json → LLM 產出 zh/en/ja 三篇分析文章

用法：
  python3 article_generator.py                    # 用今天的資料
  python3 article_generator.py --date 2026-03-20  # 指定日期
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"
ARTICLES = BASE / "articles"

# LLM 設定（走 ClawAPI 或直接 Anthropic）
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://clawapi.washinmura.jp/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def call_llm(prompt: str, max_tokens: int = 2000) -> str:
    """呼叫 LLM — 優先用 claude -p（零額外成本），fallback 到 API"""
    import subprocess

    # 方法 1：claude -p（本機 Claude Code，用你現有的 Max 額度）
    try:
        result = subprocess.run(
            ["claude", "-p", "--output-format", "json"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("result", "")
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    # 方法 2：API fallback（需要 key）
    if not LLM_API_KEY:
        raise RuntimeError("claude -p 失敗且無 API key")

    payload = json.dumps({
        "model": LLM_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        f"{LLM_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        },
    )
    resp = urllib.request.urlopen(req, timeout=60)
    result = json.loads(resp.read())
    return result["choices"][0]["message"]["content"]


def load_today_data(target_date: str):
    """載入指定日期的推文和報告"""
    # 從 multi_source_fetcher 抓最新資料
    try:
        from multi_source_fetcher import fetch_all_sources
        all_posts, _ = fetch_all_sources()
    except:
        all_posts = []

    # 過濾當天
    day_posts = [p for p in all_posts if p.get("created_at", "").startswith(target_date)]

    # 讀 daily_report
    report_path = DATA / "daily_report.json"
    report = {}
    if report_path.exists():
        with open(report_path) as f:
            report = json.load(f)

    return day_posts, report


def build_prompt(lang: str, posts: list, report: dict, target_date: str) -> str:
    """建構 LLM prompt"""
    # 整理推文摘要
    posts_text = ""
    for i, p in enumerate(posts[:30], 1):
        time = p.get("created_at", "")[:16]
        content = p.get("content", "")[:200]
        posts_text += f"{i}. [{time}] {content}\n"

    if not posts_text:
        posts_text = "(今天尚無推文)"

    # 信號摘要
    signals = report.get("signals_detected", [])
    consensus = report.get("direction_summary", {}).get("consensus", "N/A")
    hit_rate = report.get("historical_hit_rate", {}).get("rate", "N/A")
    n_posts = report.get("posts_today", len(posts))

    lang_config = {
        "zh": {
            "instruction": "你是「川普密碼」的分析師。用繁體中文寫一篇給台灣投資人看的每日分析。語氣專業但不死板，像一個懂市場的朋友在跟你聊天。",
            "audience": "台灣投資人，關心美股、台股連動、匯率影響",
            "format": "標題用「川普密碼｜日報」開頭",
        },
        "en": {
            "instruction": "You are the 'Trump Code' analyst. Write a daily analysis for Western traders. Professional, data-driven, concise. Reference Polymarket odds when relevant.",
            "audience": "US/EU traders interested in S&P 500, prediction markets, and political signals",
            "format": "Title starts with 'Trump Code | Daily'",
        },
        "ja": {
            "instruction": "あなたは「トランプ・コード」のアナリストです。日本の投資家向けに日次分析を書いてください。丁寧だが簡潔に。日経平均・為替への影響を意識してください。",
            "audience": "日本の個人投資家。日経平均、ドル円、地政学リスクに関心",
            "format": "タイトルは「トランプ・コード｜日報」で始める",
        },
    }

    cfg = lang_config[lang]

    return f"""{cfg['instruction']}

日期：{target_date}
今日推文數：{n_posts}
偵測信號：{', '.join(signals) if signals else 'None'}
模型共識：{consensus}
歷史命中率：{hit_rate}%

今日推文：
{posts_text}

目標讀者：{cfg['audience']}

請產出一篇 300-500 字的分析文章，包含：
1. 今日重點（川普在說什麼、語氣如何）
2. 信號解讀（對市場的潛在影響）
3. 趨勢觀察（跟前幾天比有什麼變化）
4. 一句話結論

格式：{cfg['format']}
用 Markdown 格式輸出。不要加 ```markdown 標記。
"""


def generate_articles(target_date: str = None):
    """生成三語文章"""
    if not target_date:
        target_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    log(f"📝 生成 {target_date} 三語文章")

    posts, report = load_today_data(target_date)
    log(f"   推文：{len(posts)} 篇")

    # 建目錄
    month = target_date[:7]  # 2026-03
    day = target_date[8:]    # 20
    article_dir = ARTICLES / month
    article_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for lang in ["zh", "en", "ja"]:
        log(f"   [{lang}] 呼叫 LLM...")
        try:
            prompt = build_prompt(lang, posts, report, target_date)
            article = call_llm(prompt)

            # 存檔
            out_path = article_dir / f"{day}-{lang}.md"
            out_path.write_text(article, encoding="utf-8")
            results[lang] = {"status": "ok", "path": str(out_path), "length": len(article)}
            log(f"   [{lang}] ✅ {len(article)} 字 → {out_path}")
        except Exception as e:
            results[lang] = {"status": "error", "error": str(e)}
            log(f"   [{lang}] ❌ {e}")

    # 存 metadata
    meta = {
        "date": target_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "posts_count": len(posts),
        "articles": results,
    }
    (article_dir / f"{day}-meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    log(f"✅ 完成：{article_dir}")
    return meta


# __main__ 移到檔案最底部


def update_index():
    """更新文章索引（給主站用）"""
    dates = set()
    for month_dir in ARTICLES.iterdir():
        if month_dir.is_dir() and month_dir.name[:4].isdigit():
            for f in month_dir.iterdir():
                if f.name.endswith("-zh.md"):
                    day = f.name.split("-")[0]
                    dates.add(f"{month_dir.name}-{day}")
    dates = sorted(dates, reverse=True)
    index_path = ARTICLES / "index.json"
    index_path.write_text(json.dumps(dates, ensure_ascii=False, indent=2))
    log(f"📋 索引更新：{len(dates)} 篇")
    return dates


def publish_to_devto(date: str, lang: str = "zh"):
    """發布到 Dev.to（單篇）"""
    month = date[:7]
    day = date[8:]
    article_path = ARTICLES / month / f"{day}-{lang}.md"
    if not article_path.exists():
        log(f"Dev.to: {article_path} 不存在")
        return

    content = article_path.read_text(encoding="utf-8")

    # Dev.to API key
    devto_key = os.environ.get("DEVTO_API_KEY", "")
    if not devto_key:
        env_path = Path.home() / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("DEVTO_API_KEY="):
                    devto_key = line.split("=", 1)[1].strip().strip('"')
                    break
    if not devto_key:
        log("Dev.to: 無 API key，跳過")
        return

    # 標題和 tags 依語言
    lang_config = {
        "zh": {"title_prefix": "川普密碼｜", "tags": ["trump", "investing", "ai", "chinese"]},
        "en": {"title_prefix": "Trump Code | ", "tags": ["trump", "investing", "ai", "stockmarket"]},
        "ja": {"title_prefix": "トランプ・コード｜", "tags": ["trump", "investing", "ai", "japanese"]},
    }
    cfg = lang_config.get(lang, lang_config["en"])

    title = f"{cfg['title_prefix']}Daily Analysis {date}"
    body = content + f"\n\n---\n\n🔗 [Full dashboard](https://trumpcode.washinmura.jp/) | [All articles](https://trumpcode.washinmura.jp/daily.html)"

    payload = json.dumps({
        "article": {
            "title": title,
            "body_markdown": body,
            "published": True,
            "tags": cfg["tags"],
            "series": cfg["title_prefix"].strip("｜| "),
        }
    }).encode()

    req = urllib.request.Request(
        "https://dev.to/api/articles",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "api-key": devto_key,
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        log(f"Dev.to [{lang}]: ✅ 發布成功 → {result.get('url', '?')}")
    except Exception as e:
        log(f"Dev.to [{lang}]: ❌ {e}")


def full_pipeline(target_date: str = None):
    """完整管線：生成文章 + 更新索引 + 發布 Dev.to"""
    meta = generate_articles(target_date)
    update_index()

    # Dev.to 三語都發
    actual_date = target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for lang in ["zh", "en", "ja"]:
        if meta.get("articles", {}).get(lang, {}).get("status") == "ok":
            publish_to_devto(actual_date, lang)

    return meta


if __name__ == "__main__":
    date = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--date" and i + 1 < len(sys.argv) - 1:
            date = sys.argv[i + 2]
    full_pipeline(date)
