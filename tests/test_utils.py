"""
tests/test_utils.py
Test core functions in utils.py: est_hour, has_keywords, market_session
"""
import sys
import os

# Ensure utils from root directory can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from utils import est_hour, has_keywords, market_session


class TestEstHour:
    def test_est_winter(self):
        """Winter time (EST = UTC-5): UTC 14:30 → EST 9:30"""
        h, m = est_hour("2025-01-15T14:30:00Z")
        assert h == 9 and m == 30  # 9:30 AM EST

    def test_edt_summer(self):
        """Daylight saving time (EDT = UTC-4): UTC 14:30 → EDT 10:30"""
        h, m = est_hour("2025-07-15T14:30:00Z")
        assert h == 10 and m == 30  # 10:30 AM EDT

    def test_dst_transition_before(self):
        """2025-03-09 before DST switch: UTC 06:00 = EST 01:00 (UTC-5 not switched yet)"""
        h, _ = est_hour("2025-03-09T06:00:00Z")
        assert h == 1  # 1 AM EST

    def test_dst_transition_after(self):
        """2025-03-09 after DST switch: UTC 08:00 = EDT 04:00 (UTC-4 switched)"""
        h, _ = est_hour("2025-03-09T08:00:00Z")
        assert h == 4  # 4 AM EDT (not 3 AM)

    def test_midnight_utc(self):
        """UTC 00:00 winter = EST 19:00 previous day"""
        h, m = est_hour("2025-01-15T00:00:00Z")
        assert h == 19 and m == 0  # 7 PM EST (previous day)

    def test_minute_preserved(self):
        """Minutes should be preserved correctly"""
        h, m = est_hour("2025-01-15T15:45:00Z")
        assert m == 45


class TestHasKeywords:
    def test_exact_word_match(self):
        """Exact word match should return True"""
        assert has_keywords("tariff policy", ['tariff']) is True

    def test_plural_not_matched_by_singular(self):
        """Plural form should not be matched by singular keyword (word boundary)"""
        assert has_keywords("tariffs policy", ['tariff']) is False

    def test_plural_matched_by_plural_keyword(self):
        """Plural keyword can match plural form"""
        assert has_keywords("tariffs policy", ['tariffs']) is True

    def test_case_insensitive(self):
        """Keyword matching should be case-insensitive"""
        assert has_keywords("TARIFF POLICY", ['tariff']) is True

    def test_no_substring_match_totally(self):
        """'total' should not match 'totally'"""
        assert has_keywords("totally fine", ['total']) is False

    def test_no_substring_match_kitchen(self):
        """'Mitch' should not match 'kitchen'"""
        assert has_keywords("kitchen sink", ['Mitch']) is False

    def test_multiple_keywords_any_match(self):
        """Return True if any keyword matches"""
        assert has_keywords("big deal signed today", ['tariff', 'deal']) is True

    def test_multiple_keywords_none_match(self):
        """Return False if no keywords are in text"""
        assert has_keywords("good morning everyone", ['tariff', 'deal']) is False

    def test_empty_text(self):
        """Empty string should return False"""
        assert has_keywords("", ['tariff']) is False

    def test_word_at_sentence_end(self):
        """Keyword at sentence end should match"""
        assert has_keywords("This is about tariff", ['tariff']) is True


class TestMarketSession:
    def test_pre_market(self):
        """UTC 13:00 = EST 8:00 AM → PRE_MARKET"""
        assert market_session("2025-01-15T13:00:00Z") == 'PRE_MARKET'

    def test_market_open(self):
        """UTC 15:00 = EST 10:00 AM → MARKET_OPEN"""
        assert market_session("2025-01-15T15:00:00Z") == 'MARKET_OPEN'

    def test_after_hours(self):
        """UTC 22:00 = EST 17:00 (5 PM) → AFTER_HOURS"""
        assert market_session("2025-01-15T22:00:00Z") == 'AFTER_HOURS'

    def test_overnight_early_morning(self):
        """UTC 04:00 = EST 23:00 previous day → OVERNIGHT"""
        assert market_session("2025-01-15T04:00:00Z") == 'OVERNIGHT'

    def test_market_open_start_930(self):
        """UTC 14:30 = EST 9:30 AM → MARKET_OPEN (market opening time)"""
        assert market_session("2025-01-15T14:30:00Z") == 'MARKET_OPEN'

    def test_pre_market_before_930(self):
        """UTC 14:29 = EST 9:29 AM → PRE_MARKET (one minute before opening)"""
        assert market_session("2025-01-15T14:29:00Z") == 'PRE_MARKET'

    def test_after_hours_start_1600(self):
        """UTC 21:00 = EST 16:00 (4 PM) → AFTER_HOURS (first minute after close)"""
        assert market_session("2025-01-15T21:00:00Z") == 'AFTER_HOURS'

    def test_overnight_late_night(self):
        """UTC 01:00 = EST 20:00 previous day (8 PM) → OVERNIGHT"""
        assert market_session("2025-01-15T01:00:00Z") == 'OVERNIGHT'

    def test_very_early_morning_overnight(self):
        """UTC 06:00 = EST 01:00 → OVERNIGHT (h < 4)"""
        assert market_session("2025-01-15T06:00:00Z") == 'OVERNIGHT'

    def test_pre_market_early(self):
        """UTC 09:00 = EST 04:00 → PRE_MARKET (h >= 4, h < 9)"""
        assert market_session("2025-01-15T09:00:00Z") == 'PRE_MARKET'

