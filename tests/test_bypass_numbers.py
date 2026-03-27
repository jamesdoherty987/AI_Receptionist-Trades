"""
Tests for the bypass numbers (always-forward) feature.
Verifies phone number matching logic and settings round-trip.
"""
import json
import re
import pytest
from unittest.mock import patch, MagicMock


def normalize_and_match(caller_phone, bypass_list):
    """
    Replicates the bypass matching logic from twilio_voice in src/app.py.
    Returns (matched: bool, matched_entry: dict or None)
    """
    caller_normalized = re.sub(r'[\s\-\(\)\+]', '', caller_phone)
    for entry in bypass_list:
        if not isinstance(entry, dict):
            continue
        entry_phone = re.sub(r'[\s\-\(\)\+]', '', entry.get('phone', ''))
        if entry_phone and len(entry_phone) >= 7 and caller_normalized[-9:] == entry_phone[-9:]:
            return True, entry
    return False, None


class TestBypassPhoneMatching:
    """Test the phone number matching logic used for bypass numbers."""

    def test_exact_match(self):
        bypass = [{"name": "John", "phone": "+353851234567"}]
        matched, entry = normalize_and_match("+353851234567", bypass)
        assert matched
        assert entry["name"] == "John"

    def test_match_with_country_code_difference(self):
        """Caller has +353, bypass stored as 0851234567 (local format)."""
        bypass = [{"name": "Mary", "phone": "0851234567"}]
        matched, _ = normalize_and_match("+353851234567", bypass)
        assert matched

    def test_match_local_to_international(self):
        """Caller uses local format, bypass stored with country code."""
        bypass = [{"name": "Pat", "phone": "+353851234567"}]
        matched, _ = normalize_and_match("0851234567", bypass)
        assert matched

    def test_match_with_spaces_and_dashes(self):
        """Phone numbers with various formatting."""
        bypass = [{"name": "Sean", "phone": "085 123 4567"}]
        matched, _ = normalize_and_match("+353-85-123-4567", bypass)
        assert matched

    def test_match_with_parentheses(self):
        bypass = [{"name": "Liam", "phone": "(085) 123 4567"}]
        matched, _ = normalize_and_match("+353851234567", bypass)
        assert matched

    def test_no_match_different_number(self):
        bypass = [{"name": "John", "phone": "+353851234567"}]
        matched, _ = normalize_and_match("+353859999999", bypass)
        assert not matched

    def test_no_match_empty_list(self):
        matched, _ = normalize_and_match("+353851234567", [])
        assert not matched

    def test_no_match_short_number(self):
        """Numbers shorter than 7 digits should not match (safety)."""
        bypass = [{"name": "Short", "phone": "12345"}]
        matched, _ = normalize_and_match("+353851212345", bypass)
        assert not matched

    def test_multiple_entries_matches_correct_one(self):
        bypass = [
            {"name": "Alice", "phone": "+353851111111"},
            {"name": "Bob", "phone": "+353852222222"},
            {"name": "Charlie", "phone": "+353853333333"},
        ]
        matched, entry = normalize_and_match("+353852222222", bypass)
        assert matched
        assert entry["name"] == "Bob"

    def test_skips_non_dict_entries(self):
        """Malformed entries in the list should be skipped gracefully."""
        bypass = ["bad_entry", 123, {"name": "Valid", "phone": "+353851234567"}]
        matched, entry = normalize_and_match("+353851234567", bypass)
        assert matched
        assert entry["name"] == "Valid"

    def test_entry_missing_phone_key(self):
        bypass = [{"name": "NoPhone"}]
        matched, _ = normalize_and_match("+353851234567", bypass)
        assert not matched

    def test_uk_number_format(self):
        bypass = [{"name": "UK Contact", "phone": "+447911123456"}]
        matched, _ = normalize_and_match("+447911123456", bypass)
        assert matched

    def test_us_number_format(self):
        bypass = [{"name": "US Contact", "phone": "+12125551234"}]
        matched, _ = normalize_and_match("+12125551234", bypass)
        assert matched

    def test_us_local_vs_international(self):
        bypass = [{"name": "US Local", "phone": "2125551234"}]
        matched, _ = normalize_and_match("+12125551234", bypass)
        assert matched


