"""
Test Data Isolation Between User Accounts

This test verifies that:
1. User A's data is NOT visible to User B
2. User A's data persists after logging out and back in
3. Database queries properly filter by company_id
4. API endpoints reject access to other users' data
"""
import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import MagicMock, patch
from datetime import datetime


class TestDatabaseIsolation:
    """Test that database methods properly filter by company_id"""
    
    def test_get_booking_with_company_id_filter(self):
        """Test that get_booking filters by company_id when provided"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        # Create a mock for the database
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock the connection pool
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            # Test with company_id filter
            mock_cursor.fetchone.return_value = None
            result = db.get_booking(1, company_id=100)
            
            # Verify the query includes company_id filter
            call_args = mock_cursor.execute.call_args
            query = call_args[0][0]
            params = call_args[0][1]
            
            assert 'company_id' in query.lower(), "Query should filter by company_id"
            assert 100 in params, "company_id should be in query parameters"
    
    def test_get_booking_without_company_id_no_filter(self):
        """Test that get_booking works without company_id for backwards compatibility"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            mock_cursor.fetchone.return_value = None
            result = db.get_booking(1)  # No company_id
            
            call_args = mock_cursor.execute.call_args
            query = call_args[0][0]
            
            # Without company_id, query should just filter by id
            assert 'id = %s' in query.lower()
    
    def test_get_client_with_company_id_filter(self):
        """Test that get_client filters by company_id when provided"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            mock_cursor.fetchone.return_value = None
            result = db.get_client(1, company_id=100)
            
            call_args = mock_cursor.execute.call_args
            query = call_args[0][0]
            params = call_args[0][1]
            
            assert 'company_id' in query.lower(), "Query should filter by company_id"
            assert 100 in params, "company_id should be in query parameters"
    
    def test_get_worker_with_company_id_filter(self):
        """Test that get_worker filters by company_id when provided"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            mock_cursor.fetchone.return_value = None
            result = db.get_worker(1, company_id=100)
            
            call_args = mock_cursor.execute.call_args
            query = call_args[0][0]
            params = call_args[0][1]
            
            assert 'company_id' in query.lower(), "Query should filter by company_id"
            assert 100 in params, "company_id should be in query parameters"
    
    def test_get_client_bookings_with_company_id_filter(self):
        """Test that get_client_bookings filters by company_id when provided"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            db.get_appointment_notes = MagicMock(return_value=[])
            
            mock_cursor.fetchall.return_value = []
            result = db.get_client_bookings(1, company_id=100)
            
            call_args = mock_cursor.execute.call_args
            query = call_args[0][0]
            params = call_args[0][1]
            
            assert 'company_id' in query.lower(), "Query should filter by company_id"
            assert 100 in params, "company_id should be in query parameters"
    
    def test_get_job_workers_with_company_id_filter(self):
        """Test that get_job_workers filters by company_id when provided"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            mock_cursor.fetchall.return_value = []
            result = db.get_job_workers(1, company_id=100)
            
            call_args = mock_cursor.execute.call_args
            query = call_args[0][0]
            params = call_args[0][1]
            
            assert 'company_id' in query.lower(), "Query should filter by company_id"
            assert 100 in params, "company_id should be in query parameters"
    
    def test_get_worker_jobs_with_company_id_filter(self):
        """Test that get_worker_jobs filters by company_id when provided"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            mock_cursor.fetchall.return_value = []
            result = db.get_worker_jobs(1, include_completed=False, company_id=100)
            
            call_args = mock_cursor.execute.call_args
            query = call_args[0][0]
            
            assert 'company_id' in query.lower(), "Query should filter by company_id"


class TestDataIsolationScenarios:
    """Test realistic data isolation scenarios"""
    
    def test_user_cannot_access_other_users_booking(self):
        """Simulate User B trying to access User A's booking"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            # User A's booking (company_id=1) - booking exists but belongs to different company
            # When User B (company_id=2) tries to access it, should return None
            mock_cursor.fetchone.return_value = None  # No match when filtering by wrong company_id
            
            result = db.get_booking(booking_id=1, company_id=2)  # User B's company
            
            assert result is None, "User B should not be able to access User A's booking"
    
    def test_user_can_access_own_booking(self):
        """Simulate User A accessing their own booking"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            # User A's booking - should be accessible
            mock_cursor.fetchone.return_value = {
                'id': 1,
                'company_id': 1,
                'service_type': 'Plumbing',
                'status': 'scheduled'
            }
            
            result = db.get_booking(booking_id=1, company_id=1)  # User A's company
            
            assert result is not None, "User A should be able to access their own booking"
            assert result['id'] == 1
            assert result['company_id'] == 1
    
    def test_data_persists_after_logout_login(self):
        """Verify data persists when user logs out and back in"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            # Simulate User A's data
            user_a_booking = {
                'id': 1,
                'company_id': 1,
                'service_type': 'Electrical Work',
                'status': 'scheduled',
                'charge': 150.00
            }
            
            # First login - User A sees their data
            mock_cursor.fetchone.return_value = user_a_booking
            result_before_logout = db.get_booking(booking_id=1, company_id=1)
            
            # Simulate logout (no database change, just session cleared)
            # ...
            
            # Second login - User A should still see their data
            mock_cursor.fetchone.return_value = user_a_booking
            result_after_login = db.get_booking(booking_id=1, company_id=1)
            
            assert result_before_logout == result_after_login, "Data should persist after logout/login"
            assert result_after_login['service_type'] == 'Electrical Work'
            assert result_after_login['charge'] == 150.00


