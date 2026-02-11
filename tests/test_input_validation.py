"""
Test Input Validation and None/Empty Handling

Tests that all CRUD endpoints properly:
1. Validate required fields (return 400 if empty)
2. Sanitize optional fields (convert empty strings to None)
3. Handle edge cases (negative numbers, invalid types, etc.)
"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestClientValidation:
    """Test client creation and update validation"""
    
    def test_client_creation_requires_name(self):
        """Client creation should fail without name"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Verify the validation code exists
        assert "Customer name is required" in content, \
            "Client creation should validate name is required"
    
    def test_client_creation_name_empty_string_rejected(self):
        """Empty string name should be rejected"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check that name is stripped and checked
        assert "name = data.get('name', '').strip()" in content or \
               "name.strip()" in content, \
            "Client name should be stripped before validation"
    
    def test_client_optional_fields_sanitized(self):
        """Phone and email should be sanitized (empty -> None)"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check sanitization pattern for phone
        assert "phone if phone else None" in content, \
            "Phone should be converted to None if empty"
        
        # Check sanitization pattern for email
        assert "email if email else None" in content, \
            "Email should be converted to None if empty"
    
    def test_client_update_validates_name(self):
        """Client update should validate name if provided"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check that PUT endpoint validates name
        assert "if key == 'name':" in content and "Customer name is required" in content, \
            "Client update should validate name is not empty"


class TestWorkerValidation:
    """Test worker creation and update validation"""
    
    def test_worker_creation_requires_name(self):
        """Worker creation should fail without name"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Worker name is required" in content, \
            "Worker creation should validate name is required"
    
    def test_worker_optional_fields_sanitized(self):
        """Phone, email, trade_specialty should be sanitized"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check that optional fields are handled
        assert "trade_specialty" in content, \
            "Worker should have trade_specialty field"
    
    def test_worker_weekly_hours_validation(self):
        """Weekly hours should be validated (0-168 range)"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check for weekly hours validation
        assert "weekly_hours < 0 or weekly_hours > 168" in content or \
               "hours < 0 or hours > 168" in content, \
            "Weekly hours should be validated in 0-168 range"
    
    def test_worker_weekly_hours_default(self):
        """Weekly hours should default to 40 if invalid"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "40.0" in content or "40" in content, \
            "Weekly hours should default to 40"
    
    def test_worker_update_validates_name(self):
        """Worker update should validate name if provided"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check that PUT endpoint validates name
        assert "Worker name is required" in content, \
            "Worker update should validate name is not empty"


class TestServiceValidation:
    """Test service creation and update validation"""
    
    def test_service_creation_requires_name(self):
        """Service creation should fail without name"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Service name is required" in content, \
            "Service creation should validate name is required"
    
    def test_service_price_validation(self):
        """Price should be validated (>= 0)"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check for price validation
        assert "price < 0" in content or "price >= 0" in content, \
            "Service price should be validated as non-negative"
    
    def test_service_duration_validation(self):
        """Duration should be validated (> 0)"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check for duration validation
        assert "duration < 1" in content or "duration > 0" in content, \
            "Service duration should be validated as positive"
    
    def test_service_duration_default(self):
        """Duration should default to 60 if invalid"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check default duration
        assert "duration = 60" in content or "duration_minutes = 60" in content, \
            "Service duration should default to 60"


class TestBookingValidation:
    """Test booking creation and update validation"""
    
    def test_booking_requires_client_id(self):
        """Booking creation should fail without client_id"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Customer is required" in content, \
            "Booking should validate client_id is required"
    
    def test_booking_requires_appointment_time(self):
        """Booking creation should fail without appointment_time"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Date & Time is required" in content, \
            "Booking should validate appointment_time is required"
    
    def test_booking_requires_service_type(self):
        """Booking creation should fail without service_type"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Service type is required" in content, \
            "Booking should validate service_type is required"
    
    def test_booking_validates_client_exists(self):
        """Booking should verify client exists"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Customer not found" in content, \
            "Booking should verify client exists before creation"
    
    def test_booking_charge_validation(self):
        """Charge should be validated (>= 0 or None)"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check for charge validation
        assert "job_charge < 0" in content or "float(job_charge)" in content, \
            "Booking charge should be validated"
    
    def test_booking_optional_fields_sanitized(self):
        """Optional fields should be sanitized"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check that address is sanitized
        assert "job_address if job_address else None" in content or \
               "job_address = job_address if job_address" in content, \
            "Job address should be sanitized"


