"""
Tests for Google Calendar OAuth integration.
Tests the OAuth flow logic, token storage, and CompanyGoogleCalendar interface.
"""
import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timedelta


class TestGetClientConfig:
    """Test _get_client_config builds correct OAuth config from env vars."""

    @patch.dict('os.environ', {
        'GOOGLE_OAUTH_CLIENT_ID': 'test-client-id.apps.googleusercontent.com',
        'GOOGLE_OAUTH_CLIENT_SECRET': 'test-secret'
    })
    def test_builds_config_from_env(self):
        from src.services.google_calendar_oauth import _get_client_config
        config = _get_client_config()
        # Verify it reads from env (actual values may differ if .env is loaded)
        assert 'client_id' in config['web']
        assert 'client_secret' in config['web']
        assert config['web']['auth_uri'] == 'https://accounts.google.com/o/oauth2/auth'
        assert config['web']['token_uri'] == 'https://oauth2.googleapis.com/token'

    @patch.dict('os.environ', {}, clear=True)
    def test_raises_without_env_vars(self):
        # Need to also clear any existing env vars
        import os
        os.environ.pop('GOOGLE_OAUTH_CLIENT_ID', None)
        os.environ.pop('GOOGLE_OAUTH_CLIENT_SECRET', None)
        from src.services.google_calendar_oauth import _get_client_config
        with pytest.raises(ValueError, match="GOOGLE_OAUTH_CLIENT_ID"):
            _get_client_config()

    @patch.dict('os.environ', {
        'GOOGLE_OAUTH_CLIENT_ID': 'test-id',
        'GOOGLE_OAUTH_CLIENT_SECRET': ''
    })
    def test_raises_with_empty_secret(self):
        from src.services.google_calendar_oauth import _get_client_config
        with pytest.raises(ValueError):
            _get_client_config()


class TestOAuthRedirectUri:
    """Test redirect URI generation."""

    @patch('src.services.google_calendar_oauth.config')
    def test_uses_public_url(self, mock_config):
        mock_config.PUBLIC_URL = 'https://myapp.onrender.com'
        from src.services.google_calendar_oauth import get_oauth_redirect_uri
        uri = get_oauth_redirect_uri()
        assert uri == 'https://myapp.onrender.com/api/google-calendar/callback'

    @patch('src.services.google_calendar_oauth.config')
    def test_strips_trailing_slash(self, mock_config):
        mock_config.PUBLIC_URL = 'https://myapp.onrender.com/'
        from src.services.google_calendar_oauth import get_oauth_redirect_uri
        uri = get_oauth_redirect_uri()
        assert uri == 'https://myapp.onrender.com/api/google-calendar/callback'

    @patch('src.services.google_calendar_oauth.config')
    def test_fallback_to_localhost(self, mock_config):
        mock_config.PUBLIC_URL = None
        from src.services.google_calendar_oauth import get_oauth_redirect_uri
        uri = get_oauth_redirect_uri()
        assert uri == 'http://localhost:5000/api/google-calendar/callback'


class TestDisconnectGoogleCalendar:
    """Test disconnecting Google Calendar."""

    def test_disconnect_clears_credentials(self):
        from src.services.google_calendar_oauth import disconnect_google_calendar, _company_calendar_cache
        mock_db = MagicMock()
        mock_db.update_company.return_value = True

        # Pre-populate cache
        _company_calendar_cache[42] = MagicMock()

        result = disconnect_google_calendar(42, mock_db)
        assert result is True
        mock_db.update_company.assert_called_once_with(
            42, google_credentials_json=None, google_calendar_id=None
        )
        assert 42 not in _company_calendar_cache


