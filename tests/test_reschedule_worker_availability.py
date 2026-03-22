"""
Integration tests for reschedule flow with worker-specific availability.

Tests the fix for the issue where:
1. User asks to reschedule a job
2. AI suggests available days from general availability
3. But the assigned worker isn't available on those days
4. Creating an endless loop

The fix ensures that when rescheduling, the system suggests days
when the ASSIGNED WORKER is available, not just general availability.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.calendar_tools import (
    execute_tool_call,
    _find_worker_available_days,
    CALENDAR_TOOLS
)


def mock_parse_datetime(text, require_time=True, default_time=None, allow_past=False):
    """Mock date parser that handles common test date formats."""
    text_lower = text.lower().strip()
    
    # Map common test dates to actual datetimes
    date_map = {
        'friday march 13th': datetime(2026, 3, 13, 9, 0),
        'friday': datetime(2026, 3, 13, 9, 0),
        'monday march 9th': datetime(2026, 3, 9, 9, 0),
        'monday': datetime(2026, 3, 9, 9, 0),
        'wednesday march 11th': datetime(2026, 3, 11, 9, 0),
        'wednesday': datetime(2026, 3, 11, 9, 0),
        'thursday march 12th': datetime(2026, 3, 12, 9, 0),
        'thursday': datetime(2026, 3, 12, 9, 0),
        'tuesday march 10th': datetime(2026, 3, 10, 9, 0),
        'tuesday': datetime(2026, 3, 10, 9, 0),
    }
    
    for key, value in date_map.items():
        if key in text_lower:
            return value
    return None


class TestFindWorkerAvailableDays:
    """Test the _find_worker_available_days helper function"""
    
    def create_mock_db(self, worker_available_days: list):
        """Create a mock DB where worker is available on specific days."""
        mock_db = Mock()
        
        def check_availability(worker_id, appointment_time, duration_minutes, exclude_booking_id, company_id):
            weekday = appointment_time.weekday()
            return {'available': weekday in worker_available_days}
        
        mock_db.check_worker_availability = Mock(side_effect=check_availability)
        return mock_db
    
    def test_finds_available_days_for_worker(self):
        """Worker available Mon/Wed/Fri should return those days"""
        mock_db = self.create_mock_db([0, 2, 4])  # Mon, Wed, Fri
        
        with patch('src.utils.config.config') as mock_config:
            mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
            mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
            
            available = _find_worker_available_days(
                db=mock_db, worker_ids=[1], duration_minutes=480,
                exclude_booking_id=None, company_id=1, days_to_check=14
            )
        
        assert len(available) > 0
        day_names = [d.split()[0] for d in available]
        assert any(d in ['Monday', 'Wednesday', 'Friday'] for d in day_names)
    
    def test_returns_empty_when_worker_never_available(self):
        """Worker with no availability should return empty list"""
        mock_db = self.create_mock_db([])
        
        with patch('src.utils.config.config') as mock_config:
            mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
            mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
            
            available = _find_worker_available_days(
                db=mock_db, worker_ids=[1], duration_minutes=480,
                exclude_booking_id=None, company_id=1, days_to_check=14
            )
        
        assert available == []
    
    def test_skips_weekends(self):
        """Should not return weekend days even if worker is available"""
        mock_db = self.create_mock_db([5, 6])  # Only Sat/Sun
        
        with patch('src.utils.config.config') as mock_config:
            mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
            mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
            
            available = _find_worker_available_days(
                db=mock_db, worker_ids=[1], duration_minutes=480,
                exclude_booking_id=None, company_id=1, days_to_check=14
            )
        
        assert available == []


class TestRescheduleWithWorkerAvailability:
    """Test reschedule flow includes worker-specific availability"""
    
    def create_mock_services(self, bookings, worker_available_days=None):
        mock_db = Mock()
        mock_db.get_all_bookings.return_value = bookings
        mock_db.update_booking.return_value = True
        mock_db.has_workers.return_value = True
        
        def get_worker(worker_id, company_id):
            return {'id': worker_id, 'name': f'Worker {worker_id}'}
        mock_db.get_worker = Mock(side_effect=get_worker)
        
        if worker_available_days is not None:
            def check_availability(worker_id, appointment_time, duration_minutes, exclude_booking_id, company_id):
                weekday = appointment_time.weekday()
                return {'available': weekday in worker_available_days}
            mock_db.check_worker_availability = Mock(side_effect=check_availability)
        else:
            mock_db.check_worker_availability = Mock(return_value={'available': True})
        
        mock_calendar = Mock()
        mock_calendar.reschedule_appointment.return_value = {'id': 'evt1'}
        mock_calendar.check_availability.return_value = True
        mock_calendar.service = None
        
        return {'db': mock_db, 'google_calendar': mock_calendar, 'company_id': 1}
    
    @patch('src.utils.date_parser.parse_datetime', side_effect=mock_parse_datetime)
    @patch('src.utils.config.config')
    def test_reschedule_suggests_worker_available_days_on_name_confirm(self, mock_config, mock_parse):
        """When customer name is confirmed, response should include available days."""
        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
        
        bookings = [{
            'id': 1, 'client_name': 'James Doherty',
            'appointment_time': '2026-03-13 09:00:00',
            'service_type': 'Brick wall build', 'duration_minutes': 480,
            'status': 'scheduled', 'calendar_event_id': 'evt1',
            'assigned_worker_ids': [1]
        }]
        
        services = self.create_mock_services(bookings, worker_available_days=[2, 3, 4])
        
        result = execute_tool_call(
            'reschedule_job',
            {'current_date': 'Friday March 13th', 'customer_name': 'James Doherty'},
            services
        )
        
        assert result.get('customer_name_confirmed') == True
        error_msg = result.get('error', '')
        # Should mention available days for the worker
        has_days = 'Wednesday' in error_msg or 'Thursday' in error_msg or 'available_days' in result
        assert has_days, f"Should include worker's available days. Got: {error_msg}"

    
    @patch('src.utils.date_parser.parse_datetime', side_effect=mock_parse_datetime)
    @patch('src.utils.config.config')
    def test_reschedule_failure_includes_worker_available_days(self, mock_config, mock_parse):
        """When reschedule fails, response should include days when worker IS available."""
        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
        
        bookings = [{
            'id': 1, 'client_name': 'James Doherty',
            'appointment_time': '2026-03-13 09:00:00',
            'service_type': 'Brick wall build', 'duration_minutes': 480,
            'status': 'scheduled', 'calendar_event_id': 'evt1',
            'assigned_worker_ids': [1]
        }]
        
        # Worker only available Wed/Thu/Fri (not Monday)
        services = self.create_mock_services(bookings, worker_available_days=[2, 3, 4])
        
        with patch('src.utils.config.Config') as MockConfig:
            MockConfig.get_business_hours.return_value = {'start': 9, 'end': 17}
            MockConfig.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
            MockConfig.BUSINESS_DAYS = [0, 1, 2, 3, 4]
            
            result = execute_tool_call(
                'reschedule_job',
                {'current_date': 'Friday', 'customer_name': 'James Doherty', 'new_datetime': 'Monday'},
                services
            )
        
        assert result['success'] == False
        error_msg = result.get('error', '')
        assert 'not available' in error_msg.lower()
        # Should suggest alternative days
        has_alternatives = 'available on' in error_msg.lower() or 'available_days' in result
        assert has_alternatives, f"Should suggest alternatives. Got: {error_msg}"
    
    @patch('src.utils.date_parser.parse_datetime', side_effect=mock_parse_datetime)
    @patch('src.utils.config.config')
    def test_reschedule_succeeds_when_worker_available(self, mock_config, mock_parse):
        """Reschedule should succeed when worker is available on new date."""
        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
        
        bookings = [{
            'id': 1, 'client_name': 'James Doherty',
            'appointment_time': '2026-03-13 09:00:00',
            'service_type': 'Brick wall build', 'duration_minutes': 480,
            'status': 'scheduled', 'calendar_event_id': 'evt1',
            'assigned_worker_ids': [1]
        }]
        
        # Worker available all weekdays
        services = self.create_mock_services(bookings, worker_available_days=[0, 1, 2, 3, 4])
        
        with patch('src.utils.config.Config') as MockConfig:
            MockConfig.get_business_hours.return_value = {'start': 9, 'end': 17}
            MockConfig.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
            MockConfig.BUSINESS_DAYS = [0, 1, 2, 3, 4]
            
            result = execute_tool_call(
                'reschedule_job',
                {'current_date': 'Friday', 'customer_name': 'James Doherty', 'new_datetime': 'Wednesday'},
                services
            )
        
        assert result.get('requires_reschedule_confirmation') == True
        assert 'confirm' in result['message'].lower()
        
        # Now confirm
        with patch('src.utils.config.Config') as MockConfig:
            MockConfig.get_business_hours.return_value = {'start': 9, 'end': 17}
            MockConfig.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
            MockConfig.BUSINESS_DAYS = [0, 1, 2, 3, 4]
            
            result = execute_tool_call(
                'reschedule_job',
                {'current_date': 'Friday', 'customer_name': 'James Doherty', 'new_datetime': 'Wednesday', 'confirmed': True},
                services
            )
        
        assert result['success'] == True
        assert 'rescheduled' in result['message'].lower()


class TestFullRescheduleConversationFlow:
    """Test the complete conversation flow for rescheduling."""
    
    def create_mock_services(self, bookings, worker_available_days):
        mock_db = Mock()
        mock_db.get_all_bookings.return_value = bookings
        mock_db.update_booking.return_value = True
        mock_db.has_workers.return_value = True
        
        def get_worker(worker_id, company_id):
            return {'id': worker_id, 'name': 'Brick guy'}
        mock_db.get_worker = Mock(side_effect=get_worker)
        
        def check_availability(worker_id, appointment_time, duration_minutes, exclude_booking_id, company_id):
            weekday = appointment_time.weekday()
            return {'available': weekday in worker_available_days}
        mock_db.check_worker_availability = Mock(side_effect=check_availability)
        
        mock_calendar = Mock()
        mock_calendar.reschedule_appointment.return_value = {'id': 'evt1'}
        mock_calendar.service = None
        
        return {'db': mock_db, 'google_calendar': mock_calendar, 'company_id': 1}
    
    @patch('src.utils.date_parser.parse_datetime', side_effect=mock_parse_datetime)
    @patch('src.utils.config.config')
    def test_full_reschedule_flow_with_worker_restrictions(self, mock_config, mock_parse):
        """Test complete reschedule flow with worker availability."""
        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
        
        bookings = [
            {'id': 1, 'client_name': 'Patrick Smith', 'appointment_time': '2026-03-13 09:00:00',
             'service_type': 'Cobble stone', 'duration_minutes': 480, 'status': 'scheduled',
             'calendar_event_id': 'evt1', 'assigned_worker_ids': [1]},
            {'id': 2, 'client_name': 'James Doherty', 'appointment_time': '2026-03-13 09:00:00',
             'service_type': 'Brick wall', 'duration_minutes': 480, 'status': 'scheduled',
             'calendar_event_id': 'evt2', 'assigned_worker_ids': [2]}
        ]
        
        # Worker only available Wed/Thu/Fri
        services = self.create_mock_services(bookings, worker_available_days=[2, 3, 4])
        
        # Step 1: Ask about Friday - should list both bookings
        result1 = execute_tool_call('reschedule_job', {'current_date': 'Friday'}, services)
        assert result1['requires_confirmation'] == True
        assert 'Patrick Smith' in result1['message']
        assert 'James Doherty' in result1['message']
        
        # Step 2: Confirm name - should include available days
        result2 = execute_tool_call(
            'reschedule_job',
            {'current_date': 'Friday', 'customer_name': 'James Doherty'},
            services
        )
        assert result2['customer_name_confirmed'] == True
        error_msg = result2.get('error', '')
        has_days = 'Wednesday' in error_msg or 'Thursday' in error_msg or 'available_days' in result2
        assert has_days, f"Should include available days. Got: {error_msg}"

    
    @patch('src.utils.date_parser.parse_datetime', side_effect=mock_parse_datetime)
    @patch('src.utils.config.config')
    def test_reschedule_loop_prevention(self, mock_config, mock_parse):
        """Verify the fix prevents the endless loop scenario."""
        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
        
        bookings = [{
            'id': 1, 'client_name': 'James Doherty',
            'appointment_time': '2026-03-13 09:00:00',
            'service_type': 'Brick wall build', 'duration_minutes': 480,
            'status': 'scheduled', 'calendar_event_id': 'evt1',
            'assigned_worker_ids': [1]
        }]
        
        # Worker only available Wed/Thu/Fri
        services = self.create_mock_services(bookings, worker_available_days=[2, 3, 4])
        
        with patch('src.utils.config.Config') as MockConfig:
            MockConfig.get_business_hours.return_value = {'start': 9, 'end': 17}
            MockConfig.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
            MockConfig.BUSINESS_DAYS = [0, 1, 2, 3, 4]
            
            # User tries Monday (worker not available)
            result = execute_tool_call(
                'reschedule_job',
                {'current_date': 'Friday', 'customer_name': 'James Doherty', 'new_datetime': 'Monday'},
                services
            )
        
        assert result['success'] == False
        error_msg = result.get('error', '')
        assert 'not available' in error_msg.lower()
        
        # KEY: Should include SPECIFIC available days
        has_specific_days = (
            'available_days' in result or
            'Wednesday' in error_msg or 'Thursday' in error_msg or 'Friday' in error_msg
        )
        assert has_specific_days, f"Should include specific available days. Got: {error_msg}"
        
        # Should NOT just say "suggest another day" without specifics
        vague_only = 'suggest another day' in error_msg.lower() and not has_specific_days
        assert not vague_only, "Response should include specific days, not vague suggestion"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