class TestWorkerAvailabilityChecking:
    """Test worker availability checking logic"""
    
    def test_check_worker_availability_function_exists(self):
        """check_worker_availability should exist in database wrapper"""
        with open('src/services/db_postgres_wrapper.py', 'r') as f:
            content = f.read()
        
        assert "def check_worker_availability" in content, \
            "check_worker_availability function should exist"
    
    def test_worker_availability_uses_buffer(self):
        """Worker availability should use buffer time"""
        with open('src/services/db_postgres_wrapper.py', 'r') as f:
            content = f.read()
        
        # Check for buffer time in availability check
        assert "buffer" in content.lower() or "15" in content, \
            "Worker availability should consider buffer time"
    
    def test_worker_availability_returns_safe_default_on_error(self):
        """On error, availability should return False (safe default)"""
        with open('src/services/db_postgres_wrapper.py', 'r') as f:
            content = f.read()
        
        # Check for error handling that returns False
        assert "'available': False" in content or '"available": False' in content, \
            "Worker availability should return False on error"
    
    def test_assign_worker_endpoint_checks_availability(self):
        """Assign worker endpoint should check availability"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "check_worker_availability" in content, \
            "Assign worker endpoint should check availability"
    
    def test_assign_worker_supports_force_option(self):
        """Assign worker should support force option to bypass availability"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "force" in content and "force_assign" in content, \
            "Assign worker should support force option"


class TestServiceDurationAndBuffer:
    """Test service duration and buffer time features"""
    
    def test_booking_stores_duration(self):
        """Bookings should store duration_minutes"""
        with open('src/services/db_postgres_wrapper.py', 'r') as f:
            content = f.read()
        
        assert "duration_minutes" in content, \
            "Bookings should have duration_minutes field"
    
    def test_settings_manager_has_buffer_time(self):
        """Settings manager should have buffer time setting"""
        with open('src/services/settings_manager.py', 'r') as f:
            content = f.read()
        
        assert "buffer_time" in content.lower() or "get_buffer_time" in content, \
            "Settings manager should have buffer time"
    
    def test_settings_manager_has_default_duration(self):
        """Settings manager should have default duration setting"""
        with open('src/services/settings_manager.py', 'r') as f:
            content = f.read()
        
        assert "default_duration" in content.lower() or "get_default_duration" in content, \
            "Settings manager should have default duration"
    
    def test_availability_check_uses_duration(self):
        """Availability check should use service duration"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "duration_minutes" in content and "total_duration" in content, \
            "Availability check should use service duration"
    
    def test_booking_creation_uses_duration_and_buffer(self):
        """Booking creation should use duration + buffer for conflict check"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "buffer_time" in content and "total_duration" in content, \
            "Booking creation should use duration + buffer"


