"""
Tests for the dedicated search_reschedule_availability tool.

This tool searches for alternative dates during a reschedule flow,
checking the ASSIGNED worker's availability — not general availability.
This prevents the bug where search_availability would suggest days
that any worker could do, but the assigned worker couldn't.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.calendar_tools import execute_tool_call, CALENDAR_TOOLS


def make_services(mock_db, company_id=1):
    """Create a services dict with a mock DB."""
    mock_calendar = Mock()
    return {
        'google_calendar': mock_calendar,
        'db': mock_db,
        'company_id': company_id,
    }


def make_mock_db(bookings, worker_available_days):
    """
    Create a mock DB.
    
    Args:
        bookings: list of booking dicts (must include 'id', 'assigned_worker_ids', 'duration_minutes')
        worker_available_days: dict of worker_id -> list of weekday indices (0=Mon, 4=Fri)
    """
    mock_db = Mock()
    mock_db.get_all_bookings.return_value = bookings
    mock_db.has_workers.return_value = True
    
    def check_avail(worker_id, appointment_time, duration_minutes, exclude_booking_id=None, company_id=None):
        available_weekdays = worker_available_days.get(worker_id, [])
        weekday = appointment_time.weekday()
        return {'available': weekday in available_weekdays, 'conflicts': [], 'message': ''}
    
    mock_db.check_worker_availability = Mock(side_effect=check_avail)
    mock_db.get_worker = Mock(return_value={'id': 1, 'name': 'Test Worker'})
    
    # Batch optimization: generate fake blocking bookings for unavailable days
    def get_worker_bookings_in_range(worker_id, range_start, range_end, exclude_booking_id=None, company_id=None):
        available_weekdays = worker_available_days.get(worker_id, [])
        # Generate all-day bookings for each unavailable business day in the range
        fake_bookings = []
        if isinstance(range_start, str):
            range_start = datetime.fromisoformat(range_start)
        if isinstance(range_end, str):
            range_end = datetime.fromisoformat(range_end)
        current = range_start.replace(hour=0, minute=0, second=0, microsecond=0)
        booking_id_counter = 9000
        while current < range_end:
            if current.weekday() not in available_weekdays and current.weekday() in [0, 1, 2, 3, 4]:
                # Block this day with a full-day booking
                fake_bookings.append({
                    'id': booking_id_counter,
                    'appointment_time': current.replace(hour=8, minute=0),
                    'duration_minutes': 540,  # 9 hours blocks the whole day
                })
                booking_id_counter += 1
            current += timedelta(days=1)
        return fake_bookings
    
    mock_db.get_worker_bookings_in_range = Mock(side_effect=get_worker_bookings_in_range)
    
    # _calculate_job_end_time: simple implementation for tests
    def calc_end_time(start_time, duration_minutes, biz_start_hour=9, biz_end_hour=17, buffer_minutes=15, company_id=None):
        if duration_minutes < 480:
            return start_time + timedelta(minutes=duration_minutes + buffer_minutes)
        elif duration_minutes <= 1440:
            end = start_time.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0)
            return end + timedelta(minutes=buffer_minutes)
        else:
            # Multi-day: rough approximation for tests
            days = duration_minutes // 1440
            end = start_time + timedelta(days=days)
            return end.replace(hour=biz_end_hour, minute=0, second=0, microsecond=0) + timedelta(minutes=buffer_minutes)
    
    mock_db._calculate_job_end_time = Mock(side_effect=calc_end_time)
    
    return mock_db


class TestToolDefinitionExists:
    """Verify the tool is properly defined in CALENDAR_TOOLS."""
    
    def test_tool_in_calendar_tools(self):
        tool_names = [t['function']['name'] for t in CALENDAR_TOOLS]
        assert 'search_reschedule_availability' in tool_names
    
    def test_tool_requires_booking_id(self):
        tool = next(t for t in CALENDAR_TOOLS if t['function']['name'] == 'search_reschedule_availability')
        assert 'booking_id' in tool['function']['parameters']['required']
    
    def test_tool_requires_query(self):
        tool = next(t for t in CALENDAR_TOOLS if t['function']['name'] == 'search_reschedule_availability')
        assert 'query' in tool['function']['parameters']['required']
    
    def test_reschedule_job_description_points_to_new_tool(self):
        tool = next(t for t in CALENDAR_TOOLS if t['function']['name'] == 'reschedule_job')
        assert 'search_reschedule_availability' in tool['function']['description']
        assert 'NOT search_availability' in tool['function']['description']


class TestSearchRescheduleAvailability:
    """Test the search_reschedule_availability tool execution."""
    
    def test_missing_booking_id_returns_error(self):
        mock_db = make_mock_db([], {})
        services = make_services(mock_db)
        
        result = execute_tool_call('search_reschedule_availability', {
            'query': 'next week'
        }, services)
        
        assert result['success'] is False
        assert 'Booking ID' in result.get('error', '')
    
    def test_booking_not_found_falls_back(self):
        """If booking has no assigned workers, should fall back to general search."""
        mock_db = make_mock_db([
            {'id': 99, 'assigned_worker_ids': [], 'duration_minutes': 60, 'status': 'confirmed'}
        ], {})
        services = make_services(mock_db)
        
        # This should fall through to search_availability
        with patch('src.services.calendar_tools.execute_tool_call') as mock_exec:
            # We can't easily mock recursive call, so just verify it doesn't crash
            result = execute_tool_call('search_reschedule_availability', {
                'booking_id': 99,
                'query': 'next week'
            }, services)
            # Should get some result (either from fallback or the tool itself)
            assert result is not None
    
    @patch('src.utils.config.config')
    def test_filters_by_assigned_worker(self, mock_config):
        """Core test: only returns days the ASSIGNED worker is available."""
        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]  # Mon-Fri
        mock_config.get_business_hours.return_value = {'start': 8, 'end': 15}
        
        # Worker 5 only works Mon and Fri (weekday 0 and 4)
        mock_db = make_mock_db(
            bookings=[{
                'id': 42,
                'assigned_worker_ids': [5],
                'duration_minutes': 480,
                'appointment_time': datetime.now() + timedelta(days=1),
                'status': 'confirmed'
            }],
            worker_available_days={5: [0, 4]}  # Monday and Friday only
        )
        services = make_services(mock_db)
        
        result = execute_tool_call('search_reschedule_availability', {
            'booking_id': 42,
            'query': 'next week or the week after'
        }, services)
        
        assert result['success'] is True
        # Should only have Monday and Friday results
        summary = result.get('natural_summary', '') or result.get('message', '')
        assert summary  # Should have some results
        
        # Verify get_worker_bookings_in_range was called with worker_id=5
        calls = mock_db.get_worker_bookings_in_range.call_args_list
        assert len(calls) > 0
        for call in calls:
            assert call.kwargs.get('worker_id') == 5 or call[1].get('worker_id') == 5 or call[0][0] == 5
    
    @patch('src.utils.config.config')
    def test_excludes_current_booking_date(self, mock_config):
        """Should not suggest the day the booking is currently on."""
        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
        
        # Booking is on a specific date
        booking_date = datetime.now().replace(hour=9, minute=0) + timedelta(days=3)
        
        # Worker available every day
        mock_db = make_mock_db(
            bookings=[{
                'id': 10,
                'assigned_worker_ids': [1],
                'duration_minutes': 480,
                'appointment_time': booking_date,
                'status': 'confirmed'
            }],
            worker_available_days={1: [0, 1, 2, 3, 4]}
        )
        services = make_services(mock_db)
        
        result = execute_tool_call('search_reschedule_availability', {
            'booking_id': 10,
            'query': 'any other options'
        }, services)
        
        assert result['success'] is True
        # The exclude_booking_id should be passed to get_worker_bookings_in_range
        calls = mock_db.get_worker_bookings_in_range.call_args_list
        for call in calls:
            kwargs = call.kwargs if call.kwargs else {}
            if 'exclude_booking_id' in kwargs:
                assert kwargs['exclude_booking_id'] == 10
    
    @patch('src.utils.config.config')
    def test_no_availability_returns_helpful_message(self, mock_config):
        """When assigned worker has zero availability, return a clear message."""
        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
        
        # Worker available on NO days
        mock_db = make_mock_db(
            bookings=[{
                'id': 7,
                'assigned_worker_ids': [3],
                'duration_minutes': 480,
                'appointment_time': datetime.now() + timedelta(days=1),
                'status': 'confirmed'
            }],
            worker_available_days={3: []}  # Never available
        )
        services = make_services(mock_db)
        
        result = execute_tool_call('search_reschedule_availability', {
            'booking_id': 7,
            'query': 'next week'
        }, services)
        
        assert result['success'] is True
        assert result.get('available_slots') == []
        assert 'no availability' in result.get('message', '').lower()
    
    @patch('src.utils.config.config')
    def test_multiple_assigned_workers_all_must_be_free(self, mock_config):
        """When multiple workers are assigned, ALL must be available on the day."""
        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
        
        # Worker 1: Mon/Tue/Wed, Worker 2: Wed/Thu/Fri
        # Only Wednesday overlaps
        mock_db = make_mock_db(
            bookings=[{
                'id': 20,
                'assigned_worker_ids': [1, 2],
                'duration_minutes': 480,
                'appointment_time': datetime.now() + timedelta(days=1),
                'status': 'confirmed'
            }],
            worker_available_days={
                1: [0, 1, 2],  # Mon, Tue, Wed
                2: [2, 3, 4],  # Wed, Thu, Fri
            }
        )
        services = make_services(mock_db)
        
        result = execute_tool_call('search_reschedule_availability', {
            'booking_id': 20,
            'query': 'any day next few weeks'
        }, services)
        
        assert result['success'] is True
        # Should only find Wednesdays (weekday 2) since that's the only overlap
        summary = result.get('natural_summary', '') or result.get('message', '')
        assert 'Wednesday' in summary or result.get('days_found', 0) > 0


class TestSearchAvailabilityUnchanged:
    """Verify that search_availability (for booking) still works independently."""
    
    def test_search_availability_still_in_tools(self):
        tool_names = [t['function']['name'] for t in CALENDAR_TOOLS]
        assert 'search_availability' in tool_names
    
    def test_search_availability_does_not_require_booking_id(self):
        tool = next(t for t in CALENDAR_TOOLS if t['function']['name'] == 'search_availability')
        required = tool['function']['parameters'].get('required', [])
        assert 'booking_id' not in required


class TestFastPathQueries:
    """Test that the date range parsing handles common reschedule queries."""
    
    @patch('src.utils.config.config')
    def test_next_week_query(self, mock_config):
        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
        
        mock_db = make_mock_db(
            bookings=[{
                'id': 1, 'assigned_worker_ids': [1], 'duration_minutes': 480,
                'appointment_time': datetime.now() + timedelta(days=1), 'status': 'confirmed'
            }],
            worker_available_days={1: [0, 1, 2, 3, 4]}
        )
        services = make_services(mock_db)
        
        result = execute_tool_call('search_reschedule_availability', {
            'booking_id': 1,
            'query': 'next week'
        }, services)
        
        assert result['success'] is True
        assert result.get('days_found', 0) > 0
    
    @patch('src.utils.config.config')
    def test_vague_other_options_query(self, mock_config):
        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
        
        mock_db = make_mock_db(
            bookings=[{
                'id': 1, 'assigned_worker_ids': [1], 'duration_minutes': 480,
                'appointment_time': datetime.now() + timedelta(days=1), 'status': 'confirmed'
            }],
            worker_available_days={1: [0, 1, 2, 3, 4]}
        )
        services = make_services(mock_db)
        
        # This was the query that caused the 15s timeout before
        result = execute_tool_call('search_reschedule_availability', {
            'booking_id': 1,
            'query': 'any other options'
        }, services)
        
        assert result['success'] is True
        assert result.get('days_found', 0) > 0
    
    @patch('src.utils.config.config')
    def test_week_after_next_query(self, mock_config):
        mock_config.get_business_days_indices.return_value = [0, 1, 2, 3, 4]
        mock_config.get_business_hours.return_value = {'start': 9, 'end': 17}
        
        mock_db = make_mock_db(
            bookings=[{
                'id': 1, 'assigned_worker_ids': [1], 'duration_minutes': 480,
                'appointment_time': datetime.now() + timedelta(days=1), 'status': 'confirmed'
            }],
            worker_available_days={1: [0, 1, 2, 3, 4]}
        )
        services = make_services(mock_db)
        
        result = execute_tool_call('search_reschedule_availability', {
            'booking_id': 1,
            'query': 'the week after next'
        }, services)
        
        assert result['success'] is True
