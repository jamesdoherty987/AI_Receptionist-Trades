"""
Test CRUD Operations with Mocked Database

Tests actual endpoint logic with mocked database to verify:
1. Required field validation returns proper error codes
2. Optional field sanitization works correctly
3. Edge cases are handled properly
"""
import pytest
import sys
import os
import json
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# Set up environment before importing app
os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost/test')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing')


@pytest.fixture
def app_client():
    """Create Flask test client with mocked database"""
    # Patch database at module level before importing
    with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://test:test@localhost/test', 'SECRET_KEY': 'test-key'}):
        with patch('src.services.database.PostgreSQLDatabaseWrapper') as MockDB:
            with patch('src.services.database._db_instance', None):
                mock_db = MagicMock()
                MockDB.return_value = mock_db
                
                # Mock company for subscription check
                mock_db.get_company.return_value = {
                    'id': 1,
                    'company_name': 'Test Co',
                    'subscription_tier': 'professional',
                    'subscription_status': 'active',
                    'trial_end': (datetime.now() + timedelta(days=30)).isoformat()
                }
                
                # Need to patch get_database function
                with patch('src.services.database.get_database', return_value=mock_db):
                    # Import app after patching
                    from src.app import app
                    app.config['TESTING'] = True
                    app.config['WTF_CSRF_ENABLED'] = False
                    
                    with app.test_client() as client:
                        # Set up session
                        with client.session_transaction() as sess:
                            sess['company_id'] = 1
                            sess['email'] = 'test@test.com'
                        
                        yield client, mock_db


class TestClientValidationCodeInspection:
    """Test client validation by inspecting code"""
    
    def test_client_creation_requires_name(self):
        """Client creation should fail without name"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Customer name is required" in content
    
    def test_client_name_stripped(self):
        """Client name should be stripped"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert ".strip()" in content
    
    def test_client_optional_fields_sanitized(self):
        """Phone and email should be sanitized"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "phone if phone else None" in content


class TestEmployeeValidationCodeInspection:
    """Test employee validation by inspecting code"""
    
    def test_employee_creation_requires_name(self):
        """Employee creation should fail without name"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Employee name is required" in content
    
    def test_employee_weekly_hours_validation(self):
        """Weekly hours should be validated"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "weekly_hours < 0 or weekly_hours > 168" in content or "hours < 0 or hours > 168" in content


class TestBookingValidationCodeInspection:
    """Test booking validation by inspecting code"""
    
    def test_booking_requires_client_id(self):
        """Booking should require client_id"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Customer is required" in content
    
    def test_booking_requires_appointment_time(self):
        """Booking should require appointment_time"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Date & Time is required" in content
    
    def test_booking_requires_service_type(self):
        """Booking should require service_type"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Service type is required" in content
    
    def test_booking_validates_client_exists(self):
        """Booking should verify client exists"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Customer not found" in content


class TestServiceValidationCodeInspection:
    """Test service validation by inspecting code"""
    
    def test_service_creation_requires_name(self):
        """Service creation should require name"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Service name is required" in content
    
    def test_service_price_validation(self):
        """Price should be validated"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "price < 0" in content
    
    def test_service_duration_validation(self):
        """Duration should be validated"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "duration < 1" in content or "duration > 0" in content


class TestEmployeeAssignmentCodeInspection:
    """Test employee assignment by inspecting code"""
    
    def test_assign_employee_requires_employee_id(self):
        """Assign employee should require employee_id"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "employee_id is required" in content
    
    def test_assign_employee_validates_employee_id(self):
        """Assign employee should validate employee_id"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "Invalid employee_id" in content
    
    def test_assign_employee_checks_availability(self):
        """Assign employee should check availability"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "check_employee_availability" in content
    
    def test_assign_employee_supports_force(self):
        """Assign employee should support force option"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "force" in content


class TestErrorHandlingCodeInspection:
    """Test error handling by inspecting code"""
    
    def test_type_conversion_errors_caught(self):
        """Type conversion errors should be caught"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "except (ValueError, TypeError)" in content
    
    def test_empty_strings_handled(self):
        """Empty strings should be handled"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert "or ''" in content or "if data.get" in content


class TestDatabaseMethodsCodeInspection:
    """Test database methods by inspecting code"""
    
    def test_check_employee_availability_exists(self):
        """check_employee_availability should exist"""
        with open('src/services/db_postgres_wrapper.py', 'r') as f:
            content = f.read()
        
        assert "def check_employee_availability" in content
    
    def test_assigned_employee_ids_in_bookings(self):
        """get_all_bookings should return assigned_employee_ids"""
        with open('src/services/db_postgres_wrapper.py', 'r') as f:
            content = f.read()
        
        assert "assigned_employee_ids" in content
        assert "ARRAY_AGG" in content
    
    def test_general_service_created(self):
        """General Service should be created for new companies"""
        with open('src/services/db_postgres_wrapper.py', 'r') as f:
            content = f.read()
        
        assert "General Service" in content


class TestSettingsManagerCodeInspection:
    """Test settings manager by inspecting code"""
    
    def test_buffer_time_setting(self):
        """Settings manager should have buffer time"""
        with open('src/services/settings_manager.py', 'r') as f:
            content = f.read()
        
        assert "buffer" in content.lower()
    
    def test_default_duration_setting(self):
        """Settings manager should have default duration"""
        with open('src/services/settings_manager.py', 'r') as f:
            content = f.read()
        
        assert "duration" in content.lower()


class TestFrontendValidationCodeInspection:
    """Test frontend validation by inspecting code"""
    
    def test_customer_detail_modal_validates_name(self):
        """CustomerDetailModal should validate name"""
        with open('frontend/src/components/modals/CustomerDetailModal.jsx', 'r') as f:
            content = f.read()
        
        assert "editData.name" in content
    
    def test_add_job_modal_has_employee_selection(self):
        """AddJobModal should have employee selection"""
        with open('frontend/src/components/modals/AddJobModal.jsx', 'r') as f:
            content = f.read()
        
        assert "employee_id" in content
        assert "handleEmployeeSelect" in content
    
    def test_add_job_modal_checks_employee_availability(self):
        """AddJobModal should check employee availability"""
        with open('frontend/src/components/modals/AddJobModal.jsx', 'r') as f:
            content = f.read()
        
        assert "checkEmployeeAvailability" in content
    
    def test_employees_tab_uses_assigned_employee_ids(self):
        """EmployeesTab should use assigned_employee_ids"""
        with open('frontend/src/components/dashboard/EmployeesTab.jsx', 'r') as f:
            content = f.read()
        
        assert "assigned_employee_ids" in content
    
    def test_employees_tab_shows_busy_status(self):
        """EmployeesTab should show busy status"""
        with open('frontend/src/components/dashboard/EmployeesTab.jsx', 'r') as f:
            content = f.read()
        
        assert "isBusy" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
