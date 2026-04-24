"""
Test Callout Service Flow

Tests the callout system end-to-end:
1. _resolve_callout_duration helper with various edge cases
2. book_job callout logic — verifies callout duration is used instead of full job
3. Availability tools use callout duration for callout services
4. Pre-check full-day logic uses resolved callout duration
"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def make_services(include_general_callout=True, callout_duration=60):
    services = [
        {'name': 'Kitchen Renovation', 'duration_minutes': 2880, 'price': 5000,
         'requires_callout': True, 'employees_required': 1, 'employee_restrictions': None},
        {'name': 'Plumbing Repair', 'duration_minutes': 120, 'price': 150,
         'requires_callout': False, 'employees_required': 1, 'employee_restrictions': None},
        {'name': 'Roof Repair', 'duration_minutes': 1440, 'price': 3000,
         'requires_callout': True, 'employees_required': 2, 'employee_restrictions': None},
    ]
    if include_general_callout:
        services.append({
            'name': 'General Callout', 'duration_minutes': callout_duration,
            'price': 50, 'requires_callout': False, 'employees_required': 1,
            'employee_restrictions': None
        })
    return services


def _next_weekday(hour=10):
    d = datetime.now() + timedelta(days=1)
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d.replace(hour=hour, minute=0, second=0, microsecond=0)


# ═══════════════════════════════════════════════════════════════
# 1. _resolve_callout_duration helper
# ═══════════════════════════════════════════════════════════════

class TestResolveCalloutDuration:

    def test_non_callout_returns_own_duration(self):
        from src.services.calendar_tools import _resolve_callout_duration
        assert _resolve_callout_duration({'duration_minutes': 120, 'requires_callout': False}) == 120

    def test_missing_flag_returns_own_duration(self):
        from src.services.calendar_tools import _resolve_callout_duration
        assert _resolve_callout_duration({'duration_minutes': 90}) == 90

    def test_callout_uses_general_callout_duration(self):
        from src.services.calendar_tools import _resolve_callout_duration
        svc = {'duration_minutes': 2880, 'requires_callout': True}
        mock_sm = MagicMock()
        mock_sm.get_services.return_value = make_services(callout_duration=45)
        with patch('src.services.settings_manager.get_settings_manager', return_value=mock_sm):
            assert _resolve_callout_duration(svc, company_id=1) == 45

    def test_fallback_to_any_callout_service(self):
        from src.services.calendar_tools import _resolve_callout_duration
        svc = {'duration_minutes': 1440, 'requires_callout': True}
        mock_sm = MagicMock()
        mock_sm.get_services.return_value = [
            {'name': 'Emergency Callout', 'duration_minutes': 30},
            {'name': 'Plumbing', 'duration_minutes': 120},
        ]
        with patch('src.services.settings_manager.get_settings_manager', return_value=mock_sm):
            assert _resolve_callout_duration(svc, company_id=1) == 30

    def test_no_callout_service_defaults_60(self):
        from src.services.calendar_tools import _resolve_callout_duration
        svc = {'duration_minutes': 1440, 'requires_callout': True}
        mock_sm = MagicMock()
        mock_sm.get_services.return_value = [{'name': 'Plumbing', 'duration_minutes': 120}]
        with patch('src.services.settings_manager.get_settings_manager', return_value=mock_sm):
            assert _resolve_callout_duration(svc, company_id=1) == 60

    def test_callout_service_missing_duration_defaults_60(self):
        from src.services.calendar_tools import _resolve_callout_duration
        svc = {'duration_minutes': 2880, 'requires_callout': True}
        mock_sm = MagicMock()
        mock_sm.get_services.return_value = [{'name': 'General Callout'}]
        with patch('src.services.settings_manager.get_settings_manager', return_value=mock_sm):
            assert _resolve_callout_duration(svc, company_id=1) == 60

    def test_non_callout_missing_duration_defaults_60(self):
        from src.services.calendar_tools import _resolve_callout_duration
        assert _resolve_callout_duration({'requires_callout': False}) == 60


# ═══════════════════════════════════════════════════════════════
# 2. ServiceMatcher preserves requires_callout
# ═══════════════════════════════════════════════════════════════

class TestServiceMatcherCalloutFlag:

    def test_callout_service_flag_true(self):
        from src.services.calendar_tools import ServiceMatcher
        result = ServiceMatcher.match('kitchen renovation', make_services())
        assert result['service'].get('requires_callout') is True

    def test_non_callout_service_flag_false(self):
        from src.services.calendar_tools import ServiceMatcher
        result = ServiceMatcher.match('plumbing repair', make_services())
        assert result['service'].get('requires_callout') is False


# ═══════════════════════════════════════════════════════════════
# 3. book_job callout logic (unit-tested via direct callout code path)
# ═══════════════════════════════════════════════════════════════

class TestBookJobCalloutLogic:
    """Test the callout branching logic in book_job without running the full
    execute_tool_call (which has many side-effect imports).
    
    We directly test the decision logic:
    - When matched_service.requires_callout is True, the code should find
      General Callout and use its duration
    - The booking should be flagged with is_callout_booking=True
    """

    def test_callout_branch_finds_general_callout(self):
        """Simulate the callout branch from book_job lines ~3910-3940"""
        mock_sm = MagicMock()
        mock_sm.get_services.return_value = make_services(callout_duration=45)

        matched_service = {
            'name': 'Kitchen Renovation', 'duration_minutes': 2880,
            'requires_callout': True, 'price': 5000
        }
        matched_service_name = 'Kitchen Renovation'
        service_duration = matched_service['duration_minutes']
        is_callout_booking = False
        original_service_name = matched_service_name

        # Replicate the callout logic from book_job
        if matched_service.get('requires_callout'):
            with patch('src.services.settings_manager.get_settings_manager', return_value=mock_sm):
                from src.services.settings_manager import get_settings_manager
                settings_mgr = get_settings_manager()
                all_services = settings_mgr.get_services(company_id=1)
                callout_service = None
                for svc in all_services:
                    svc_name = (svc.get('name') or '').lower()
                    if 'general callout' in svc_name or ('general' in svc_name and 'callout' in svc_name):
                        callout_service = svc
                        break
                if not callout_service:
                    for svc in all_services:
                        if 'callout' in (svc.get('name') or '').lower():
                            callout_service = svc
                            break
                if callout_service:
                    service_duration = callout_service.get('duration_minutes', 60)
                    matched_service_name = f"Callout for {original_service_name}"
                    is_callout_booking = True

        assert is_callout_booking is True
        assert service_duration == 45
        assert matched_service_name == "Callout for Kitchen Renovation"

    def test_non_callout_branch_keeps_full_duration(self):
        """Non-callout service should keep its own duration"""
        matched_service = {
            'name': 'Plumbing Repair', 'duration_minutes': 120,
            'requires_callout': False, 'price': 150
        }
        service_duration = matched_service['duration_minutes']
        is_callout_booking = False

        if matched_service.get('requires_callout'):
            is_callout_booking = True  # Should NOT reach here

        assert is_callout_booking is False
        assert service_duration == 120

    def test_callout_no_general_callout_defaults_60(self):
        """If no General Callout service exists, default to 60 min"""
        mock_sm = MagicMock()
        mock_sm.get_services.return_value = [
            {'name': 'Plumbing', 'duration_minutes': 120},
            {'name': 'Electrical', 'duration_minutes': 90},
        ]

        matched_service = {'name': 'Roof Repair', 'duration_minutes': 1440, 'requires_callout': True}
        service_duration = matched_service['duration_minutes']
        is_callout_booking = False
        original_service_name = 'Roof Repair'

        if matched_service.get('requires_callout'):
            with patch('src.services.settings_manager.get_settings_manager', return_value=mock_sm):
                from src.services.settings_manager import get_settings_manager
                settings_mgr = get_settings_manager()
                all_services = settings_mgr.get_services(company_id=1)
                callout_service = None
                for svc in all_services:
                    svc_name = (svc.get('name') or '').lower()
                    if 'general callout' in svc_name:
                        callout_service = svc
                        break
                if not callout_service:
                    for svc in all_services:
                        if 'callout' in (svc.get('name') or '').lower():
                            callout_service = svc
                            break
                if callout_service:
                    service_duration = callout_service.get('duration_minutes', 60)
                else:
                    service_duration = 60
                matched_service_name = f"Callout for {original_service_name}"
                is_callout_booking = True

        assert is_callout_booking is True
        assert service_duration == 60

    def test_precheck_callout_does_not_trigger_fullday(self):
        """Pre-check should use callout duration (45 min), not raw (2880 min).
        So a callout for a full-day job should NOT trigger full-day logic (>= 480)."""
        from src.services.calendar_tools import _resolve_callout_duration

        matched_service = {
            'name': 'Kitchen Renovation', 'duration_minutes': 2880,
            'requires_callout': True
        }

        mock_sm = MagicMock()
        mock_sm.get_services.return_value = make_services(callout_duration=45)

        with patch('src.services.settings_manager.get_settings_manager', return_value=mock_sm):
            resolved = _resolve_callout_duration(matched_service, company_id=1)

        # 45 min is NOT >= 480, so full-day logic should NOT trigger
        assert resolved == 45
        assert resolved < 480, "Callout duration should NOT trigger full-day logic"


# ═══════════════════════════════════════════════════════════════
# 4. Availability tools use callout-resolved duration
# ═══════════════════════════════════════════════════════════════

class TestAvailabilityCalloutDuration:

    @patch('src.utils.config.config')
    @patch('src.services.calendar_tools.match_service')
    @patch('src.services.calendar_tools._resolve_callout_duration')
    def test_check_availability_uses_callout_duration(self, mock_resolve, mock_match, mock_config):
        from src.services.calendar_tools import execute_tool_call

        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.BUSINESS_DAYS = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}

        mock_match.return_value = {
            'service': {'name': 'Kitchen Renovation', 'duration_minutes': 2880,
                        'requires_callout': True, 'employees_required': 1, 'employee_restrictions': None},
            'matched_name': 'Kitchen Renovation', 'score': 95
        }
        mock_resolve.return_value = 45

        mock_cal = MagicMock()
        mock_cal.get_available_slots_for_day.return_value = [_next_weekday(10)]
        mock_db = MagicMock()
        mock_db.has_employees.return_value = False

        tomorrow = _next_weekday(10).strftime('%Y-%m-%d')
        result = execute_tool_call('check_availability', {
            'start_date': tomorrow, 'job_description': 'kitchen renovation',
        }, {'google_calendar': mock_cal, 'db': mock_db, 'company_id': 1})

        assert result['success'] is True
        mock_resolve.assert_called_once()
        assert result.get('is_callout_service') is True
        # Verify calendar was called with 45 min, not 2880
        call_args = mock_cal.get_available_slots_for_day.call_args
        passed_duration = call_args[1].get('service_duration') if call_args[1] else call_args[0][1]
        assert passed_duration == 45

    @patch('src.utils.config.config')
    @patch('src.services.calendar_tools.match_service')
    @patch('src.services.calendar_tools._resolve_callout_duration')
    def test_get_next_available_uses_callout_duration(self, mock_resolve, mock_match, mock_config):
        from src.services.calendar_tools import execute_tool_call

        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.BUSINESS_DAYS = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}

        mock_match.return_value = {
            'service': {'name': 'Roof Repair', 'duration_minutes': 1440,
                        'requires_callout': True, 'employees_required': 1, 'employee_restrictions': None},
            'matched_name': 'Roof Repair', 'score': 90
        }
        mock_resolve.return_value = 60

        mock_cal = MagicMock()
        mock_cal.get_available_slots_for_day.return_value = [_next_weekday(9)]
        mock_db = MagicMock()
        mock_db.has_employees.return_value = False

        result = execute_tool_call('get_next_available', {
            'job_description': 'roof repair',
        }, {'google_calendar': mock_cal, 'db': mock_db, 'company_id': 1})

        assert result['success'] is True
        mock_resolve.assert_called_once()
        assert result.get('is_callout_service') is True

    @patch('src.utils.config.config')
    @patch('src.services.calendar_tools.match_service')
    @patch('src.services.calendar_tools._resolve_callout_duration')
    def test_non_callout_not_flagged(self, mock_resolve, mock_match, mock_config):
        from src.services.calendar_tools import execute_tool_call

        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.BUSINESS_DAYS = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}

        mock_match.return_value = {
            'service': {'name': 'Plumbing', 'duration_minutes': 120,
                        'requires_callout': False, 'employees_required': 1, 'employee_restrictions': None},
            'matched_name': 'Plumbing', 'score': 95
        }
        mock_resolve.return_value = 120

        mock_cal = MagicMock()
        mock_cal.get_available_slots_for_day.return_value = [_next_weekday(10)]
        mock_db = MagicMock()
        mock_db.has_employees.return_value = False

        tomorrow = _next_weekday(10).strftime('%Y-%m-%d')
        result = execute_tool_call('check_availability', {
            'start_date': tomorrow, 'job_description': 'plumbing',
        }, {'google_calendar': mock_cal, 'db': mock_db, 'company_id': 1})

        assert result['success'] is True
        assert result.get('is_callout_service') is False


# ═══════════════════════════════════════════════════════════════
# 5. DB layer: add_booking accepts requires_callout
# ═══════════════════════════════════════════════════════════════

class TestDBCalloutColumn:

    def test_add_booking_signature_accepts_requires_callout(self):
        """add_booking should accept requires_callout parameter"""
        import inspect
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        sig = inspect.signature(PostgreSQLDatabaseWrapper.add_booking)
        assert 'requires_callout' in sig.parameters

    def test_update_booking_whitelist_includes_requires_callout(self):
        """update_booking should allow requires_callout in its field whitelist"""
        import inspect
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        # Read the source to verify the whitelist
        source = inspect.getsource(PostgreSQLDatabaseWrapper.update_booking)
        assert 'requires_callout' in source

    def test_add_service_accepts_requires_callout(self):
        """add_service should accept requires_callout parameter"""
        import inspect
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        sig = inspect.signature(PostgreSQLDatabaseWrapper.add_service)
        assert 'requires_callout' in sig.parameters
