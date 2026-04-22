#!/usr/bin/env python3
"""
Trump Code - Shared Utility Module
Unified timezone conversion, keyword matching, sentiment scoring, and other core functions
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

# Eastern Time Zone (automatically handles EST/EDT daylight saving)
ET = ZoneInfo("America/New_York")


# ============================================================
# Timezone Conversion (DST bug fixed)
# ============================================================

def to_eastern(utc_str: str) -> datetime:
    """Convert UTC string to Eastern Time (auto-handles EST/EDT)"""
    dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
    return dt.astimezone(ET)


def est_hour(utc_str: str) -> tuple:
    """Return Eastern (hour, minute), auto-handles daylight saving"""
    et = to_eastern(utc_str)
    return et.hour, et.minute


def market_session(utc_str: str) -> str:
    """Determine US stock trading session"""
    h, m = est_hour(utc_str)
    if h < 4:
        return 'OVERNIGHT'
    elif h < 9 or (h == 9 and m < 30):
        return 'PRE_MARKET'
    elif h < 16:
        return 'MARKET_OPEN'
    elif h < 20:
        return 'AFTER_HOURS'
    else:
        return 'OVERNIGHT'


# ============================================================
# Keyword Matching (word boundaries to avoid substring false positives)
# ============================================================

@lru_cache(maxsize=256)
def _make_pattern(words: tuple) -> re.Pattern:
    """Compile word boundary regex pattern (cached)"""
    escaped = [re.escape(w) for w in words]
    return re.compile(r'\b(?:' + '|'.join(escaped) + r')\b', re.IGNORECASE)


def count_keywords(text: str, keywords: list) -> int:
    """Count keyword occurrences using word boundary matching"""
    pattern = _make_pattern(tuple(keywords))
    return len(pattern.findall(text))


def has_keywords(text: str, keywords: list) -> bool:
    """Check if text contains any keyword (word boundary matching)"""
    pattern = _make_pattern(tuple(keywords))
    return bool(pattern.search(text))


# ============================================================
# Sentiment Score (unified version)
# ============================================================

STRONG_WORDS = frozenset([
    'never', 'always', 'worst', 'best', 'greatest', 'terrible',
    'incredible', 'tremendous', 'massive', 'total', 'complete',
    'absolute', 'disaster', 'perfect', 'beautiful', 'horrible',
    'amazing', 'fantastic', 'disgrace', 'pathetic', 'historic',
    'unprecedented', 'radical', 'corrupt', 'crooked', 'fake'
])


def emotion_score(content: str) -> float:
    """Calculate sentiment intensity of a single post (0-100)"""
    score = 0.0
    text = content

    # Uppercase letter ratio (max 30 points)
    upper = sum(1 for c in text if c.isupper())
    alpha = sum(1 for c in text if c.isalpha())
    caps_ratio = upper / max(alpha, 1)
    score += caps_ratio * 30

    # Exclamation mark density (max 25 points)
    excl = text.count('!')
    excl_density = excl / max(len(text), 1) * 100
    score += min(excl_density * 10, 25)

    # Strong words - using word boundary matching (max 25 points)
    word_count = len(re.findall(r'\b\w+\b', text.lower()))
    strong_count = count_keywords(text, list(STRONG_WORDS))
    score += min(strong_count / max(word_count, 1) * 500, 25)

    # All-caps consecutive words (max 20 points)
    caps_words = len(re.findall(r'\b[A-Z]{3,}\b', text))
    score += min(caps_words * 2, 20)

    return min(round(score, 1), 100)


# ============================================================
# Next Trading Day
# ============================================================

def safe_json_write(path, data) -> None:
    """Atomic JSON write - write to temp file first then os.replace, prevents corruption on interrupt"""
    path = Path(path)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def next_trading_day(date_str: str, market_data: dict, max_days: int = 10) -> str:
    """Find next trading day after date_str, search up to max_days forward"""
    d = datetime.strptime(date_str, '%Y-%m-%d')
    for i in range(1, max_days + 1):
        candidate = (d + timedelta(days=i)).strftime('%Y-%m-%d')
        if candidate in market_data:
            return candidate
    return None

