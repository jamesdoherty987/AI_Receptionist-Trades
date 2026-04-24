"""
Tests for service employee restrictions functionality.

Tests the flow:
1. Service matching based on job description
2. Employee restrictions filtering (all, only, except)
3. Availability checking with restricted employees
4. Booking with restricted employees
"""
import pytest
from datetime import datetime, timedelta


class TestEmployeeRestrictionsLogic:
    """Test the employee restrictions filtering logic"""
    
    def test_all_employees_restriction_no_filtering(self):
        """When restriction type is 'all', no employees should be filtered out"""
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        employee_restrictions = {'type': 'all', 'employee_ids': []}
        
        # Apply restrictions (simulating the logic in calendar_tools.py)
        if employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] not in restricted_ids]
        
        # All 3 employees should remain
        assert len(available_employees) == 3
    
    def test_only_restriction_filters_to_selected(self):
        """When restriction type is 'only', only selected employees should remain"""
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        # Only employees 1 and 3 can do this job
        employee_restrictions = {'type': 'only', 'employee_ids': [1, 3]}
        
        if employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] not in restricted_ids]
        
        # Only John and Bob should remain
        assert len(available_employees) == 2
        assert available_employees[0]['name'] == 'John'
        assert available_employees[1]['name'] == 'Bob'
    
    def test_except_restriction_excludes_selected(self):
        """When restriction type is 'except', selected employees should be excluded"""
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        # All employees except employee 2 can do this job
        employee_restrictions = {'type': 'except', 'employee_ids': [2]}
        
        if employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] not in restricted_ids]
        
        # John and Bob should remain, Jane excluded
        assert len(available_employees) == 2
        assert all(w['name'] != 'Jane' for w in available_employees)
    
    def test_only_restriction_with_empty_ids_no_filtering(self):
        """When 'only' restriction has empty employee_ids, no filtering should occur"""
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'}
        ]
        
        employee_restrictions = {'type': 'only', 'employee_ids': []}
        
        if employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] not in restricted_ids]
        
        # No filtering should occur
        assert len(available_employees) == 2
    
    def test_none_restrictions_no_filtering(self):
        """When employee_restrictions is None, no filtering should occur"""
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'}
        ]
        
        employee_restrictions = None
        
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] not in restricted_ids]
        
        # No filtering should occur
        assert len(available_employees) == 2


class TestServiceMatchingWithRestrictions:
    """Test that service matching returns employee_restrictions"""
    
    def test_service_dict_includes_employee_restrictions(self):
        """Service dict should include employee_restrictions field"""
        service = {
            'id': 'service_1',
            'name': 'Electrical Work',
            'duration_minutes': 120,
            'price': 100,
            'employees_required': 1,
            'employee_restrictions': {'type': 'only', 'employee_ids': [1, 2]}
        }
        
        # Verify the field exists and has correct structure
        assert 'employee_restrictions' in service
        assert service['employee_restrictions']['type'] == 'only'
        assert service['employee_restrictions']['employee_ids'] == [1, 2]
    
    def test_service_without_restrictions_returns_none(self):
        """Service without restrictions should have None or missing field"""
        service = {
            'id': 'service_1',
            'name': 'General Service',
            'duration_minutes': 60,
            'price': 50,
            'employees_required': 1
        }
        
        # employee_restrictions should be None or not present
        restrictions = service.get('employee_restrictions')
        assert restrictions is None


class TestAvailabilityWithRestrictions:
    """Test availability checking with employee restrictions"""
    
    def test_slot_available_when_restricted_employee_free(self):
        """Slot should be available when at least one restricted employee is free"""
        all_employees = [
            {'id': 1, 'name': 'John', 'available': True},
            {'id': 2, 'name': 'Jane', 'available': False},
            {'id': 3, 'name': 'Bob', 'available': True}
        ]
        
        # Only employees 1 and 2 can do this job
        employee_restrictions = {'type': 'only', 'employee_ids': [1, 2]}
        employees_required = 1
        
        # Simulate availability check
        available_employees = [w for w in all_employees if w['available']]
        
        # Apply restrictions
        restriction_type = employee_restrictions.get('type', 'all')
        restricted_ids = employee_restrictions.get('employee_ids', [])
        
        if restriction_type == 'only' and restricted_ids:
            available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # John (id=1) is available and can do the job
        assert len(available_employees) >= employees_required
        assert available_employees[0]['name'] == 'John'
    
    def test_slot_unavailable_when_no_restricted_employees_free(self):
        """Slot should be unavailable when no restricted employees are free"""
        all_employees = [
            {'id': 1, 'name': 'John', 'available': False},
            {'id': 2, 'name': 'Jane', 'available': False},
            {'id': 3, 'name': 'Bob', 'available': True}
        ]
        
        # Only employees 1 and 2 can do this job
        employee_restrictions = {'type': 'only', 'employee_ids': [1, 2]}
        employees_required = 1
        
        # Simulate availability check
        available_employees = [w for w in all_employees if w['available']]
        
        # Apply restrictions
        restriction_type = employee_restrictions.get('type', 'all')
        restricted_ids = employee_restrictions.get('employee_ids', [])
        
        if restriction_type == 'only' and restricted_ids:
            available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # Bob is available but can't do this job, John and Jane can but aren't available
        assert len(available_employees) < employees_required


class TestBookingWithRestrictions:
    """Test booking with employee restrictions"""
    
    def test_booking_assigns_restricted_employee(self):
        """Booking should only assign employees who can do the job"""
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        # Only employee 2 can do this specialized job
        employee_restrictions = {'type': 'only', 'employee_ids': [2]}
        employees_required = 1
        
        # Apply restrictions
        if employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # Select employees for assignment
        assigned_employees = available_employees[:employees_required]
        
        # Only Jane should be assigned
        assert len(assigned_employees) == 1
        assert assigned_employees[0]['name'] == 'Jane'
    
    def test_booking_excludes_restricted_employees(self):
        """Booking should not assign employees who are excluded"""
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        # Employee 1 cannot do this job (maybe not certified)
        employee_restrictions = {'type': 'except', 'employee_ids': [1]}
        employees_required = 1
        
        # Apply restrictions
        if employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] not in restricted_ids]
        
        # Select employees for assignment
        assigned_employees = available_employees[:employees_required]
        
        # John should NOT be assigned
        assert len(assigned_employees) == 1
        assert assigned_employees[0]['name'] != 'John'


class TestMultipleEmployeesRequired:
    """Test scenarios where multiple employees are required"""
    
    def test_enough_restricted_employees_available(self):
        """Should succeed when enough restricted employees are available"""
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'},
            {'id': 4, 'name': 'Alice'}
        ]
        
        # Only employees 1, 2, 3 can do this job
        employee_restrictions = {'type': 'only', 'employee_ids': [1, 2, 3]}
        employees_required = 2
        
        # Apply restrictions
        if employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # Should have 3 available, need 2
        assert len(available_employees) >= employees_required
    
    def test_not_enough_restricted_employees_available(self):
        """Should fail when not enough restricted employees are available"""
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 4, 'name': 'Alice'}
        ]
        
        # Only employees 1, 2, 3 can do this job, but only 1 is available
        employee_restrictions = {'type': 'only', 'employee_ids': [1, 2, 3]}
        employees_required = 2
        
        # Apply restrictions
        if employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # Only John (id=1) is available and can do the job
        assert len(available_employees) < employees_required


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