class TestGetCompanyCalendarStatus:
    """Test calendar status checking."""

    def test_not_connected_when_no_company(self):
        from src.services.google_calendar_oauth import get_company_calendar_status
        mock_db = MagicMock()
        mock_db.get_company.return_value = None
        status = get_company_calendar_status(1, mock_db)
        assert status['connected'] is False

    def test_not_connected_when_no_credentials(self):
        from src.services.google_calendar_oauth import get_company_calendar_status
        mock_db = MagicMock()
        mock_db.get_company.return_value = {'google_credentials_json': None}
        status = get_company_calendar_status(1, mock_db)
        assert status['connected'] is False

    def test_not_connected_when_empty_credentials(self):
        from src.services.google_calendar_oauth import get_company_calendar_status
        mock_db = MagicMock()
        mock_db.get_company.return_value = {'google_credentials_json': ''}
        status = get_company_calendar_status(1, mock_db)
        assert status['connected'] is False

    @patch('src.services.google_calendar_oauth.build')
    @patch('src.services.google_calendar_oauth.Request')
    def test_connected_with_valid_credentials(self, mock_request, mock_build):
        from src.services.google_calendar_oauth import get_company_calendar_status
        mock_db = MagicMock()
        token_data = {
            'token': 'valid-token',
            'refresh_token': 'refresh-token',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test-id',
            'client_secret': 'test-secret',
            'scopes': ['https://www.googleapis.com/auth/calendar'],
            'expiry': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        mock_db.get_company.return_value = {
            'google_credentials_json': json.dumps(token_data),
            'google_calendar_id': 'primary'
        }

        # Mock the calendar API call
        mock_service = MagicMock()
        mock_service.calendars().get().execute.return_value = {
            'summary': 'test@gmail.com', 'id': 'test@gmail.com'
        }
        mock_build.return_value = mock_service

        status = get_company_calendar_status(1, mock_db)
        assert status['connected'] is True
        assert status['calendar_id'] == 'primary'


class TestGetCompanyGoogleCalendar:
    """Test getting a calendar service instance."""

    def test_returns_none_when_no_company(self):
        from src.services.google_calendar_oauth import get_company_google_calendar, _company_calendar_cache
        _company_calendar_cache.clear()
        mock_db = MagicMock()
        mock_db.get_company.return_value = None
        result = get_company_google_calendar(1, mock_db)
        assert result is None

    def test_returns_none_when_no_credentials(self):
        from src.services.google_calendar_oauth import get_company_google_calendar, _company_calendar_cache
        _company_calendar_cache.clear()
        mock_db = MagicMock()
        mock_db.get_company.return_value = {'google_credentials_json': None}
        result = get_company_google_calendar(1, mock_db)
        assert result is None

    @patch('src.services.google_calendar_oauth.build')
    @patch('src.services.google_calendar_oauth.Request')
    def test_creates_calendar_with_valid_credentials(self, mock_request, mock_build):
        from src.services.google_calendar_oauth import get_company_google_calendar, _company_calendar_cache
        _company_calendar_cache.clear()
        mock_db = MagicMock()
        token_data = {
            'token': 'valid-token',
            'refresh_token': 'refresh-token',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test-id',
            'client_secret': 'test-secret',
            'scopes': ['https://www.googleapis.com/auth/calendar'],
            'expiry': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        mock_db.get_company.return_value = {
            'google_credentials_json': json.dumps(token_data),
            'google_calendar_id': 'primary'
        }
        mock_build.return_value = MagicMock()

        result = get_company_google_calendar(99, mock_db)
        assert result is not None
        assert result.calendar_id == 'primary'
        assert result.company_id == 99
        # Should be cached
        assert 99 in _company_calendar_cache

    @patch('src.services.google_calendar_oauth.build')
    @patch('src.services.google_calendar_oauth.Request')
    def test_uses_cache_on_second_call(self, mock_request, mock_build):
        from src.services.google_calendar_oauth import get_company_google_calendar, _company_calendar_cache
        _company_calendar_cache.clear()
        mock_db = MagicMock()
        token_data = {
            'token': 'valid-token',
            'refresh_token': 'refresh-token',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test-id',
            'client_secret': 'test-secret',
            'scopes': ['https://www.googleapis.com/auth/calendar'],
            'expiry': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        mock_db.get_company.return_value = {
            'google_credentials_json': json.dumps(token_data),
            'google_calendar_id': 'primary'
        }
        mock_build.return_value = MagicMock()

        result1 = get_company_google_calendar(100, mock_db)
        result2 = get_company_google_calendar(100, mock_db)
        # Should only build once
        assert mock_build.call_count == 1
        assert result1 is result2


class TestCompanyGoogleCalendar:
    """Test the CompanyGoogleCalendar wrapper methods."""

    def _make_calendar(self):
        from src.services.google_calendar_oauth import CompanyGoogleCalendar
        mock_service = MagicMock()
        return CompanyGoogleCalendar(mock_service, 'primary', company_id=1)

    def test_is_valid_when_fresh(self):
        cal = self._make_calendar()
        assert cal.is_valid() is True

    def test_is_invalid_after_timeout(self):
        cal = self._make_calendar()
        cal._created_at = datetime.now() - timedelta(seconds=3100)
        assert cal.is_valid() is False

    def test_book_appointment_creates_event(self):
        cal = self._make_calendar()
        cal.service.events().insert().execute.return_value = {'id': 'evt123', 'htmlLink': 'http://...'}

        start = datetime(2026, 3, 25, 10, 0)
        result = cal.book_appointment('Test Job - John', start, duration_minutes=60, description='Plumbing fix')

        assert result is not None
        cal.service.events().insert.assert_called()

    def test_check_availability_returns_true_when_no_events(self):
        cal = self._make_calendar()
        cal.service.events().list().execute.return_value = {'items': []}

        start = datetime(2026, 3, 25, 10, 0)
        assert cal.check_availability(start, 60) is True

    def test_check_availability_returns_false_when_busy(self):
        cal = self._make_calendar()
        cal.service.events().list().execute.return_value = {'items': [{'id': 'existing'}]}

        start = datetime(2026, 3, 25, 10, 0)
        assert cal.check_availability(start, 60) is False

    def test_cancel_appointment(self):
        cal = self._make_calendar()
        cal.service.events().delete().execute.return_value = None

        assert cal.cancel_appointment('evt123') is True

    def test_cancel_appointment_handles_error(self):
        cal = self._make_calendar()
        cal.service.events().delete().execute.side_effect = Exception("Not found")

        assert cal.cancel_appointment('evt123') is False

    def test_update_event_description(self):
        cal = self._make_calendar()
        cal.service.events().get().execute.return_value = {'id': 'evt123', 'description': 'old'}
        cal.service.events().update().execute.return_value = {'id': 'evt123'}

        assert cal.update_event_description('evt123', 'new description') is True


class TestHandleOAuthCallback:
    """Test the OAuth callback token exchange."""

    @patch('src.services.google_calendar_oauth._get_client_config')
    @patch('src.services.google_calendar_oauth.get_oauth_redirect_uri')
    @patch('src.services.google_calendar_oauth.Flow')
    def test_stores_tokens_in_db(self, mock_flow_class, mock_redirect, mock_config):
        from src.services.google_calendar_oauth import handle_oauth_callback, _company_calendar_cache

        mock_config.return_value = {'web': {'client_id': 'id', 'client_secret': 'secret',
                                             'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                                             'token_uri': 'https://oauth2.googleapis.com/token',
                                             'redirect_uris': []}}
        mock_redirect.return_value = 'http://localhost:5000/api/google-calendar/callback'

        # Mock the flow
        mock_flow = MagicMock()
        mock_flow_class.from_client_config.return_value = mock_flow
        mock_creds = MagicMock()
        mock_creds.token = 'access-token'
        mock_creds.refresh_token = 'refresh-token'
        mock_creds.token_uri = 'https://oauth2.googleapis.com/token'
        mock_creds.client_id = 'id'
        mock_creds.client_secret = 'secret'
        mock_creds.scopes = {'https://www.googleapis.com/auth/calendar'}
        mock_creds.expiry = datetime(2026, 3, 20, 12, 0, 0)
        mock_flow.credentials = mock_creds

        mock_db = MagicMock()
        mock_db.update_company.return_value = True

        # Pre-populate cache to verify it gets cleared
        _company_calendar_cache[5] = MagicMock()

        result = handle_oauth_callback('http://localhost?code=abc&state=5', 5, mock_db)
        assert result is True

        # Verify tokens stored in DB
        call_kwargs = mock_db.update_company.call_args
        assert call_kwargs[0][0] == 5  # company_id
        stored_json = call_kwargs[1]['google_credentials_json']
        stored = json.loads(stored_json)
        assert stored['token'] == 'access-token'
        assert stored['refresh_token'] == 'refresh-token'
        assert call_kwargs[1]['google_calendar_id'] == 'primary'

        # Cache should be cleared
        assert 5 not in _company_calendar_cache


class TestStartOAuthFlow:
    """Test starting the OAuth flow."""

    @patch('src.services.google_calendar_oauth._get_client_config')
    @patch('src.services.google_calendar_oauth.get_oauth_redirect_uri')
    @patch('src.services.google_calendar_oauth.Flow')
    def test_returns_authorization_url(self, mock_flow_class, mock_redirect, mock_config):
        from src.services.google_calendar_oauth import start_oauth_flow

        mock_config.return_value = {'web': {'client_id': 'id', 'client_secret': 'secret',
                                             'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                                             'token_uri': 'https://oauth2.googleapis.com/token',
                                             'redirect_uris': []}}
        mock_redirect.return_value = 'http://localhost:5000/api/google-calendar/callback'

        mock_flow = MagicMock()
        mock_flow_class.from_client_config.return_value = mock_flow
        mock_flow.authorization_url.return_value = ('https://accounts.google.com/o/oauth2/auth?...', 'state123')

        url = start_oauth_flow(42)
        assert 'accounts.google.com' in url

        # Verify state is set to company_id
        mock_flow.authorization_url.assert_called_once_with(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state='42'
        )
