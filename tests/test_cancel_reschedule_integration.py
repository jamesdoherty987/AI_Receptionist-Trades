"""
Integration tests for cancel/reschedule flows.
Tests the complete conversation flow including:
- AI prompt understanding
- Tool call sequences
- Response formatting
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.calendar_tools import (
    fuzzy_match_name,
    find_jobs_on_day,
    execute_tool_call,
    CALENDAR_TOOLS
)


class TestCancelFlowIntegration:
    """Test complete cancel flow scenarios"""
    
    def create_mock_services(self, bookings):
        mock_db = Mock()
        mock_db.get_all_bookings.return_value = bookings
        mock_db.get_worker.return_value = None
        mock_db.delete_booking.return_value = True
        mock_db.has_workers.return_value = False
        
        mock_calendar = Mock()
        mock_calendar.cancel_appointment.return_value = True
        
        return {
            'db': mock_db,
            'google_calendar': mock_calendar,
            'company_id': 1
        }
    
    def test_cancel_single_job_flow(self):
        """
        Scenario: Customer calls to cancel, only one job on that day
        Flow: 
        1. AI asks "What day is your booking for?"
        2. Customer: "Thursday"
        3. AI calls cancel_job(appointment_date="Thursday")
        4. System returns: "I have one booking on Thursday for John Smith. Is that your booking?"
        5. Customer: "Yes"
        6. AI calls cancel_job(appointment_date="Thursday", customer_name="John Smith")
        7. System returns: "Successfully cancelled"
        """
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-03-12 10:00:00',  # Thursday
            'service_type': 'Plumbing',
            'duration_minutes': 60,
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        # Step 1: First call with just the day
        result1 = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday March 12th'},
            services
        )
        
        assert result1['requires_confirmation'] == True
        assert 'John Smith' in result1['message']
        assert 'Is that your booking' in result1['message']
        
        # Step 2: Second call with confirmation
        result2 = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday March 12th', 'customer_name': 'John Smith'},
            services
        )
        
        assert result2['success'] == True
        assert 'cancelled' in result2['message'].lower()
    
    def test_cancel_multiple_jobs_flow(self):
        """
        Scenario: Multiple jobs on same day, AI must list all names
        """
        bookings = [
            {
                'id': 1,
                'client_name': 'John Smith',
                'appointment_time': '2026-03-12 09:00:00',
                'service_type': 'Plumbing',
                'duration_minutes': 60,
                'status': 'scheduled',
                'calendar_event_id': 'evt1',
                'assigned_worker_ids': []
            },
            {
                'id': 2,
                'client_name': 'Jane Doe',
                'appointment_time': '2026-03-12 11:00:00',
                'service_type': 'Electrical',
                'duration_minutes': 90,
                'status': 'scheduled',
                'calendar_event_id': 'evt2',
                'assigned_worker_ids': []
            },
            {
                'id': 3,
                'client_name': 'Mike Wilson',
                'appointment_time': '2026-03-12 14:00:00',
                'service_type': 'Painting',
                'duration_minutes': 120,
                'status': 'scheduled',
                'calendar_event_id': 'evt3',
                'assigned_worker_ids': []
            }
        ]
        
        services = self.create_mock_services(bookings)
        
        # First call - should list all 3 names
        result1 = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday March 12th'},
            services
        )
        
        assert result1['requires_confirmation'] == True
        assert len(result1['customer_names']) == 3
        assert 'John Smith' in result1['message']
        assert 'Jane Doe' in result1['message']
        assert 'Mike Wilson' in result1['message']
        assert 'Which name is yours' in result1['message']
        
        # Customer says "Jane" - fuzzy match should work
        result2 = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday March 12th', 'customer_name': 'Jane'},
            services
        )
        
        assert result2['success'] == True
        assert 'Jane Doe' in result2['message']
    
    def test_cancel_full_day_job(self):
        """
        Scenario: Full-day job (8+ hours) - should not mention time
        """
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-03-12 08:00:00',
            'service_type': 'Brick Work',
            'duration_minutes': 480,  # Full day
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        result1 = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday March 12th'},
            services
        )
        
        assert 'full day' in result1['message'].lower()
        
        result2 = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday March 12th', 'customer_name': 'John Smith'},
            services
        )
        
        assert result2['success'] == True
        assert 'full-day' in result2['message'].lower()
    
    def test_cancel_with_stt_name_error(self):
        """
        Scenario: STT mishears name slightly, fuzzy match should still work
        """
        bookings = [{
            'id': 1,
            'client_name': 'Seán O\'Doherty',
            'appointment_time': '2026-03-12 10:00:00',
            'service_type': 'Plumbing',
            'duration_minutes': 60,
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        # STT might hear "Sean Doherty" without the accent and O'
        result = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday March 12th', 'customer_name': 'Sean Doherty'},
            services
        )
        
        assert result['success'] == True
        assert "Seán O'Doherty" in result['message']


class TestRescheduleFlowIntegration:
    """Test complete reschedule flow scenarios"""
    
    def create_mock_services(self, bookings, has_workers=False):
        mock_db = Mock()
        mock_db.get_all_bookings.return_value = bookings
        mock_db.get_worker.return_value = None
        mock_db.update_booking.return_value = True
        mock_db.has_workers.return_value = has_workers
        
        mock_calendar = Mock()
        mock_calendar.reschedule_appointment.return_value = {'id': 'evt1'}
        mock_calendar.check_availability.return_value = True
        
        return {
            'db': mock_db,
            'google_calendar': mock_calendar,
            'company_id': 1
        }
    
    def test_reschedule_three_step_flow(self):
        """
        Scenario: Complete reschedule flow
        1. AI asks "What day is your booking for?"
        2. Customer: "Monday"
        3. AI calls reschedule_job(current_date="Monday")
        4. System returns names on that day
        5. Customer confirms name
        6. AI calls reschedule_job(current_date="Monday", customer_name="John")
        7. System asks for new date
        8. Customer: "Move it to Wednesday"
        9. AI calls reschedule_job(current_date="Monday", customer_name="John", new_datetime="Wednesday")
        10. System confirms reschedule
        """
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-03-09 10:00:00',  # Monday
            'service_type': 'Plumbing',
            'duration_minutes': 60,
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        # Step 1: First call - get jobs on day
        result1 = execute_tool_call(
            'reschedule_job',
            {'current_date': 'Monday March 9th'},
            services
        )
        
        assert result1['requires_confirmation'] == True
        assert 'John Smith' in result1['message']
        
        # Step 2: Confirm name, no new date yet
        result2 = execute_tool_call(
            'reschedule_job',
            {'current_date': 'Monday March 9th', 'customer_name': 'John Smith'},
            services
        )
        
        assert result2['success'] == False
        assert result2.get('customer_name_confirmed') == True
        assert 'What day' in result2['error']
        
        # Step 3: Provide new date
        result3 = execute_tool_call(
            'reschedule_job',
            {
                'current_date': 'Monday March 9th',
                'customer_name': 'John Smith',
                'new_datetime': 'Wednesday March 11th at 2pm'
            },
            services
        )
        
        assert result3['success'] == True
        assert 'rescheduled' in result3['message'].lower()
    
    def test_reschedule_full_day_job(self):
        """
        Scenario: Reschedule a full-day job - should not ask for time
        """
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-03-09 08:00:00',
            'service_type': 'Brick Work',
            'duration_minutes': 480,  # Full day
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        # First call
        result1 = execute_tool_call(
            'reschedule_job',
            {'current_date': 'Monday March 9th'},
            services
        )
        
        assert 'full day' in result1['message'].lower()
        
        # Complete reschedule - just provide day, no time needed
        result2 = execute_tool_call(
            'reschedule_job',
            {
                'current_date': 'Monday March 9th',
                'customer_name': 'John Smith',
                'new_datetime': 'Friday March 13th'  # No time
            },
            services
        )
        
        assert result2['success'] == True
        assert 'full-day' in result2['message'].lower()


class TestMixedJobsScenarios:
    """Test scenarios with mixed job types"""
    
    def create_mock_services(self, bookings):
        mock_db = Mock()
        mock_db.get_all_bookings.return_value = bookings
        mock_db.get_worker.return_value = None
        mock_db.delete_booking.return_value = True
        mock_db.update_booking.return_value = True
        mock_db.has_workers.return_value = False
        
        mock_calendar = Mock()
        mock_calendar.cancel_appointment.return_value = True
        mock_calendar.reschedule_appointment.return_value = {'id': 'evt1'}
        mock_calendar.check_availability.return_value = True
        
        return {
            'db': mock_db,
            'google_calendar': mock_calendar,
            'company_id': 1
        }
    
    def test_full_day_and_short_jobs_same_day(self):
        """
        Scenario: One full-day job and one short job on same day
        (Different workers would handle these)
        """
        bookings = [
            {
                'id': 1,
                'client_name': 'John Smith',
                'appointment_time': '2026-03-12 08:00:00',
                'service_type': 'Brick Work',
                'duration_minutes': 480,  # Full day
                'status': 'scheduled',
                'calendar_event_id': 'evt1',
                'assigned_worker_ids': [1]
            },
            {
                'id': 2,
                'client_name': 'Jane Doe',
                'appointment_time': '2026-03-12 10:00:00',
                'service_type': 'Consultation',
                'duration_minutes': 30,
                'status': 'scheduled',
                'calendar_event_id': 'evt2',
                'assigned_worker_ids': [2]  # Different worker
            }
        ]
        
        services = self.create_mock_services(bookings)
        
        result = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday March 12th'},
            services
        )
        
        # Should list both with appropriate formatting
        assert len(result['customer_names']) == 2
        assert 'full day' in result['message'].lower()
        assert 'John Smith' in result['message']
        assert 'Jane Doe' in result['message']
    
    def test_same_worker_multiple_short_jobs(self):
        """
        Scenario: Same worker has multiple short jobs on same day
        """
        bookings = [
            {
                'id': 1,
                'client_name': 'John Smith',
                'appointment_time': '2026-03-12 09:00:00',
                'service_type': 'Plumbing',
                'duration_minutes': 60,
                'status': 'scheduled',
                'calendar_event_id': 'evt1',
                'assigned_worker_ids': [1]
            },
            {
                'id': 2,
                'client_name': 'Jane Doe',
                'appointment_time': '2026-03-12 11:00:00',
                'service_type': 'Plumbing',
                'duration_minutes': 60,
                'status': 'scheduled',
                'calendar_event_id': 'evt2',
                'assigned_worker_ids': [1]  # Same worker
            },
            {
                'id': 3,
                'client_name': 'Mike Wilson',
                'appointment_time': '2026-03-12 14:00:00',
                'service_type': 'Plumbing',
                'duration_minutes': 60,
                'status': 'scheduled',
                'calendar_event_id': 'evt3',
                'assigned_worker_ids': [1]  # Same worker
            }
        ]
        
        services = self.create_mock_services(bookings)
        
        result = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday March 12th'},
            services
        )
        
        # Should list all 3 jobs
        assert len(result['customer_names']) == 3
        # Each should show their time
        assert '09:00' in result['message'] or '9:00' in result['message']
        assert '11:00' in result['message']
        assert '2:00' in result['message'] or '14:00' in result['message']


class TestErrorScenarios:
    """Test error handling scenarios"""
    
    def create_mock_services(self, bookings):
        mock_db = Mock()
        mock_db.get_all_bookings.return_value = bookings
        mock_db.get_worker.return_value = None
        mock_db.delete_booking.return_value = True
        mock_db.has_workers.return_value = False
        
        mock_calendar = Mock()
        mock_calendar.cancel_appointment.return_value = True
        
        return {
            'db': mock_db,
            'google_calendar': mock_calendar,
            'company_id': 1
        }
    
    def test_no_bookings_on_day(self):
        """Customer gives a day with no bookings"""
        services = self.create_mock_services([])
        
        result = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Saturday March 14th'},
            services
        )
        
        assert result['success'] == False
        assert 'No bookings found' in result['error']
    
    def test_name_doesnt_match_any_booking(self):
        """Customer gives wrong name"""
        bookings = [{
            'id': 1,
            'client_name': 'John Smith',
            'appointment_time': '2026-03-12 10:00:00',
            'service_type': 'Plumbing',
            'duration_minutes': 60,
            'status': 'scheduled',
            'calendar_event_id': 'evt1',
            'assigned_worker_ids': []
        }]
        
        services = self.create_mock_services(bookings)
        
        result = execute_tool_call(
            'cancel_job',
            {'appointment_date': 'Thursday March 12th', 'customer_name': 'Robert Williams'},
            services
        )
        
        assert result['success'] == False
        assert "couldn't find" in result['error'].lower()
        # Should suggest the actual names
        assert 'John Smith' in result['error']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
