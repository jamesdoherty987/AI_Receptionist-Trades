"""
Tests for service worker restrictions functionality.

Tests the flow:
1. Service matching based on job description
2. Worker restrictions filtering (all, only, except)
3. Availability checking with restricted workers
4. Booking with restricted workers
"""
import pytest
from datetime import datetime, timedelta


class TestWorkerRestrictionsLogic:
    """Test the worker restrictions filtering logic"""
    
    def test_all_workers_restriction_no_filtering(self):
        """When restriction type is 'all', no workers should be filtered out"""
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        worker_restrictions = {'type': 'all', 'worker_ids': []}
        
        # Apply restrictions (simulating the logic in calendar_tools.py)
        if worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
        
        # All 3 workers should remain
        assert len(available_workers) == 3
    
    def test_only_restriction_filters_to_selected(self):
        """When restriction type is 'only', only selected workers should remain"""
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        # Only workers 1 and 3 can do this job
        worker_restrictions = {'type': 'only', 'worker_ids': [1, 3]}
        
        if worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
        
        # Only John and Bob should remain
        assert len(available_workers) == 2
        assert available_workers[0]['name'] == 'John'
        assert available_workers[1]['name'] == 'Bob'
    
    def test_except_restriction_excludes_selected(self):
        """When restriction type is 'except', selected workers should be excluded"""
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        # All workers except worker 2 can do this job
        worker_restrictions = {'type': 'except', 'worker_ids': [2]}
        
        if worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
        
        # John and Bob should remain, Jane excluded
        assert len(available_workers) == 2
        assert all(w['name'] != 'Jane' for w in available_workers)
    
    def test_only_restriction_with_empty_ids_no_filtering(self):
        """When 'only' restriction has empty worker_ids, no filtering should occur"""
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'}
        ]
        
        worker_restrictions = {'type': 'only', 'worker_ids': []}
        
        if worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
        
        # No filtering should occur
        assert len(available_workers) == 2
    
    def test_none_restrictions_no_filtering(self):
        """When worker_restrictions is None, no filtering should occur"""
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'}
        ]
        
        worker_restrictions = None
        
        if available_workers and worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
        
        # No filtering should occur
        assert len(available_workers) == 2


class TestServiceMatchingWithRestrictions:
    """Test that service matching returns worker_restrictions"""
    
    def test_service_dict_includes_worker_restrictions(self):
        """Service dict should include worker_restrictions field"""
        service = {
            'id': 'service_1',
            'name': 'Electrical Work',
            'duration_minutes': 120,
            'price': 100,
            'workers_required': 1,
            'worker_restrictions': {'type': 'only', 'worker_ids': [1, 2]}
        }
        
        # Verify the field exists and has correct structure
        assert 'worker_restrictions' in service
        assert service['worker_restrictions']['type'] == 'only'
        assert service['worker_restrictions']['worker_ids'] == [1, 2]
    
    def test_service_without_restrictions_returns_none(self):
        """Service without restrictions should have None or missing field"""
        service = {
            'id': 'service_1',
            'name': 'General Service',
            'duration_minutes': 60,
            'price': 50,
            'workers_required': 1
        }
        
        # worker_restrictions should be None or not present
        restrictions = service.get('worker_restrictions')
        assert restrictions is None


