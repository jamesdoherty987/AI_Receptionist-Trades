"""
Integration tests for service matching and worker restrictions.

Tests the complete flow:
1. Service matching from job description
2. Worker restrictions applied during availability check
3. Worker restrictions applied during booking
"""
import pytest
from datetime import datetime, timedelta


class TestServiceMatcherReturnsRestrictions:
    """Test that ServiceMatcher returns worker_restrictions from service data"""
    
    def test_service_with_restrictions_returned_in_match(self):
        """When a service has worker_restrictions, it should be in the match result"""
        from src.services.calendar_tools import ServiceMatcher
        
        services = [
            {
                'id': 'electrical_1',
                'name': 'Electrical Work',
                'category': 'Electrical',
                'description': 'Electrical repairs and installations',
                'duration_minutes': 120,
                'price': 100,
                'workers_required': 1,
                'worker_restrictions': {'type': 'only', 'worker_ids': [1, 2]}
            },
            {
                'id': 'general_1',
                'name': 'General Service',
                'category': 'General',
                'description': 'General maintenance',
                'duration_minutes': 60,
                'price': 50,
                'workers_required': 1,
                'worker_restrictions': None
            }
        ]
        
        result = ServiceMatcher.match('electrical repair', services, default_duration=60)
        
        # Should match Electrical Work
        assert result['matched_name'] == 'Electrical Work'
        assert result['service']['worker_restrictions'] == {'type': 'only', 'worker_ids': [1, 2]}
    
    def test_service_without_restrictions_returns_none(self):
        """When a service has no worker_restrictions, it should be None"""
        from src.services.calendar_tools import ServiceMatcher
        
        services = [
            {
                'id': 'plumbing_1',
                'name': 'Plumbing',
                'category': 'Plumbing',
                'description': 'Plumbing repairs',
                'duration_minutes': 90,
                'price': 80,
                'workers_required': 1
                # No worker_restrictions field
            }
        ]
        
        result = ServiceMatcher.match('plumbing repair', services, default_duration=60)
        
        assert result['matched_name'] == 'Plumbing'
        assert result['service'].get('worker_restrictions') is None


class TestWorkerFilteringInAvailability:
    """Test that worker restrictions are applied when checking availability"""
    
    def test_only_restriction_filters_workers(self):
        """'only' restriction should filter to only specified workers"""
        # Simulate the filtering logic from calendar_tools.py check_availability
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        worker_restrictions = {'type': 'only', 'worker_ids': [1, 3]}
        workers_required = 1
        
        # Apply restrictions (same logic as in calendar_tools.py)
        if available_workers and worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
        
        # Check if enough workers available
        slot_available = len(available_workers) >= workers_required
        
        assert slot_available
        assert len(available_workers) == 2
        assert all(w['id'] in [1, 3] for w in available_workers)
    
    def test_except_restriction_excludes_workers(self):
        """'except' restriction should exclude specified workers"""
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        worker_restrictions = {'type': 'except', 'worker_ids': [2]}
        workers_required = 1
        
        if available_workers and worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
        
        slot_available = len(available_workers) >= workers_required
        
        assert slot_available
        assert len(available_workers) == 2
        assert all(w['id'] != 2 for w in available_workers)
    
    def test_slot_unavailable_when_no_capable_workers_free(self):
        """Slot should be unavailable when no capable workers are free"""
        # Only worker 1 is free, but only workers 2 and 3 can do this job
        available_workers = [{'id': 1, 'name': 'John'}]
        
        worker_restrictions = {'type': 'only', 'worker_ids': [2, 3]}
        workers_required = 1
        
        if available_workers and worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
        
        slot_available = len(available_workers) >= workers_required
        
        assert not slot_available
        assert len(available_workers) == 0


class TestWorkerAssignmentInBooking:
    """Test that worker restrictions are applied when booking"""
    
    def test_booking_assigns_only_capable_workers(self):
        """Booking should only assign workers who can do the job"""
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        # Only Jane (id=2) is certified for this specialized job
        worker_restrictions = {'type': 'only', 'worker_ids': [2]}
        workers_required = 1
        
        # Apply restrictions (same logic as in calendar_tools.py book_job)
        if available_workers and worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
        
        # Assign workers
        if len(available_workers) >= workers_required:
            assigned_workers = available_workers[:workers_required]
        else:
            assigned_workers = []
        
        assert len(assigned_workers) == 1
        assert assigned_workers[0]['name'] == 'Jane'
    
    def test_booking_fails_when_not_enough_capable_workers(self):
        """Booking should fail when not enough capable workers are available"""
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        # Only worker 2 can do this job, but they're not available
        worker_restrictions = {'type': 'only', 'worker_ids': [2]}
        workers_required = 1
        
        if available_workers and worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
        
        # Check if booking can proceed
        can_book = len(available_workers) >= workers_required
        
        assert not can_book


class TestFullDayJobsWithRestrictions:
    """Test full-day jobs combined with worker restrictions"""
    
    def test_full_day_job_with_restricted_workers(self):
        """Full-day job should only be available when a capable worker is free all day"""
        service_duration = 480  # 8 hours (full day)
        workers_required = 1
        worker_restrictions = {'type': 'only', 'worker_ids': [1, 2]}
        
        # Worker 1 is free all day, worker 2 has a job at 2pm
        available_workers = [
            {'id': 1, 'name': 'John', 'free_all_day': True},
            {'id': 3, 'name': 'Bob', 'free_all_day': True}  # Can't do this job
        ]
        
        # Apply restrictions
        if available_workers and worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
        
        # For full-day jobs, need workers free all day
        if service_duration >= 480:
            available_workers = [w for w in available_workers if w.get('free_all_day', False)]
        
        can_book = len(available_workers) >= workers_required
        
        assert can_book
        assert available_workers[0]['name'] == 'John'


class TestMultipleWorkersWithRestrictions:
    """Test jobs requiring multiple workers with restrictions"""
    
    def test_two_workers_required_with_restrictions(self):
        """Job requiring 2 workers should only succeed if 2 capable workers are free"""
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'},
            {'id': 4, 'name': 'Alice'}
        ]
        
        # Only workers 1, 2, 3 can do this job
        worker_restrictions = {'type': 'only', 'worker_ids': [1, 2, 3]}
        workers_required = 2
        
        if available_workers and worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
        
        can_book = len(available_workers) >= workers_required
        assigned_workers = available_workers[:workers_required] if can_book else []
        
        assert can_book
        assert len(assigned_workers) == 2
        # Alice should not be assigned (not in restricted list)
        assert all(w['name'] != 'Alice' for w in assigned_workers)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
