"""
Comprehensive tests for the cancel/reschedule functionality.
Tests the day-based lookup with fuzzy name matching for:
- Single job on a day
- Multiple jobs on a day
- Full-day jobs
- Workers with multiple jobs
- Fuzzy name matching edge cases
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.calendar_tools import (
    fuzzy_match_name,
    find_jobs_on_day,
    execute_tool_call,
    CALENDAR_TOOLS
)


class TestFuzzyMatchName:
    """Test the fuzzy name matching function"""
    
    def test_exact_match(self):
        """Exact name match should return 100% confidence"""
        names = ['John Smith', 'Jane Doe', 'Michael Johnson']
        result = fuzzy_match_name('John Smith', names)
        assert result == ('John Smith', 100, 0)
    
    def test_exact_match_case_insensitive(self):
        """Exact match should be case insensitive"""
        names = ['John Smith', 'Jane Doe']
        result = fuzzy_match_name('john smith', names)
        assert result == ('John Smith', 100, 0)
    
    def test_partial_first_name(self):
        """First name only should match with reasonable confidence"""
        names = ['John Smith', 'Jane Doe', 'Michael Johnson']
        result = fuzzy_match_name('John', names)
        assert result[0] == 'John Smith'
        assert result[1] >= 70  # Strategy 4: single-word exact match = 75
        assert result[2] == 0
    
    def test_partial_last_name(self):
        """Last name only should match with reasonable confidence"""
        names = ['John Smith', 'Jane Doe', 'Michael Johnson']
        result = fuzzy_match_name('Smith', names)
        assert result[0] == 'John Smith'
        assert result[1] >= 70  # Strategy 4: single-word exact match = 75
    
    def test_fuzzy_typo(self):
        """Should handle minor typos"""
        names = ['John Smith', 'Jane Doe']
        result = fuzzy_match_name('Jon Smith', names)  # Missing 'h'
        assert result[0] == 'John Smith'
        assert result[1] >= 50  # Should still match
    
    def test_stt_error_similar_sound(self):
        """Should handle STT errors with similar sounding names"""
        names = ['Sean Murphy', 'Jane Doe']
        result = fuzzy_match_name('Shawn Murphy', names)  # STT might hear Shawn
        assert result[0] == 'Sean Murphy'
        assert result[1] >= 50
    
    def test_no_match_low_confidence(self):
        """Completely different name should have low confidence"""
        names = ['John Smith', 'Jane Doe']
        result = fuzzy_match_name('Robert Williams', names)
        assert result[1] < 50  # Low confidence
    
    def test_empty_spoken_name(self):
        """Empty spoken name should return None"""
        names = ['John Smith', 'Jane Doe']
        result = fuzzy_match_name('', names)
        assert result == (None, 0, -1)
    
    def test_empty_candidate_list(self):
        """Empty candidate list should return None"""
        result = fuzzy_match_name('John', [])
        assert result == (None, 0, -1)
    
    def test_irish_names(self):
        """Should handle Irish names correctly (accent stripping for STT)"""
        names = ['Seán Ó Doherty', 'Siobhán Murphy', 'Ciarán Walsh']
        
        # Test with anglicized version - accent stripping should handle seán→sean
        result = fuzzy_match_name('Sean Doherty', names)
        assert result[0] == 'Seán Ó Doherty'
        assert result[1] >= 50
    
    def test_multiple_similar_names(self):
        """Should pick the best match when multiple similar names exist"""
        names = ['John Smith', 'John Smyth', 'Johnny Smith']
        result = fuzzy_match_name('John Smith', names)
        assert result == ('John Smith', 100, 0)  # Exact match
    
    def test_name_with_middle_name(self):
        """Should match even if middle name is included/excluded"""
        names = ['John Michael Smith', 'Jane Doe']
        result = fuzzy_match_name('John Smith', names)
        assert result[0] == 'John Michael Smith'
        assert result[1] >= 70


class TestFindJobsOnDay:
    """Test the find_jobs_on_day function"""
    
    def create_mock_db(self, bookings):
        """Create a mock database with given bookings"""
        mock_db = Mock()
        mock_db.get_all_bookings.return_value = bookings
        mock_db.get_worker.return_value = None
        return mock_db
    
    def test_single_job_on_day(self):
        """Should find a single job on a day"""
        target_date = datetime(2026, 3, 10, 10, 0)  # Tuesday
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-03-10 10:00:00',
            'service_type': 'Plumbing',
            'duration_minutes': 60,
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        mock_db = self.create_mock_db(bookings)
        jobs = find_jobs_on_day(target_date, mock_db, company_id=1)
        
        assert len(jobs) == 1
        assert jobs[0]['name'] == 'John Smith'
        assert jobs[0]['service'] == 'Plumbing'
        assert jobs[0]['is_full_day'] == False
    
    def test_multiple_jobs_on_day(self):
        """Should find multiple jobs on the same day"""
        target_date = datetime(2026, 3, 10, 10, 0)
        bookings = [
            {
                'id': 1,
                'client_name': 'John Smith',
                'appointment_time': '2026-03-10 09:00:00',
                'service_type': 'Plumbing',
                'duration_minutes': 60,
                'status': 'scheduled',
                'calendar_event_id': 'evt1',
                'assigned_worker_ids': []
            },
            {
                'id': 2,
                'client_name': 'Jane Doe',
                'appointment_time': '2026-03-10 14:00:00',
                'service_type': 'Electrical',
                'duration_minutes': 120,
                'status': 'scheduled',
                'calendar_event_id': 'evt2',
                'assigned_worker_ids': []
            },
            {
                'id': 3,
                'client_name': 'Mike Johnson',
                'appointment_time': '2026-03-11 10:00:00',  # Different day
                'service_type': 'Painting',
                'duration_minutes': 60,
                'status': 'scheduled',
                'calendar_event_id': 'evt3',
                'assigned_worker_ids': []
            }
        ]
        
        mock_db = self.create_mock_db(bookings)
        jobs = find_jobs_on_day(target_date, mock_db, company_id=1)
        
        assert len(jobs) == 2
        names = [j['name'] for j in jobs]
        assert 'John Smith' in names
        assert 'Jane Doe' in names
        assert 'Mike Johnson' not in names
    
    def test_full_day_job(self):
        """Should correctly identify full-day jobs (8+ hours)"""
        target_date = datetime(2026, 3, 10, 10, 0)
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-03-10 08:00:00',
            'service_type': 'Brick Work',
            'duration_minutes': 480,  # 8 hours = full day
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        mock_db = self.create_mock_db(bookings)
        jobs = find_jobs_on_day(target_date, mock_db, company_id=1)
        
        assert len(jobs) == 1
        assert jobs[0]['is_full_day'] == True
        assert jobs[0]['time'] == 'Full day'
    
    def test_excludes_cancelled_jobs(self):
        """Should not include cancelled jobs"""
        target_date = datetime(2026, 3, 10, 10, 0)
        bookings = [
            {
                'id': 1,
                'client_name': 'John Smith',
                'appointment_time': '2026-03-10 10:00:00',
                'service_type': 'Plumbing',
                'duration_minutes': 60,
                'status': 'cancelled',
                'calendar_event_id': 'evt1',
                'assigned_worker_ids': []
            },
            {
                'id': 2,
                'client_name': 'Jane Doe',
                'appointment_time': '2026-03-10 14:00:00',
                'service_type': 'Electrical',
                'duration_minutes': 60,
                'status': 'scheduled',
                'calendar_event_id': 'evt2',
                'assigned_worker_ids': []
            }
        ]
        
        mock_db = self.create_mock_db(bookings)
        jobs = find_jobs_on_day(target_date, mock_db, company_id=1)
        
        assert len(jobs) == 1
        assert jobs[0]['name'] == 'Jane Doe'
    
    def test_no_jobs_on_day(self):
        """Should return empty list when no jobs on day"""
        target_date = datetime(2026, 3, 10, 10, 0)
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-03-11 10:00:00',  # Different day
            'service_type': 'Plumbing',
            'duration_minutes': 60,
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        mock_db = self.create_mock_db(bookings)
        jobs = find_jobs_on_day(target_date, mock_db, company_id=1)
        
        assert len(jobs) == 0


class TestCancelAppointmentHandler:
    """Test the cancel_appointment tool handler"""
    
    def create_mock_services(self, bookings):
        """Create mock services for testing"""
        mock_db = Mock()
        mock_db.get_all_bookings.return_value = bookings
        mock_db.get_worker.return_value = None
        mock_db.delete_booking.return_value = True
        
        mock_calendar = Mock()
        mock_calendar.cancel_appointment.return_value = True
        # Prevent find_jobs_on_day from trying the GCal path
        mock_calendar.service = None
        
        return {
            'db': mock_db,
            'google_calendar': mock_calendar,
            'company_id': 1
        }
    
    def test_first_call_single_job(self):
        """First call with day only should return single job for confirmation"""
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-04-10 10:00:00',
            'service_type': 'Plumbing',
            'duration_minutes': 60,
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        result = execute_tool_call(
            'cancel_appointment',
            {'appointment_date': 'April 10th'},
            services
        )
        
        assert result['success'] == False
        assert result['requires_confirmation'] == True
        assert 'John Smith' in result['message']
        assert len(result['customer_names']) == 1
    
    def test_first_call_multiple_jobs(self):
        """First call should list all jobs on that day"""
        bookings = [
            {
                'id': 1,
                'client_name': 'John Smith',
                'appointment_time': '2026-04-10 09:00:00',
                'service_type': 'Plumbing',
                'duration_minutes': 60,
                'status': 'scheduled',
                'calendar_event_id': 'evt1',
                'assigned_worker_ids': []
            },
            {
                'id': 2,
                'client_name': 'Jane Doe',
                'appointment_time': '2026-04-10 14:00:00',
                'service_type': 'Electrical',
                'duration_minutes': 60,
                'status': 'scheduled',
                'calendar_event_id': 'evt2',
                'assigned_worker_ids': []
            }
        ]
        
        services = self.create_mock_services(bookings)
        
        result = execute_tool_call(
            'cancel_appointment',
            {'appointment_date': 'April 10th'},
            services
        )
        
        assert result['success'] == False
        assert result['requires_confirmation'] == True
        assert 'John Smith' in result['message']
        assert 'Jane Doe' in result['message']
        assert len(result['customer_names']) == 2
    
    def test_second_call_with_name_cancels(self):
        """Second call with name should complete cancellation"""
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-04-10 10:00:00',
            'service_type': 'Plumbing',
            'duration_minutes': 60,
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        result = execute_tool_call(
            'cancel_appointment',
            {'appointment_date': 'April 10th', 'customer_name': 'John Smith'},
            services
        )
        
        assert result['success'] == True
        assert 'cancelled' in result['message'].lower()
        services['db'].delete_booking.assert_called_once()
    
    def test_fuzzy_name_match_on_cancel(self):
        """Should use fuzzy matching to find the right job"""
        bookings = [
            {
                'id': 1,
                'client_name': 'John Smith',
                'appointment_time': '2026-04-10 09:00:00',
                'service_type': 'Plumbing',
                'duration_minutes': 60,
                'status': 'scheduled',
                'calendar_event_id': 'evt1',
                'assigned_worker_ids': []
            },
            {
                'id': 2,
                'client_name': 'Jane Doe',
                'appointment_time': '2026-04-10 14:00:00',
                'service_type': 'Electrical',
                'duration_minutes': 60,
                'status': 'scheduled',
                'calendar_event_id': 'evt2',
                'assigned_worker_ids': []
            }
        ]
        
        services = self.create_mock_services(bookings)
        
        # Use partial name "John" - should match "John Smith"
        result = execute_tool_call(
            'cancel_appointment',
            {'appointment_date': 'April 10th', 'customer_name': 'John'},
            services
        )
        
        assert result['success'] == True
        assert 'John Smith' in result['message']
    
    def test_no_jobs_on_day(self):
        """Should return error when no jobs on that day"""
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-04-11 10:00:00',  # Different day
            'service_type': 'Plumbing',
            'duration_minutes': 60,
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        result = execute_tool_call(
            'cancel_appointment',
            {'appointment_date': 'April 10th'},
            services
        )
        
        assert result['success'] == False
        assert 'No bookings found' in result['error']
    
    def test_name_not_found_on_day(self):
        """Should return error when name doesn't match any job on that day"""
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-04-10 10:00:00',
            'service_type': 'Plumbing',
            'duration_minutes': 60,
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        result = execute_tool_call(
            'cancel_appointment',
            {'appointment_date': 'April 10th', 'customer_name': 'Robert Williams'},
            services
        )
        
        assert result['success'] == False
        assert "couldn't find" in result['error'].lower() or 'no bookings found' in result['error'].lower()