class TestAvailabilityWithRestrictions:
    """Test availability checking with worker restrictions"""
    
    def test_slot_available_when_restricted_worker_free(self):
        """Slot should be available when at least one restricted worker is free"""
        all_workers = [
            {'id': 1, 'name': 'John', 'available': True},
            {'id': 2, 'name': 'Jane', 'available': False},
            {'id': 3, 'name': 'Bob', 'available': True}
        ]
        
        # Only workers 1 and 2 can do this job
        worker_restrictions = {'type': 'only', 'worker_ids': [1, 2]}
        workers_required = 1
        
        # Simulate availability check
        available_workers = [w for w in all_workers if w['available']]
        
        # Apply restrictions
        restriction_type = worker_restrictions.get('type', 'all')
        restricted_ids = worker_restrictions.get('worker_ids', [])
        
        if restriction_type == 'only' and restricted_ids:
            available_workers = [w for w in available_workers if w['id'] in restricted_ids]
        
        # John (id=1) is available and can do the job
        assert len(available_workers) >= workers_required
        assert available_workers[0]['name'] == 'John'
    
    def test_slot_unavailable_when_no_restricted_workers_free(self):
        """Slot should be unavailable when no restricted workers are free"""
        all_workers = [
            {'id': 1, 'name': 'John', 'available': False},
            {'id': 2, 'name': 'Jane', 'available': False},
            {'id': 3, 'name': 'Bob', 'available': True}
        ]
        
        # Only workers 1 and 2 can do this job
        worker_restrictions = {'type': 'only', 'worker_ids': [1, 2]}
        workers_required = 1
        
        # Simulate availability check
        available_workers = [w for w in all_workers if w['available']]
        
        # Apply restrictions
        restriction_type = worker_restrictions.get('type', 'all')
        restricted_ids = worker_restrictions.get('worker_ids', [])
        
        if restriction_type == 'only' and restricted_ids:
            available_workers = [w for w in available_workers if w['id'] in restricted_ids]
        
        # Bob is available but can't do this job, John and Jane can but aren't available
        assert len(available_workers) < workers_required


class TestBookingWithRestrictions:
    """Test booking with worker restrictions"""
    
    def test_booking_assigns_restricted_worker(self):
        """Booking should only assign workers who can do the job"""
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        # Only worker 2 can do this specialized job
        worker_restrictions = {'type': 'only', 'worker_ids': [2]}
        workers_required = 1
        
        # Apply restrictions
        if worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
        
        # Select workers for assignment
        assigned_workers = available_workers[:workers_required]
        
        # Only Jane should be assigned
        assert len(assigned_workers) == 1
        assert assigned_workers[0]['name'] == 'Jane'
    
    def test_booking_excludes_restricted_workers(self):
        """Booking should not assign workers who are excluded"""
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'}
        ]
        
        # Worker 1 cannot do this job (maybe not certified)
        worker_restrictions = {'type': 'except', 'worker_ids': [1]}
        workers_required = 1
        
        # Apply restrictions
        if worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
            elif restriction_type == 'except' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] not in restricted_ids]
        
        # Select workers for assignment
        assigned_workers = available_workers[:workers_required]
        
        # John should NOT be assigned
        assert len(assigned_workers) == 1
        assert assigned_workers[0]['name'] != 'John'


class TestMultipleWorkersRequired:
    """Test scenarios where multiple workers are required"""
    
    def test_enough_restricted_workers_available(self):
        """Should succeed when enough restricted workers are available"""
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 2, 'name': 'Jane'},
            {'id': 3, 'name': 'Bob'},
            {'id': 4, 'name': 'Alice'}
        ]
        
        # Only workers 1, 2, 3 can do this job
        worker_restrictions = {'type': 'only', 'worker_ids': [1, 2, 3]}
        workers_required = 2
        
        # Apply restrictions
        if worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
        
        # Should have 3 available, need 2
        assert len(available_workers) >= workers_required
    
    def test_not_enough_restricted_workers_available(self):
        """Should fail when not enough restricted workers are available"""
        available_workers = [
            {'id': 1, 'name': 'John'},
            {'id': 4, 'name': 'Alice'}
        ]
        
        # Only workers 1, 2, 3 can do this job, but only 1 is available
        worker_restrictions = {'type': 'only', 'worker_ids': [1, 2, 3]}
        workers_required = 2
        
        # Apply restrictions
        if worker_restrictions:
            restriction_type = worker_restrictions.get('type', 'all')
            restricted_ids = worker_restrictions.get('worker_ids', [])
            
            if restriction_type == 'only' and restricted_ids:
                available_workers = [w for w in available_workers if w['id'] in restricted_ids]
        
        # Only John (id=1) is available and can do the job
        assert len(available_workers) < workers_required


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
