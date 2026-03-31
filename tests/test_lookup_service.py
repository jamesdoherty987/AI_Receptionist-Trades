"""Tests for lookup_service_by_name — the name-based service resolver used by tool handlers."""
import pytest
from unittest.mock import patch, MagicMock

# Sample services mimicking a real plumbing company
SERVICES = [
    {'id': 'svc_general', 'name': 'General Callout', 'category': 'General', 'description': 'Default callout', 'duration_minutes': 240, 'price': 80, 'package_only': False},
    {'id': 'svc_leak', 'name': 'Leak fix', 'category': 'Plumbing', 'description': 'Fix a leak', 'duration_minutes': 120, 'price': 100, 'package_only': True},
    {'id': 'svc_inspect', 'name': 'Inspection', 'category': 'Plumbing', 'description': 'Inspect plumbing', 'duration_minutes': 60, 'price': 50, 'package_only': True},
    {'id': 'svc_boiler', 'name': 'Boiler Repair', 'category': 'Heating', 'description': 'Repair boiler', 'duration_minutes': 180, 'price': 150, 'package_only': False},
    {'id': 'svc_drain', 'name': 'Drain Unblocking', 'category': 'Plumbing', 'description': 'Unblock drains', 'duration_minutes': 90, 'price': 120, 'package_only': False},
]

PACKAGES = [
    {
        'id': 'pkg_leak_inv', 'name': 'Leak Fix and Investigation',
        'description': 'Investigate and fix a leak', 'use_when_uncertain': True,
        'total_duration_minutes': 360, 'total_price': 200,
        'duration_override': None, 'price_override': None,
        'services': [
            {'name': 'Inspection', 'duration_minutes': 60, 'price': 50},
            {'name': 'Leak fix', 'duration_minutes': 120, 'price': 100},
        ]
    }
]


def _mock_settings():
    mgr = MagicMock()
    mgr.get_services.return_value = SERVICES
    mgr.get_packages.return_value = PACKAGES
    mgr.get_default_duration_minutes.return_value = 1440
    return mgr


PATCH_TARGET = 'src.services.settings_manager.get_settings_manager'


class TestLookupServiceByName:

    def _lookup(self, name):
        from src.services.calendar_tools import lookup_service_by_name
        with patch(PATCH_TARGET, return_value=_mock_settings()):
            return lookup_service_by_name(name, company_id=1)

    def test_exact_match_standalone_service(self):
        result = self._lookup('Boiler Repair')
        assert result['matched_name'] == 'Boiler Repair'
        assert result['score'] >= 99

    def test_exact_match_case_insensitive(self):
        result = self._lookup('boiler repair')
        assert result['matched_name'] == 'Boiler Repair'
        assert result['score'] >= 99

    def test_exact_match_package_only_service(self):
        """package_only services should still be found by exact name."""
        result = self._lookup('Leak fix')
        assert result['matched_name'] == 'Leak fix'
        assert result['service']['duration_minutes'] == 120
        assert result['score'] >= 99

    def test_leak_fix_prefers_service_over_package(self):
        """'Leak fix' should match the standalone service, NOT the package."""
        result = self._lookup('Leak fix')
        assert result['matched_name'] == 'Leak fix'
        assert not result.get('is_package', False)

    def test_package_exact_match(self):
        result = self._lookup('Leak Fix and Investigation')
        assert result['matched_name'] == 'Leak Fix and Investigation'
        assert result.get('is_package', False) is True

    def test_general_callout_matched(self):
        """'general callout' should find the General Callout service."""
        result = self._lookup('general callout')
        assert 'general' in result['matched_name'].lower()
        assert result['is_general'] is True

    def test_general_service_matched(self):
        """'general service' should still resolve to General Callout."""
        result = self._lookup('general service')
        assert result['is_general'] is True

    def test_slight_variation(self):
        result = self._lookup('drain unblocking')
        assert result['matched_name'] == 'Drain Unblocking'

    def test_empty_string_falls_back(self):
        from src.services.calendar_tools import lookup_service_by_name
        with patch(PATCH_TARGET, return_value=_mock_settings()), \
             patch('src.services.calendar_tools.match_service') as mock_ms:
            mock_ms.return_value = {'service': {}, 'score': 0, 'matched_name': 'fallback', 'is_general': True}
            lookup_service_by_name('', company_id=1)
            mock_ms.assert_called_once()

    def test_nonsense_falls_back(self):
        from src.services.calendar_tools import lookup_service_by_name
        with patch(PATCH_TARGET, return_value=_mock_settings()), \
             patch('src.services.calendar_tools.match_service') as mock_ms:
            mock_ms.return_value = {'service': {}, 'score': 0, 'matched_name': 'fallback', 'is_general': True}
            lookup_service_by_name('xyzzy foobar baz', company_id=1)
            mock_ms.assert_called_once()

    def test_inspection_matches_standalone(self):
        """'Inspection' should match the standalone service, not the package."""
        result = self._lookup('Inspection')
        assert result['matched_name'] == 'Inspection'
        assert result['service']['duration_minutes'] == 60
        assert not result.get('is_package', False)