class TestRescheduleAppointmentHandler:
    """Test the reschedule_appointment tool handler"""
    
    def create_mock_services(self, bookings, has_workers=False):
        """Create mock services for testing"""
        mock_db = Mock()
        mock_db.get_all_bookings.return_value = bookings
        mock_db.get_worker.return_value = None
        mock_db.update_booking.return_value = True
        mock_db.has_workers.return_value = has_workers
        
        mock_calendar = Mock()
        mock_calendar.reschedule_appointment.return_value = {'id': 'evt1'}
        mock_calendar.check_availability.return_value = True
        # Prevent find_jobs_on_day from trying the GCal path
        mock_calendar.service = None
        
        return {
            'db': mock_db,
            'google_calendar': mock_calendar,
            'company_id': 1
        }
    
    def test_first_call_returns_jobs_list(self):
        """First call with day only should return jobs for confirmation"""
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-04-10 10:00:00',
            'service_type': 'Plumbing',
            'duration_minutes': 60,
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        result = execute_tool_call(
            'reschedule_appointment',
            {'current_date': 'April 10th'},
            services
        )
        
        assert result['success'] == False
        assert result['requires_confirmation'] == True
        assert 'John Smith' in result['message']
    
    def test_second_call_asks_for_new_date(self):
        """Second call with name but no new date should ask for new date"""
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-04-10 10:00:00',
            'service_type': 'Plumbing',
            'duration_minutes': 60,
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        result = execute_tool_call(
            'reschedule_appointment',
            {'current_date': 'April 10th', 'customer_name': 'John Smith'},
            services
        )
        
        assert result['success'] == False
        assert result.get('customer_name_confirmed') == True
        assert 'What day' in result['error']
    
    def test_third_call_completes_reschedule(self):
        """Third call with all params should complete reschedule"""
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-04-10 10:00:00',
            'service_type': 'Plumbing',
            'duration_minutes': 60,
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        result = execute_tool_call(
            'reschedule_appointment',
            {
                'current_date': 'April 10th',
                'customer_name': 'John Smith',
                'new_datetime': 'April 15th at 2pm'
            },
            services
        )
        
        assert result['success'] == True
        assert 'rescheduled' in result['message'].lower()
        services['db'].update_booking.assert_called_once()
    
    def test_full_day_job_reschedule(self):
        """Full-day job should reschedule without asking for time"""
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-04-10 08:00:00',
            'service_type': 'Brick Work',
            'duration_minutes': 480,  # Full day
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        # First call - should show as full day
        result = execute_tool_call(
            'reschedule_appointment',
            {'current_date': 'April 10th'},
            services
        )
        
        assert 'full day' in result['message'].lower()
        
        # Complete reschedule - just provide day, not time
        result = execute_tool_call(
            'reschedule_appointment',
            {
                'current_date': 'April 10th',
                'customer_name': 'John Smith',
                'new_datetime': 'April 15th'  # No time specified
            },
            services
        )
        
        assert result['success'] == True
        assert 'full-day' in result['message'].lower()


