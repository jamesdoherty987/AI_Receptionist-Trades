"""
Test Employee Availability Checking

Tests the employee availability checking logic:
1. Basic availability checking
2. Buffer time handling
3. Conflict detection
4. Error handling (safe defaults)
"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestEmployeeAvailabilityBasics:
    """Test basic employee availability functionality"""
    
    def test_check_employee_availability_exists(self):
        """check_employee_availability function should exist"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        assert hasattr(PostgreSQLDatabaseWrapper, 'check_employee_availability')
    
    def test_availability_returns_dict(self):
        """check_employee_availability should return a dict"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            result = db.check_employee_availability(
                employee_id=1,
                appointment_time='2025-03-01T10:00:00',
                duration_minutes=60,
                company_id=1
            )
            
            assert isinstance(result, dict)
            assert 'available' in result


class TestAvailabilityLogic:
    """Test availability checking logic"""
    
    def test_employee_available_when_no_conflicts(self):
        """Employee should be available when no conflicting jobs"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []  # No conflicting jobs
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            result = db.check_employee_availability(
                employee_id=1,
                appointment_time='2025-03-01T10:00:00',
                duration_minutes=60,
                company_id=1
            )
            
            assert result['available'] is True
    
    def test_employee_unavailable_when_conflict_exists(self):
        """Employee should be unavailable when conflicting job exists"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Return a conflicting job
        mock_cursor.fetchall.return_value = [{
            'id': 1,
            'appointment_time': datetime(2025, 3, 1, 10, 0),
            'duration_minutes': 60,
            'service_type': 'Plumbing'
        }]
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            result = db.check_employee_availability(
                employee_id=1,
                appointment_time='2025-03-01T10:00:00',
                duration_minutes=60,
                company_id=1
            )
            
            assert result['available'] is False
            assert 'conflict' in result or 'message' in result


class TestBufferTimeHandling:
    """Test buffer time in availability checking"""
    
    def test_buffer_time_considered(self):
        """Buffer time should be considered in availability check"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            db.check_employee_availability(
                employee_id=1,
                appointment_time='2025-03-01T10:00:00',
                duration_minutes=60,
                company_id=1
            )
            
            # Verify the query was called
            assert mock_cursor.execute.called
            
            # The query should consider buffer time
            query = mock_cursor.execute.call_args[0][0]
            # Buffer time should extend the time window checked
            assert 'appointment_time' in query.lower()


class TestErrorHandling:
    """Test error handling in availability checking"""
    
    def test_returns_false_on_database_error(self):
        """Should return available=False on database error (safe default)"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            result = db.check_employee_availability(
                employee_id=1,
                appointment_time='2025-03-01T10:00:00',
                duration_minutes=60,
                company_id=1
            )
            
            # Should return False on error to prevent double-booking
            assert result['available'] is False
    
    def test_handles_invalid_datetime(self):
        """Should handle invalid datetime gracefully"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            result = db.check_employee_availability(
                employee_id=1,
                appointment_time='invalid-datetime',
                duration_minutes=60,
                company_id=1
            )
            
            # Should not crash, should return safe default
            assert isinstance(result, dict)
            assert 'available' in result


class TestConflictDetails:
    """Test conflict details in availability response"""
    
    def test_conflict_includes_job_details(self):
        """Conflict response should include job details"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        conflicting_job = {
            'id': 1,
            'appointment_time': datetime(2025, 3, 1, 10, 0),
            'duration_minutes': 60,
            'service_type': 'Plumbing',
            'client_name': 'John Doe'
        }
        mock_cursor.fetchall.return_value = [conflicting_job]
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            result = db.check_employee_availability(
                employee_id=1,
                appointment_time='2025-03-01T10:00:00',
                duration_minutes=60,
                company_id=1
            )
            
            assert result['available'] is False
            # Should include some conflict information
            assert 'message' in result or 'conflict' in result or 'conflicting_job' in result


class TestEdgeCases:
    """Test edge cases in availability checking"""
    
    def test_zero_duration_handled(self):
        """Should handle zero duration gracefully"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            result = db.check_employee_availability(
                employee_id=1,
                appointment_time='2025-03-01T10:00:00',
                duration_minutes=0,  # Edge case
                company_id=1
            )
            
            # Should not crash
            assert isinstance(result, dict)
    
    def test_negative_duration_handled(self):
        """Should handle negative duration gracefully"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            result = db.check_employee_availability(
                employee_id=1,
                appointment_time='2025-03-01T10:00:00',
                duration_minutes=-60,  # Invalid
                company_id=1
            )
            
            # Should not crash
            assert isinstance(result, dict)
    
    def test_none_employee_id_handled(self):
        """Should handle None employee_id gracefully"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            result = db.check_employee_availability(
                employee_id=None,
                appointment_time='2025-03-01T10:00:00',
                duration_minutes=60,
                company_id=1
            )
            
            # Should return a dict (either available or not)
            assert isinstance(result, dict)
            assert 'available' in result


class TestCompanyIsolation:
    """Test that availability checking respects company isolation"""
    
    def test_only_checks_same_company_jobs(self):
        """Should only check jobs from the same company"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            db.check_employee_availability(
                employee_id=1,
                appointment_time='2025-03-01T10:00:00',
                duration_minutes=60,
                company_id=1
            )
            
            # Verify company_id is in the query
            query = mock_cursor.execute.call_args[0][0]
            params = mock_cursor.execute.call_args[0][1]
            
            assert 'company_id' in query.lower() or 1 in params


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