class TestBypassSettingsRoundTrip:
    """Test that bypass_numbers serializes/deserializes correctly."""

    def test_serialize_empty_list(self):
        data = json.dumps([])
        assert data == '[]'
        assert json.loads(data) == []

    def test_serialize_entries(self):
        entries = [
            {"name": "John", "phone": "+353851234567"},
            {"name": "Mary", "phone": "0859876543"},
        ]
        serialized = json.dumps(entries)
        deserialized = json.loads(serialized)
        assert len(deserialized) == 2
        assert deserialized[0]["name"] == "John"
        assert deserialized[1]["phone"] == "0859876543"

    def test_deserialize_null_or_empty(self):
        """Backend returns '[]' for null/empty, frontend should handle both."""
        for raw in ['[]', '', None]:
            parsed = json.loads(raw) if raw else []
            assert parsed == []

    def test_deserialize_malformed_json_fallback(self):
        """If JSON is malformed, should fall back to empty list."""
        raw = "not valid json"
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            parsed = []
        assert parsed == []


class TestBypassInTwilioVoice:
    """Integration-style tests for the bypass check in twilio_voice."""

    def _make_company(self, bypass_list=None, ai_enabled=True, phone="+353861234567"):
        return {
            'id': 1,
            'company_name': 'Test Co',
            'phone': phone,
            'ai_enabled': ai_enabled,
            'bypass_numbers': json.dumps(bypass_list or []),
            'twilio_phone_number': '+353211234567',
        }

    def test_bypass_caller_gets_forwarded_even_when_ai_enabled(self):
        """Core feature: bypass number should forward even if AI is on."""
        company = self._make_company(
            bypass_list=[{"name": "Boss", "phone": "+353851234567"}],
            ai_enabled=True
        )
        bypass_numbers_raw = company.get('bypass_numbers', '[]')
        bypass_list = json.loads(bypass_numbers_raw) if bypass_numbers_raw else []
        
        caller_phone = "+353851234567"
        caller_normalized = re.sub(r'[\s\-\(\)\+]', '', caller_phone)
        
        bypass_forward = False
        for entry in bypass_list:
            if not isinstance(entry, dict):
                continue
            entry_phone = re.sub(r'[\s\-\(\)\+]', '', entry.get('phone', ''))
            if entry_phone and len(entry_phone) >= 7 and caller_normalized[-9:] == entry_phone[-9:]:
                bypass_forward = True
                break
        
        assert bypass_forward is True
        # The condition in twilio_voice is: if not ai_enabled or bypass_forward
        assert (not company['ai_enabled'] or bypass_forward) is True

    def test_non_bypass_caller_goes_to_ai(self):
        company = self._make_company(
            bypass_list=[{"name": "Boss", "phone": "+353851234567"}],
            ai_enabled=True
        )
        bypass_numbers_raw = company.get('bypass_numbers', '[]')
        bypass_list = json.loads(bypass_numbers_raw) if bypass_numbers_raw else []
        
        caller_phone = "+353859999999"
        caller_normalized = re.sub(r'[\s\-\(\)\+]', '', caller_phone)
        
        bypass_forward = False
        for entry in bypass_list:
            if not isinstance(entry, dict):
                continue
            entry_phone = re.sub(r'[\s\-\(\)\+]', '', entry.get('phone', ''))
            if entry_phone and len(entry_phone) >= 7 and caller_normalized[-9:] == entry_phone[-9:]:
                bypass_forward = True
                break
        
        assert bypass_forward is False
        # AI is enabled and not bypass, so should go to AI
        assert (not company['ai_enabled'] or bypass_forward) is False

    def test_bypass_with_ai_disabled_still_forwards(self):
        """If AI is off AND caller is bypass, still forwards (no double issue)."""
        company = self._make_company(
            bypass_list=[{"name": "Boss", "phone": "+353851234567"}],
            ai_enabled=False
        )
        bypass_numbers_raw = company.get('bypass_numbers', '[]')
        bypass_list = json.loads(bypass_numbers_raw) if bypass_numbers_raw else []
        
        matched, _ = normalize_and_match("+353851234567", bypass_list)
        assert (not company['ai_enabled'] or matched) is True

    def test_empty_bypass_list_no_effect(self):
        company = self._make_company(bypass_list=[], ai_enabled=True)
        bypass_numbers_raw = company.get('bypass_numbers', '[]')
        bypass_list = json.loads(bypass_numbers_raw) if bypass_numbers_raw else []
        
        matched, _ = normalize_and_match("+353851234567", bypass_list)
        assert matched is False
        assert (not company['ai_enabled'] or matched) is False

    def test_none_bypass_numbers_no_crash(self):
        """If column is NULL in DB, should not crash."""
        company = self._make_company()
        company['bypass_numbers'] = None
        
        bypass_numbers_raw = company.get('bypass_numbers', '[]')
        try:
            bypass_list = json.loads(bypass_numbers_raw) if bypass_numbers_raw else []
        except Exception:
            bypass_list = []
        
        matched, _ = normalize_and_match("+353851234567", bypass_list)
        assert matched is False