class TestToolDefinitions:
    """Test that tool definitions are correct"""
    
    def test_cancel_job_uses_appointment_date(self):
        """cancel_job should use appointment_date parameter"""
        cancel_tool = next(t for t in CALENDAR_TOOLS if t['function']['name'] == 'cancel_job')
        params = cancel_tool['function']['parameters']['properties']
        
        assert 'appointment_date' in params
        assert 'appointment_datetime' not in params
        assert cancel_tool['function']['parameters']['required'] == ['appointment_date']
    
    def test_reschedule_job_uses_current_date(self):
        """reschedule_job should use current_date parameter"""
        reschedule_tool = next(t for t in CALENDAR_TOOLS if t['function']['name'] == 'reschedule_job')
        params = reschedule_tool['function']['parameters']['properties']
        
        assert 'current_date' in params
        assert 'current_datetime' not in params
        assert reschedule_tool['function']['parameters']['required'] == ['current_date']
    
    def test_cancel_appointment_uses_appointment_date(self):
        """cancel_appointment should use appointment_date parameter"""
        cancel_tool = next(t for t in CALENDAR_TOOLS if t['function']['name'] == 'cancel_appointment')
        params = cancel_tool['function']['parameters']['properties']
        
        assert 'appointment_date' in params
    
    def test_reschedule_appointment_uses_current_date(self):
        """reschedule_appointment should use current_date parameter"""
        reschedule_tool = next(t for t in CALENDAR_TOOLS if t['function']['name'] == 'reschedule_appointment')
        params = reschedule_tool['function']['parameters']['properties']
        
        assert 'current_date' in params


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def create_mock_services(self, bookings):
        mock_db = Mock()
        mock_db.get_all_bookings.return_value = bookings
        mock_db.get_worker.return_value = None
        mock_db.delete_booking.return_value = True
        mock_db.has_workers.return_value = False
        
        mock_calendar = Mock()
        mock_calendar.cancel_appointment.return_value = True
        mock_calendar.check_availability.return_value = True
        # Prevent find_jobs_on_day from trying the GCal path
        mock_calendar.service = None
        
        return {
            'db': mock_db,
            'google_calendar': mock_calendar,
            'company_id': 1
        }
    
    def test_invalid_date_format(self):
        """Should handle invalid date formats - AI defaults to tomorrow"""
        services = self.create_mock_services([])
        
        result = execute_tool_call(
            'cancel_appointment',
            {'appointment_date': 'gibberish not a date'},
            services
        )
        
        # AI parser defaults to tomorrow when it can't understand
        # So we get "no bookings found" rather than "could not understand"
        assert result['success'] == False
        # Either error message is acceptable
        assert 'No bookings found' in result['error'] or 'Could not understand' in result['error']
    
    def test_missing_date_parameter(self):
        """Should handle missing date parameter"""
        services = self.create_mock_services([])
        
        result = execute_tool_call(
            'cancel_appointment',
            {},
            services
        )
        
        assert result['success'] == False
        assert 'ask the customer' in result['error'].lower()
    
    def test_worker_with_multiple_jobs_same_day(self):
        """Should handle worker with multiple jobs on same day"""
        bookings = [
            {
                'id': 1,
                'client_name': 'John Smith',
                'appointment_time': '2026-04-10 09:00:00',
                'service_type': 'Plumbing',
                'duration_minutes': 60,
                'status': 'scheduled',
                'calendar_event_id': 'evt1',
                'assigned_worker_ids': [1]  # Worker 1
            },
            {
                'id': 2,
                'client_name': 'Jane Doe',
                'appointment_time': '2026-04-10 14:00:00',
                'service_type': 'Plumbing',
                'duration_minutes': 60,
                'status': 'scheduled',
                'calendar_event_id': 'evt2',
                'assigned_worker_ids': [1]  # Same worker
            }
        ]
        
        services = self.create_mock_services(bookings)
        
        result = execute_tool_call(
            'cancel_appointment',
            {'appointment_date': 'April 10th'},
            services
        )
        
        # Should list both jobs
        assert result['requires_confirmation'] == True
        assert len(result['customer_names']) == 2
    
    def test_mixed_full_day_and_short_jobs(self):
        """Should handle mix of full-day and short jobs on same day"""
        bookings = [
            {
                'id': 1,
                'client_name': 'John Smith',
                'appointment_time': '2026-04-10 08:00:00',
                'service_type': 'Brick Work',
                'duration_minutes': 480,  # Full day
                'status': 'scheduled',
                'calendar_event_id': 'evt1',
                'assigned_worker_ids': [1]
            },
            {
                'id': 2,
                'client_name': 'Jane Doe',
                'appointment_time': '2026-04-10 10:00:00',
                'service_type': 'Consultation',
                'duration_minutes': 30,  # Short job
                'status': 'scheduled',
                'calendar_event_id': 'evt2',
                'assigned_worker_ids': [2]  # Different worker
            }
        ]
        
        services = self.create_mock_services(bookings)
        
        result = execute_tool_call(
            'cancel_appointment',
            {'appointment_date': 'April 10th'},
            services
        )
        
        # Should list both with appropriate time info
        assert 'full day' in result['message'].lower()
        assert len(result['customer_names']) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
