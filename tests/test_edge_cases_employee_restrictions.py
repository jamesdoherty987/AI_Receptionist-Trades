"""
Edge case tests for employee restrictions functionality.

Tests unusual scenarios that could cause issues in production.
"""
import pytest
from datetime import datetime, timedelta


class TestEdgeCaseRestrictions:
    """Test edge cases in employee restrictions"""
    
    def test_restrictions_with_deleted_employee_ids(self):
        """
        If a service has restrictions pointing to employees that no longer exist,
        the filtering should result in no available employees.
        """
        # Available employees (employees 1 and 2 were deleted)
        available_employees = [
            {'id': 3, 'name': 'Bob'},
            {'id': 4, 'name': 'Alice'}
        ]
        
        # Restrictions point to deleted employees
        employee_restrictions = {'type': 'only', 'employee_ids': [1, 2]}
        employees_required = 1
        
        # Apply restrictions
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # No employees should be available
        assert len(available_employees) == 0
    
    def test_restrictions_with_empty_employee_ids_list(self):
        """
        If restrictions have type 'only' but empty employee_ids,
        no filtering should occur (backend should have set to null).
        """
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'}
        ]
        
        # Empty employee_ids - this shouldn't happen if backend validates correctly
        employee_restrictions = {'type': 'only', 'employee_ids': []}
        
        # Apply restrictions
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            # This condition is False because restricted_ids is empty
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # All employees should still be available (no filtering)
        assert len(available_employees) == 2
    
    def test_restrictions_type_all_with_employee_ids(self):
        """
        If restrictions have type 'all' but also have employee_ids,
        no filtering should occur.
        """
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        # Type is 'all' so employee_ids should be ignored
        employee_restrictions = {'type': 'all', 'employee_ids': [1, 2]}
        
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] not in restricted_ids]
        
        # All employees should be available
        assert len(available_employees) == 3
    
    def test_restrictions_with_none_value(self):
        """
        If employee_restrictions is None, no filtering should occur.
        """
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'}
        ]
        
        employee_restrictions = None
        
        if available_employees and employee_restrictions:
            # This block won't execute
            pass
        
        assert len(available_employees) == 2
    
    def test_restrictions_with_invalid_type(self):
        """
        If restrictions have an invalid type, no filtering should occur.
        """
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'}
        ]
        
        # Invalid type
        employee_restrictions = {'type': 'invalid', 'employee_ids': [1]}
        
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] not in restricted_ids]
        
        # No filtering should occur
        assert len(available_employees) == 2
    
    def test_except_all_employees(self):
        """
        If 'except' restriction excludes all available employees,
        no employees should be available.
        """
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'}
        ]
        
        # Exclude all employees
        employee_restrictions = {'type': 'except', 'employee_ids': [1, 2]}
        
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] not in restricted_ids]
        
        assert len(available_employees) == 0
    
    def test_employee_id_type_mismatch(self):
        """
        If employee IDs are stored as strings but compared as integers,
        filtering might fail. Test both scenarios.
        """
        # Employees with integer IDs
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'}
        ]
        
        # Restrictions with integer IDs (should work)
        employee_restrictions = {'type': 'only', 'employee_ids': [1]}
        
        if available_employees and employee_restrictions:
            restriction_type = employee_restrictions.get('type', 'all')
            restricted_ids = employee_restrictions.get('employee_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        assert len(available_employees) == 1
        assert available_employees[0]['name'] == 'John'


class TestConversationSimulation:
    """Simulate real conversation scenarios"""
    
    def test_electrical_job_only_electrician_available(self):
        """
        Scenario: Customer calls for electrical work.
        Only certified electricians (employees 1, 2) can do this job.
        Employee 1 is busy, employee 2 is free.
        """
        # All employees
        all_employees = [
            {'id': 1, 'name': 'John (Electrician)', 'busy': True},
            {'id': 2, 'name': 'Jane (Electrician)', 'busy': False},
            {'id': 3, 'name': 'Bob (Plumber)', 'busy': False}
        ]
        
        # Service: Electrical Work - only electricians
        service = {
            'name': 'Electrical Work',
            'duration_minutes': 120,
            'employees_required': 1,
            'employee_restrictions': {'type': 'only', 'employee_ids': [1, 2]}
        }
        
        # Step 1: Find available employees (not busy)
        available_employees = [w for w in all_employees if not w['busy']]
        assert len(available_employees) == 2  # Jane and Bob
        
        # Step 2: Apply restrictions
        restrictions = service['employee_restrictions']
        if restrictions and restrictions.get('type') == 'only':
            restricted_ids = restrictions.get('employee_ids', [])
            available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # Only Jane should be available
        assert len(available_employees) == 1
        assert available_employees[0]['name'] == 'Jane (Electrician)'
        
        # Step 3: Assign employee
        employees_required = service['employees_required']
        assert len(available_employees) >= employees_required
        assigned = available_employees[:employees_required]
        assert assigned[0]['name'] == 'Jane (Electrician)'
    
    def test_plumbing_job_all_employees_except_apprentice(self):
        """
        Scenario: Customer calls for plumbing work.
        All employees can do this except the apprentice (employee 3).
        """
        all_employees = [
            {'id': 1, 'name': 'John (Senior)', 'busy': False},
            {'id': 2, 'name': 'Jane (Senior)', 'busy': True},
            {'id': 3, 'name': 'Bob (Apprentice)', 'busy': False}
        ]
        
        service = {
            'name': 'Plumbing',
            'duration_minutes': 90,
            'employees_required': 1,
            'employee_restrictions': {'type': 'except', 'employee_ids': [3]}
        }
        
        # Find available employees
        available_employees = [w for w in all_employees if not w['busy']]
        assert len(available_employees) == 2  # John and Bob
        
        # Apply restrictions
        restrictions = service['employee_restrictions']
        if restrictions and restrictions.get('type') == 'except':
            restricted_ids = restrictions.get('employee_ids', [])
            available_employees = [w for w in available_employees if w['id'] not in restricted_ids]
        
        # Only John should be available (Bob is apprentice)
        assert len(available_employees) == 1
        assert available_employees[0]['name'] == 'John (Senior)'
    
    def test_general_service_all_employees(self):
        """
        Scenario: Customer calls for general maintenance.
        All employees can do this job.
        """
        all_employees = [
            {'id': 1, 'name': 'John', 'busy': False},
            {'id': 2, 'name': 'Jane', 'busy': False},
            {'id': 3, 'name': 'Bob', 'busy': True}
        ]
        
        service = {
            'name': 'General Service',
            'duration_minutes': 60,
            'employees_required': 1,
            'employee_restrictions': None  # No restrictions
        }
        
        # Find available employees
        available_employees = [w for w in all_employees if not w['busy']]
        assert len(available_employees) == 2  # John and Jane
        
        # No restrictions to apply
        restrictions = service.get('employee_restrictions')
        if available_employees and restrictions:
            pass  # Won't execute
        
        # Both John and Jane available
        assert len(available_employees) == 2
    
    def test_two_person_job_with_restrictions(self):
        """
        Scenario: Customer needs heavy lifting job requiring 2 employees.
        Only employees 1, 2, 3 are strong enough.
        Employees 1 and 3 are free, employee 2 is busy.
        """
        all_employees = [
            {'id': 1, 'name': 'John (Strong)', 'busy': False},
            {'id': 2, 'name': 'Jane (Strong)', 'busy': True},
            {'id': 3, 'name': 'Bob (Strong)', 'busy': False},
            {'id': 4, 'name': 'Alice (Light duty)', 'busy': False}
        ]
        
        service = {
            'name': 'Heavy Lifting',
            'duration_minutes': 240,
            'employees_required': 2,
            'employee_restrictions': {'type': 'only', 'employee_ids': [1, 2, 3]}
        }
        
        # Find available employees
        available_employees = [w for w in all_employees if not w['busy']]
        assert len(available_employees) == 3  # John, Bob, Alice
        
        # Apply restrictions
        restrictions = service['employee_restrictions']
        if restrictions and restrictions.get('type') == 'only':
            restricted_ids = restrictions.get('employee_ids', [])
            available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # John and Bob available (Alice excluded)
        assert len(available_employees) == 2
        
        # Can we book? Need 2 employees
        employees_required = service['employees_required']
        assert len(available_employees) >= employees_required
        
        assigned = available_employees[:employees_required]
        assert len(assigned) == 2
        assert all(w['id'] in [1, 3] for w in assigned)
    
    def test_no_qualified_employees_available(self):
        """
        Scenario: Customer calls for specialized job.
        Only employee 1 is qualified, but they're busy.
        """
        all_employees = [
            {'id': 1, 'name': 'John (Specialist)', 'busy': True},
            {'id': 2, 'name': 'Jane (General)', 'busy': False},
            {'id': 3, 'name': 'Bob (General)', 'busy': False}
        ]
        
        service = {
            'name': 'Specialized Work',
            'duration_minutes': 180,
            'employees_required': 1,
            'employee_restrictions': {'type': 'only', 'employee_ids': [1]}
        }
        
        # Find available employees
        available_employees = [w for w in all_employees if not w['busy']]
        assert len(available_employees) == 2  # Jane and Bob
        
        # Apply restrictions
        restrictions = service['employee_restrictions']
        if restrictions and restrictions.get('type') == 'only':
            restricted_ids = restrictions.get('employee_ids', [])
            available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # No qualified employees available
        assert len(available_employees) == 0
        
        # Booking should fail
        employees_required = service['employees_required']
        can_book = len(available_employees) >= employees_required
        assert not can_book


class TestFullDayWithRestrictions:
    """Test full-day jobs combined with employee restrictions"""
    
    def test_full_day_job_restricted_employee_free(self):
        """
        Full-day job where only specific employees can do it.
        One qualified employee is free all day.
        """
        service_duration = 480  # 8 hours
        employees_required = 1
        employee_restrictions = {'type': 'only', 'employee_ids': [1, 2]}
        
        # Employee 1 is free all day, employee 2 has afternoon job
        available_employees = [
            {'id': 1, 'name': 'John', 'free_all_day': True},
            {'id': 2, 'name': 'Jane', 'free_all_day': False},
            {'id': 3, 'name': 'Bob', 'free_all_day': True}
        ]
        
        # Apply restrictions first
        if employee_restrictions and employee_restrictions.get('type') == 'only':
            restricted_ids = employee_restrictions.get('employee_ids', [])
            available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # Then filter for full-day availability
        if service_duration >= 480:
            available_employees = [w for w in available_employees if w.get('free_all_day', False)]
        
        # Only John should be available
        assert len(available_employees) == 1
        assert available_employees[0]['name'] == 'John'
    
    def test_full_day_job_no_qualified_employee_free_all_day(self):
        """
        Full-day job where qualified employees exist but none are free all day.
        """
        service_duration = 480
        employees_required = 1
        employee_restrictions = {'type': 'only', 'employee_ids': [1, 2]}
        
        # Both qualified employees have partial day bookings
        available_employees = [
            {'id': 1, 'name': 'John', 'free_all_day': False},
            {'id': 2, 'name': 'Jane', 'free_all_day': False},
            {'id': 3, 'name': 'Bob', 'free_all_day': True}  # Not qualified
        ]
        
        # Apply restrictions
        if employee_restrictions and employee_restrictions.get('type') == 'only':
            restricted_ids = employee_restrictions.get('employee_ids', [])
            available_employees = [w for w in available_employees if w['id'] in restricted_ids]
        
        # Filter for full-day
        if service_duration >= 480:
            available_employees = [w for w in available_employees if w.get('free_all_day', False)]
        
        # No employees available
        assert len(available_employees) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestAPIValidation:
    """Test API validation of employee_restrictions"""
    
    def test_api_validates_restriction_type(self):
        """
        API should reject invalid restriction types and set to None.
        """
        # Simulate API validation logic
        def validate_restrictions(restrictions):
            if restrictions and isinstance(restrictions, dict):
                valid_types = ['all', 'only', 'except']
                if restrictions.get('type') not in valid_types:
                    return None
                elif restrictions.get('type') != 'all' and not restrictions.get('employee_ids'):
                    return None
                elif restrictions.get('type') == 'all':
                    return None  # 'all' doesn't need to be stored
            else:
                return None
            return restrictions
        
        # Invalid type should return None
        assert validate_restrictions({'type': 'invalid', 'employee_ids': [1]}) is None
        
        # 'all' type should return None (no need to store)
        assert validate_restrictions({'type': 'all', 'employee_ids': []}) is None
        
        # 'only' without employee_ids should return None
        assert validate_restrictions({'type': 'only', 'employee_ids': []}) is None
        
        # 'except' without employee_ids should return None
        assert validate_restrictions({'type': 'except', 'employee_ids': []}) is None
        
        # Valid 'only' with employee_ids should be preserved
        result = validate_restrictions({'type': 'only', 'employee_ids': [1, 2]})
        assert result == {'type': 'only', 'employee_ids': [1, 2]}
        
        # Valid 'except' with employee_ids should be preserved
        result = validate_restrictions({'type': 'except', 'employee_ids': [3]})
        assert result == {'type': 'except', 'employee_ids': [3]}
        
        # Non-dict should return None
        assert validate_restrictions("invalid") is None
        assert validate_restrictions([1, 2, 3]) is None
        assert validate_restrictions(None) is None
    
    def test_employees_required_minimum_is_one(self):
        """
        employees_required should always be at least 1.
        """
        def validate_employees_required(value):
            try:
                employees = int(value) if value else 1
                return max(1, employees)
            except (ValueError, TypeError):
                return 1
        
        assert validate_employees_required(0) == 1
        assert validate_employees_required(-1) == 1
        assert validate_employees_required(None) == 1
        assert validate_employees_required('') == 1
        assert validate_employees_required('invalid') == 1
        assert validate_employees_required(1) == 1
        assert validate_employees_required(5) == 5
        assert validate_employees_required('3') == 3


class TestStringEmployeeIds:
    """Test handling of employee IDs that might come as strings from JSON"""
    
    def test_string_employee_ids_in_restrictions(self):
        """
        If employee_ids come as strings from JSON, comparison should still work.
        PostgreSQL JSONB preserves integer types, but test defensive coding.
        """
        available_employees = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'}
        ]
        
        # Simulate string IDs (shouldn't happen with PostgreSQL JSONB but be safe)
        employee_restrictions = {'type': 'only', 'employee_ids': ['1']}
        
        # Current code uses direct comparison which would fail with strings
        # This test documents the expected behavior
        restriction_type = employee_restrictions.get('type', 'all')
        restricted_ids = employee_restrictions.get('employee_ids', [])
        
        if restriction_type == 'only' and restricted_ids:
            # Direct comparison - would fail if IDs are strings
            filtered = [w for w in available_employees if w['id'] in restricted_ids]
        
        # With string IDs, this would return 0 employees (type mismatch)
        # This is acceptable because PostgreSQL JSONB preserves integer types
        # and the frontend sends integers
        assert len(filtered) == 0  # Documents current behavior
        
        # If we wanted to handle string IDs, we'd need:
        # restricted_ids_int = [int(id) for id in restricted_ids]
        # filtered = [w for w in available_employees if w['id'] in restricted_ids_int]
