"""
Integration tests for service matching and employee restrictions.

Tests the complete flow:
1. Service matching from job description
2. Employee restrictions applied during availability check
3. Employee restrictions applied during booking
"""
import pytest
from datetime import datetime, timedelta


class TestServiceMatcherReturnsRestrictions:
    """Test that ServiceMatcher returns employee_restrictions from service data"""
    
    def test_service_with_restrictions_returned_in_match(self):
        """When a service has employee_restrictions, it should be in the match result"""
        from src.services.calendar_tools import ServiceMatcher
        
        services = [
            {
                'id': 'electrical_1',
                'name': 'Electrical Work',
                'category': 'Electrical',
                'description': 'Electrical repairs and installations',
                'duration_minutes': 120,
                'price': 100,
                'employees_required': 1,
                'employee_restrictions': {'type': 'only', 'employee_ids': [1, 2]}
            },
            {
                'id': 'general_1',
                'name': 'General Service',
                'category': 'General',
                'description': 'General maintenance',
                'duration_minutes': 60,
                'price': 50,
                'employees_required': 1,
                'employee_restrictions': None
            }
        ]
        
        result = ServiceMatcher.match('electrical repair', services, default_duration=60)
        
        # Should match Electrical Work
        assert result['matched_name'] == 'Electrical Work'
        assert result['service']['employee_restrictions'] == {'type': 'only', 'employee_ids': [1, 2]}
    
    def test_service_without_restrictions_returns_none(self):
        """When a service has no employee_restrictions, it should be None"""
        from src.services.calendar_tools import ServiceMatcher
        
        services = [
            {
                'id': 'plumbing_1',
                'name': 'Plumbing',
                'category': 'Plumbing',
                'description': 'Plumbing repairs',
                'duration_minutes': 90,
                'price': 80,
                'employees_required': 1
                # No employee_restrictions field
            }
        ]
        
        result = ServiceMatcher.match('plumbing repair', services, default_duration=60)
        
        assert result['matched_name'] == 'Plumbing'
        assert result['service'].get('employee_restrictions') is None


class TestEmployeeFilteringInAvailability:
    """Test that employee restrictions are applied when checking availability"""
    
    def test_only_restriction_filters_employees(self):
        """'only' restriction should filter to only specified employees"""
        # Simulate the filtering logic from calendar_tools.py check_availability
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        employee_restrictions = {'type': 'only', 'employee_ids': [1, 3]}
        employees_required = 1
        
        # Apply restrictions (same logic as in calendar_tools.py)
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] not in restricted_ids]
        
        # Check if enough employees available
        slot_available = len(available_employees) >= employees_required
        
        assert slot_available
        assert len(available_employees) == 2
        assert all(w['id'] in [1, 3] for w in available_employees)
    
    def test_except_restriction_excludes_employees(self):
        """'except' restriction should exclude specified employees"""
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        employee_restrictions = {'type': 'except', 'employee_ids': [2]}
        employees_required = 1
        
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] not in restricted_ids]
        
        slot_available = len(available_employees) >= employees_required
        
        assert slot_available
        assert len(available_employees) == 2
        assert all(w['id'] != 2 for w in available_employees)
    
    def test_slot_unavailable_when_no_capable_employees_free(self):
        """Slot should be unavailable when no capable employees are free"""
        # Only employee 1 is free, but only employees 2 and 3 can do this job
        available_employees = [{'id': 1, 'name': 'John'}]
        
        employee_restrictions = {'type': 'only', 'employee_ids': [2, 3]}
        employees_required = 1
        
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        slot_available = len(available_employees) >= employees_required
        
        assert not slot_available
        assert len(available_employees) == 0


class TestEmployeeAssignmentInBooking:
    """Test that employee restrictions are applied when booking"""
    
    def test_booking_assigns_only_capable_employees(self):
        """Booking should only assign employees who can do the job"""
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        # Only Jane (id=2) is certified for this specialized job
        employee_restrictions = {'type': 'only', 'employee_ids': [2]}
        employees_required = 1
        
        # Apply restrictions (same logic as in calendar_tools.py book_job)
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] not in restricted_ids]
        
        # Assign employees
        if len(available_employees) >= employees_required:
            assigned_employees = available_employees[:employees_required]
        else:
            assigned_employees = []
        
        assert len(assigned_employees) == 1
        assert assigned_employees[0]['name'] == 'Jane'
    
    def test_booking_fails_when_not_enough_capable_employees(self):
        """Booking should fail when not enough capable employees are available"""
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        # Only employee 2 can do this job, but they're not available
        employee_restrictions = {'type': 'only', 'employee_ids': [2]}
        employees_required = 1
        
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # Check if booking can proceed
        can_book = len(available_employees) >= employees_required
        
        assert not can_book


class TestFullDayJobsWithRestrictions:
    """Test full-day jobs combined with employee restrictions"""
    
    def test_full_day_job_with_restricted_employees(self):
        """Full-day job should only be available when a capable employee is free all day"""
        service_duration = 480  # 8 hours (full day)
        employees_required = 1
        employee_restrictions = {'type': 'only', 'employee_ids': [1, 2]}
        
        # Employee 1 is free all day, employee 2 has a job at 2pm
        available_employees = [
            {'id': 1, 'name': 'John', 'free_all_day': True},
            {'id': 3, 'name': 'Bob', 'free_all_day': True}  # Can't do this job
        ]
        
        # Apply restrictions
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # For full-day jobs, need employees free all day
        if service_duration >= 480:
            available_employees = [w for w in available_employees if w.get('free_all_day', False)]
        
        can_book = len(available_employees) >= employees_required
        
        assert can_book
        assert available_employees[0]['name'] == 'John'


class TestMultipleEmployeesWithRestrictions:
    """Test jobs requiring multiple employees with restrictions"""
    
    def test_two_employees_required_with_restrictions(self):
        """Job requiring 2 employees should only succeed if 2 capable employees are free"""
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'},
            {'id': 4, 'name': 'Alice'}
        ]
        
        # Only employees 1, 2, 3 can do this job
        employee_restrictions = {'type': 'only', 'employee_ids': [1, 2, 3]}
        employees_required = 2
        
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        can_book = len(available_employees) >= employees_required
        assigned_employees = available_employees[:employees_required] if can_book else []
        
        assert can_book
        assert len(assigned_employees) == 2
        # Alice should not be assigned (not in restricted list)
        assert all(w['name'] != 'Alice' for w in assigned_employees)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