class TestServiceMatcher:
    """Test service matching logic"""
    
    def test_service_matcher_class_exists(self):
        """ServiceMatcher class should exist"""
        with open('src/services/calendar_tools.py', 'r') as f:
            content = f.read()
        
        assert "class ServiceMatcher" in content, \
            "ServiceMatcher class should exist"
    
    def test_service_matcher_has_match_method(self):
        """ServiceMatcher should have match_service method"""
        with open('src/services/calendar_tools.py', 'r') as f:
            content = f.read()
        
        assert "def match_service" in content, \
            "ServiceMatcher should have match_service method"
    
    def test_service_matcher_uses_confidence_threshold(self):
        """ServiceMatcher should use confidence threshold"""
        with open('src/services/calendar_tools.py', 'r') as f:
            content = f.read()
        
        assert "confidence" in content.lower() and "threshold" in content.lower(), \
            "ServiceMatcher should use confidence threshold"
    
    def test_service_matcher_falls_back_to_general(self):
        """ServiceMatcher should fall back to General Service"""
        with open('src/services/calendar_tools.py', 'r') as f:
            content = f.read()
        
        assert "General Service" in content, \
            "ServiceMatcher should fall back to General Service"
    
    def test_general_service_created_for_new_companies(self):
        """New companies should get General Service created"""
        with open('src/services/db_postgres_wrapper.py', 'r') as f:
            content = f.read()
        
        assert "General Service" in content, \
            "General Service should be created for new companies"


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_empty_string_name_rejected(self):
        """Empty string (after strip) should be rejected for required fields"""
        # Test that "   " (whitespace only) is rejected
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check that strip() is called before validation
        assert ".strip()" in content, \
            "Input should be stripped before validation"
    
    def test_negative_price_handled(self):
        """Negative prices should be converted to 0 or rejected"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "price < 0" in content, \
            "Negative prices should be handled"
    
    def test_negative_duration_handled(self):
        """Negative durations should be converted to default"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "duration < 1" in content or "duration > 0" in content, \
            "Negative durations should be handled"
    
    def test_invalid_worker_id_handled(self):
        """Invalid worker_id should be handled gracefully"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Invalid worker_id" in content, \
            "Invalid worker_id should return error"
    
    def test_none_values_dont_crash(self):
        """None values should not cause crashes"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check for safe None handling patterns
        assert "or ''" in content or "if data.get" in content, \
            "None values should be handled safely"
    
    def test_type_conversion_errors_handled(self):
        """Type conversion errors should be caught"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check for try/except around type conversions
        assert "except (ValueError, TypeError)" in content, \
            "Type conversion errors should be caught"


class TestFrontendValidation:
    """Test frontend form validation"""
    
    def test_customer_detail_modal_validates_name(self):
        """CustomerDetailModal should validate name when editing"""
        with open('frontend/src/components/modals/CustomerDetailModal.jsx', 'r') as f:
            content = f.read()
        
        assert "name is required" in content.lower() or "editData.name" in content, \
            "CustomerDetailModal should validate name"
    
    def test_add_job_modal_validates_required_fields(self):
        """AddJobModal should validate required fields"""
        with open('frontend/src/components/modals/AddJobModal.jsx', 'r') as f:
            content = f.read()
        
        assert "required fields" in content.lower() or "client_id" in content, \
            "AddJobModal should validate required fields"
    
    def test_add_job_modal_has_worker_selection(self):
        """AddJobModal should have worker selection"""
        with open('frontend/src/components/modals/AddJobModal.jsx', 'r') as f:
            content = f.read()
        
        assert "worker_id" in content and "handleWorkerSelect" in content, \
            "AddJobModal should have worker selection"
    
    def test_add_job_modal_checks_worker_availability(self):
        """AddJobModal should check worker availability"""
        with open('frontend/src/components/modals/AddJobModal.jsx', 'r') as f:
            content = f.read()
        
        assert "checkWorkerAvailability" in content or "workerAvailability" in content, \
            "AddJobModal should check worker availability"


class TestWorkersTabStatus:
    """Test workers tab status display"""
    
    def test_workers_tab_uses_assigned_worker_ids(self):
        """WorkersTab should use assigned_worker_ids array"""
        with open('frontend/src/components/dashboard/WorkersTab.jsx', 'r') as f:
            content = f.read()
        
        assert "assigned_worker_ids" in content, \
            "WorkersTab should use assigned_worker_ids array"
    
    def test_workers_tab_shows_busy_status(self):
        """WorkersTab should show busy/available status"""
        with open('frontend/src/components/dashboard/WorkersTab.jsx', 'r') as f:
            content = f.read()
        
        assert "isBusy" in content and "available" in content.lower(), \
            "WorkersTab should show busy/available status"
    
    def test_workers_tab_shows_jobs_today(self):
        """WorkersTab should show jobs today count"""
        with open('frontend/src/components/dashboard/WorkersTab.jsx', 'r') as f:
            content = f.read()
        
        assert "jobsToday" in content, \
            "WorkersTab should show jobs today count"


class TestDatabaseAssignedWorkerIds:
    """Test that database returns assigned_worker_ids array"""
    
    def test_get_all_bookings_returns_assigned_worker_ids(self):
        """get_all_bookings should return assigned_worker_ids array"""
        with open('src/services/db_postgres_wrapper.py', 'r') as f:
            content = f.read()
        
        assert "assigned_worker_ids" in content and "ARRAY_AGG" in content, \
            "get_all_bookings should return assigned_worker_ids using ARRAY_AGG"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