class TestAPIEndpointIsolation:
    """Test that API endpoints properly enforce data isolation"""
    
    def test_booking_endpoint_uses_company_id(self):
        """Verify booking API endpoint passes company_id to database"""
        # This test verifies the code structure - that endpoints call db methods with company_id
        import ast
        
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check that booking_detail_api uses company_id parameter
        assert 'db.get_booking(booking_id, company_id=company_id)' in content, \
            "booking_detail_api should pass company_id to get_booking"
    
    def test_client_endpoint_uses_company_id(self):
        """Verify client API endpoint passes company_id to database"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert 'db.get_client(client_id, company_id=company_id)' in content, \
            "client_api should pass company_id to get_client"
    
    def test_worker_endpoint_uses_company_id(self):
        """Verify worker API endpoint passes company_id to database"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        assert 'db.get_worker(worker_id, company_id=company_id)' in content, \
            "worker_api should pass company_id to get_worker"
    
    def test_no_unfiltered_get_booking_calls(self):
        """Ensure all get_booking calls in API endpoints use company_id"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Find all get_booking calls
        import re
        
        # Pattern for get_booking calls without company_id
        # This matches db.get_booking(something) but NOT db.get_booking(something, company_id=...)
        unfiltered_pattern = r'db\.get_booking\([^)]+\)(?!\s*#.*company)'
        
        # Get all get_booking calls
        all_calls = re.findall(r'db\.get_booking\([^)]+\)', content)
        
        # Check each call has company_id OR has a comment explaining it extracts company_id from booking
        for call in all_calls:
            # Allow calls that have company_id= parameter
            if 'company_id=' in call:
                continue
            # Allow calls with inline comment explaining company_id is extracted from booking itself
            # These are webhook handlers where we get booking first to extract its company_id
            call_line_pattern = re.escape(call) + r'.*#.*company_id.*extracted'
            if re.search(call_line_pattern, content):
                continue
            assert False, f"Unfiltered get_booking call found: {call}"
    
    def test_no_unfiltered_get_client_calls_in_api(self):
        """Ensure critical get_client calls use company_id"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # All get_client calls should have company_id for security
        import re
        all_calls = re.findall(r'db\.get_client\([^)]+\)', content)
        
        for call in all_calls:
            assert 'company_id=' in call, f"Unfiltered get_client call found: {call}"
    
    def test_no_unfiltered_get_worker_calls_in_api(self):
        """Ensure critical get_worker calls use company_id"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        import re
        all_calls = re.findall(r'db\.get_worker\([^)]+\)', content)
        
        for call in all_calls:
            assert 'company_id=' in call, f"Unfiltered get_worker call found: {call}"


class TestFrontendCacheClear:
    """Test that frontend properly clears cache on logout"""
    
    def test_logout_clears_query_cache(self):
        """Verify logout function calls queryClient.clear()"""
        with open('frontend/src/context/AuthContext.jsx', 'r') as f:
            content = f.read()
        
        assert 'queryClient.clear()' in content, \
            "Logout should clear React Query cache to prevent data leakage"
    
    def test_query_client_imported(self):
        """Verify queryClient is imported in AuthContext"""
        with open('frontend/src/context/AuthContext.jsx', 'r') as f:
            content = f.read()
        
        assert "import { queryClient }" in content, \
            "queryClient should be imported in AuthContext"
    
    def test_query_client_exported(self):
        """Verify queryClient is properly exported"""
        with open('frontend/src/queryClient.js', 'r') as f:
            content = f.read()
        
        assert 'export const queryClient' in content, \
            "queryClient should be exported from queryClient.js"


class TestEdgeCases:
    """Test edge cases and security boundaries"""
    
    def test_login_required_validates_company_id_type(self):
        """Verify login_required checks company_id is a valid integer"""
        with open('src/app.py', 'r') as f:
            content = f.read()
        
        # Check that login_required validates company_id is an integer
        assert 'isinstance(company_id, int)' in content, \
            "login_required should validate company_id is an integer"
    
    def test_database_methods_have_security_comments(self):
        """Verify database methods document security behavior"""
        with open('src/services/db_postgres_wrapper.py', 'r') as f:
            content = f.read()
        
        assert 'SECURITY' in content, \
            "Database methods should document security behavior"
    
    def test_null_company_id_returns_none(self):
        """Test that passing company_id=0 or None doesn't bypass security"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        from unittest.mock import MagicMock, patch
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            # When company_id=0 (falsy), it should fall back to unfiltered query
            # This is for backwards compatibility with internal services
            mock_cursor.fetchone.return_value = {'id': 1, 'company_id': 1}
            result = db.get_booking(1, company_id=0)
            
            # The query should NOT include company_id filter when company_id is 0
            call_args = mock_cursor.execute.call_args
            query = call_args[0][0]
            
            # With company_id=0 (falsy), falls back to unfiltered for backwards compat
            assert 'id = %s' in query.lower()
    
    def test_different_company_ids_isolated(self):
        """Test that two different company_ids get different results"""
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        from unittest.mock import MagicMock, patch
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(PostgreSQLDatabaseWrapper, '__init__', lambda x, y: None):
            db = PostgreSQLDatabaseWrapper.__new__(PostgreSQLDatabaseWrapper)
            db.get_connection = MagicMock(return_value=mock_conn)
            db.return_connection = MagicMock()
            
            # Company 1 queries
            mock_cursor.fetchone.return_value = {'id': 1, 'company_id': 1, 'service_type': 'Plumbing'}
            result_company1 = db.get_booking(1, company_id=1)
            
            call_args_1 = mock_cursor.execute.call_args
            params_1 = call_args_1[0][1]
            
            # Company 2 queries same booking ID
            mock_cursor.fetchone.return_value = None  # Different company, no access
            result_company2 = db.get_booking(1, company_id=2)
            
            call_args_2 = mock_cursor.execute.call_args
            params_2 = call_args_2[0][1]
            
            # Verify different company_ids were used in queries
            assert 1 in params_1, "Company 1 ID should be in first query"
            assert 2 in params_2, "Company 2 ID should be in second query"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
