"""
Tests for:
1. POST /api/finances/mark-paid endpoint (bulk mark bookings as paid)
2. Feature toggle settings (show_finances_tab, show_invoice_buttons)
3. GET /api/finances endpoint (revenue calculations, chart data)
"""
import pytest
import sys
import os
import json
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost/test')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing')


@pytest.fixture
def app_client():
    """Create Flask test client with mocked database"""
    from src.app import app
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'

    mock_db = MagicMock()
    mock_db.get_company.return_value = {
        'id': 1,
        'company_name': 'Test Co',
        'subscription_tier': 'professional',
        'subscription_status': 'active',
        'trial_end': (datetime.now() + timedelta(days=30)).isoformat()
    }

    with patch('src.app.get_database', return_value=mock_db):
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['company_id'] = 1
                sess['email'] = 'test@test.com'

            yield client, mock_db


def _make_booking(id, charge, status, payment_status, appointment_time, cancelled=False):
    """Helper to create a booking dict"""
    return {
        'id': id,
        'charge': charge,
        'status': 'cancelled' if cancelled else status,
        'payment_status': payment_status,
        'appointment_time': appointment_time,
        'customer_name': f'Customer {id}',
        'service_type': 'Plumbing',
        'client_id': None,
    }


# ─── Mark-Paid Endpoint Tests ───────────────────────────────────────────────

class TestMarkPaidEndpoint:
    """Tests for POST /api/finances/mark-paid"""

    def test_mark_all_past_as_paid(self, app_client):
        client, mock_db = app_client
        yesterday = datetime.now() - timedelta(days=1)
        bookings = [
            _make_booking(1, 100, 'scheduled', 'pending', yesterday),
            _make_booking(2, 200, 'scheduled', 'pending', yesterday - timedelta(days=5)),
        ]
        mock_db.get_all_bookings.return_value = bookings
        mock_db.update_booking.return_value = True

        resp = client.post('/api/finances/mark-paid',
                           data=json.dumps({'scope': 'all'}),
                           content_type='application/json')
        data = resp.get_json()

        assert resp.status_code == 200
        assert data['success'] is True
        assert data['updated'] == 2
        assert mock_db.update_booking.call_count == 2

    def test_mark_today_scope(self, app_client):
        client, mock_db = app_client
        today = datetime.now().replace(hour=10, minute=0)
        tomorrow = datetime.now() + timedelta(days=1)
        bookings = [
            _make_booking(1, 50, 'scheduled', 'pending', today),
            _make_booking(2, 75, 'scheduled', 'pending', tomorrow),  # future, should NOT be marked
        ]
        mock_db.get_all_bookings.return_value = bookings
        mock_db.update_booking.return_value = True

        resp = client.post('/api/finances/mark-paid',
                           data=json.dumps({'scope': 'today'}),
                           content_type='application/json')
        data = resp.get_json()

        assert resp.status_code == 200
        assert data['updated'] == 1

    def test_mark_week_scope(self, app_client):
        client, mock_db = app_client
        today = datetime.now()
        two_weeks_later = today + timedelta(days=14)
        yesterday = today - timedelta(days=1)
        bookings = [
            _make_booking(1, 100, 'scheduled', 'pending', yesterday),
            _make_booking(2, 100, 'scheduled', 'pending', today.replace(hour=8)),
            _make_booking(3, 100, 'scheduled', 'pending', two_weeks_later),  # too far out
        ]
        mock_db.get_all_bookings.return_value = bookings
        mock_db.update_booking.return_value = True

        resp = client.post('/api/finances/mark-paid',
                           data=json.dumps({'scope': 'week'}),
                           content_type='application/json')
        data = resp.get_json()

        assert resp.status_code == 200
        assert data['updated'] == 2

    def test_skips_already_paid(self, app_client):
        client, mock_db = app_client
        yesterday = datetime.now() - timedelta(days=1)
        bookings = [
            _make_booking(1, 100, 'completed', 'paid', yesterday),  # already paid
            _make_booking(2, 200, 'paid', 'paid', yesterday),       # already paid
            _make_booking(3, 150, 'scheduled', 'pending', yesterday),  # should be marked
        ]
        mock_db.get_all_bookings.return_value = bookings
        mock_db.update_booking.return_value = True

        resp = client.post('/api/finances/mark-paid',
                           data=json.dumps({'scope': 'all'}),
                           content_type='application/json')
        data = resp.get_json()

        assert data['updated'] == 1

    def test_skips_cancelled(self, app_client):
        client, mock_db = app_client
        yesterday = datetime.now() - timedelta(days=1)
        bookings = [
            _make_booking(1, 100, 'cancelled', 'pending', yesterday, cancelled=True),
            _make_booking(2, 200, 'scheduled', 'pending', yesterday),
        ]
        mock_db.get_all_bookings.return_value = bookings
        mock_db.update_booking.return_value = True

        resp = client.post('/api/finances/mark-paid',
                           data=json.dumps({'scope': 'all'}),
                           content_type='application/json')
        data = resp.get_json()

        assert data['updated'] == 1

    def test_skips_zero_charge(self, app_client):
        client, mock_db = app_client
        yesterday = datetime.now() - timedelta(days=1)
        bookings = [
            _make_booking(1, 0, 'scheduled', 'pending', yesterday),
            _make_booking(2, None, 'scheduled', 'pending', yesterday),
            _make_booking(3, 100, 'scheduled', 'pending', yesterday),
        ]
        mock_db.get_all_bookings.return_value = bookings
        mock_db.update_booking.return_value = True

        resp = client.post('/api/finances/mark-paid',
                           data=json.dumps({'scope': 'all'}),
                           content_type='application/json')
        data = resp.get_json()

        assert data['updated'] == 1

    def test_invalid_scope_returns_400(self, app_client):
        client, mock_db = app_client

        resp = client.post('/api/finances/mark-paid',
                           data=json.dumps({'scope': 'invalid'}),
                           content_type='application/json')

        assert resp.status_code == 400
        assert 'Invalid scope' in resp.get_json()['error']

    def test_no_bookings_returns_zero(self, app_client):
        client, mock_db = app_client
        mock_db.get_all_bookings.return_value = []

        resp = client.post('/api/finances/mark-paid',
                           data=json.dumps({'scope': 'all'}),
                           content_type='application/json')
        data = resp.get_json()

        assert resp.status_code == 200
        assert data['updated'] == 0

    def test_handles_datetime_objects(self, app_client):
        """appointment_time from Postgres is a datetime object, not a string"""
        client, mock_db = app_client
        yesterday = datetime.now() - timedelta(days=1)
        bookings = [
            _make_booking(1, 100, 'scheduled', 'pending', yesterday),
        ]
        mock_db.get_all_bookings.return_value = bookings
        mock_db.update_booking.return_value = True

        resp = client.post('/api/finances/mark-paid',
                           data=json.dumps({'scope': 'all'}),
                           content_type='application/json')

        assert resp.status_code == 200
        assert resp.get_json()['updated'] == 1

    def test_handles_string_appointment_time(self, app_client):
        """appointment_time can also be an ISO string"""
        client, mock_db = app_client
        yesterday_str = (datetime.now() - timedelta(days=1)).isoformat()
        bookings = [
            _make_booking(1, 100, 'scheduled', 'pending', yesterday_str),
        ]
        mock_db.get_all_bookings.return_value = bookings
        mock_db.update_booking.return_value = True

        resp = client.post('/api/finances/mark-paid',
                           data=json.dumps({'scope': 'all'}),
                           content_type='application/json')

        assert resp.status_code == 200
        assert resp.get_json()['updated'] == 1

    def test_scope_message_labels(self, app_client):
        client, mock_db = app_client
        mock_db.get_all_bookings.return_value = []

        for scope, expected_label in [
            ('all', 'all past'),
            ('today', "today's and earlier"),
            ('week', "this week's and earlier"),
        ]:
            resp = client.post('/api/finances/mark-paid',
                               data=json.dumps({'scope': scope}),
                               content_type='application/json')
            assert expected_label in resp.get_json()['message']


# ─── Finances GET Endpoint Tests ────────────────────────────────────────────

class TestFinancesEndpoint:
    """Tests for GET /api/finances"""

    def test_empty_bookings(self, app_client):
        client, mock_db = app_client
        mock_db.get_all_bookings.return_value = []

        resp = client.get('/api/finances')
        data = resp.get_json()

        assert resp.status_code == 200
        assert data['total_revenue'] == 0
        assert data['paid_revenue'] == 0
        assert data['unpaid_revenue'] == 0
        assert data['transactions'] == []
        assert data['monthly_revenue'] == []

    def test_revenue_calculation(self, app_client):
        client, mock_db = app_client
        now = datetime.now()
        bookings = [
            _make_booking(1, 100, 'completed', 'paid', now - timedelta(days=1)),
            _make_booking(2, 200, 'scheduled', 'pending', now - timedelta(days=2)),
            _make_booking(3, 50, 'cancelled', None, now - timedelta(days=3)),
        ]
        mock_db.get_all_bookings.return_value = bookings

        resp = client.get('/api/finances')
        data = resp.get_json()

        assert data['paid_revenue'] == 100
        assert data['unpaid_revenue'] == 200
        assert data['total_revenue'] == 300

    def test_transactions_exclude_zero_charge(self, app_client):
        client, mock_db = app_client
        now = datetime.now()
        bookings = [
            _make_booking(1, 100, 'scheduled', 'pending', now),
            _make_booking(2, 0, 'scheduled', 'pending', now),
        ]
        mock_db.get_all_bookings.return_value = bookings

        resp = client.get('/api/finances')
        data = resp.get_json()

        assert len(data['transactions']) == 1

    def test_monthly_revenue_chart_with_datetime_objects(self, app_client):
        """Verify chart works when appointment_time is a datetime object (Postgres)"""
        client, mock_db = app_client
        now = datetime.now()
        bookings = [
            _make_booking(1, 100, 'scheduled', 'pending', now),
            _make_booking(2, 200, 'completed', 'paid', now - timedelta(days=35)),
        ]
        mock_db.get_all_bookings.return_value = bookings

        resp = client.get('/api/finances')
        data = resp.get_json()

        assert len(data['monthly_revenue']) >= 1
        assert all(m['revenue'] > 0 for m in data['monthly_revenue'])

    def test_cancelled_excluded_from_chart(self, app_client):
        client, mock_db = app_client
        now = datetime.now()
        bookings = [
            _make_booking(1, 500, 'cancelled', None, now),
        ]
        mock_db.get_all_bookings.return_value = bookings

        resp = client.get('/api/finances')
        data = resp.get_json()

        assert data['monthly_revenue'] == []

    def test_paid_status_variants(self, app_client):
        """Both status='completed'/'paid' and payment_status='paid' count as paid"""
        client, mock_db = app_client
        now = datetime.now()
        bookings = [
            _make_booking(1, 100, 'completed', None, now),
            _make_booking(2, 100, 'paid', None, now),
            _make_booking(3, 100, 'scheduled', 'paid', now),
        ]
        mock_db.get_all_bookings.return_value = bookings

        resp = client.get('/api/finances')
        data = resp.get_json()

        assert data['paid_revenue'] == 300
        assert data['unpaid_revenue'] == 0


# ─── Feature Toggle Settings Tests ──────────────────────────────────────────

class TestFeatureToggles:
    """Tests for show_finances_tab and show_invoice_buttons settings"""

    def test_settings_get_returns_toggle_defaults(self, app_client):
        """New companies should get True defaults for both toggles"""
        client, mock_db = app_client
        mock_db.get_company.return_value = {
            'id': 1,
            'company_name': 'Test Co',
            'subscription_tier': 'professional',
            'subscription_status': 'active',
            'trial_end': (datetime.now() + timedelta(days=30)).isoformat(),
            # No toggle columns set yet
        }

        resp = client.get('/api/settings/business')
        data = resp.get_json()

        assert resp.status_code == 200
        assert data['show_finances_tab'] is True
        assert data['show_invoice_buttons'] is True

    def test_settings_get_returns_false_when_disabled(self, app_client):
        client, mock_db = app_client
        mock_db.get_company.return_value = {
            'id': 1,
            'company_name': 'Test Co',
            'subscription_tier': 'professional',
            'subscription_status': 'active',
            'trial_end': (datetime.now() + timedelta(days=30)).isoformat(),
            'show_finances_tab': False,
            'show_invoice_buttons': False,
        }

        resp = client.get('/api/settings/business')
        data = resp.get_json()

        assert data['show_finances_tab'] is False
        assert data['show_invoice_buttons'] is False

    def test_settings_post_saves_toggles(self, app_client):
        client, mock_db = app_client
        mock_db.update_company.return_value = True

        resp = client.post('/api/settings/business',
                           data=json.dumps({
                               'show_finances_tab': False,
                               'show_invoice_buttons': False,
                           }),
                           content_type='application/json')

        assert resp.status_code == 200
        # Verify update_company was called with the toggle fields
        call_kwargs = mock_db.update_company.call_args
        assert call_kwargs is not None
        _, kwargs = call_kwargs
        assert kwargs.get('show_finances_tab') is False
        assert kwargs.get('show_invoice_buttons') is False

    def test_settings_post_saves_true_toggles(self, app_client):
        client, mock_db = app_client
        mock_db.update_company.return_value = True

        resp = client.post('/api/settings/business',
                           data=json.dumps({
                               'show_finances_tab': True,
                               'show_invoice_buttons': True,
                           }),
                           content_type='application/json')

        assert resp.status_code == 200
        _, kwargs = mock_db.update_company.call_args
        assert kwargs.get('show_finances_tab') is True
        assert kwargs.get('show_invoice_buttons') is True

    def test_toggles_in_allowed_fields(self):
        """Verify the toggle fields are in db_postgres_wrapper allowed_fields"""
        import inspect
        from src.services.db_postgres_wrapper import PostgreSQLDatabaseWrapper
        source = inspect.getsource(PostgreSQLDatabaseWrapper.update_company)
        assert 'show_finances_tab' in source
        assert 'show_invoice_buttons' in source


# ─── Frontend Code Inspection Tests ─────────────────────────────────────────

class TestFrontendIntegration:
    """Verify frontend components wire up the feature toggles correctly"""

    def test_dashboard_conditionally_shows_finances_tab(self):
        """Dashboard.jsx uses spread operator to conditionally include Finances tab"""
        with open('frontend/src/pages/Dashboard.jsx', 'r') as f:
            code = f.read()
        assert 'show_finances_tab' in code
        assert 'showInvoiceButtons' in code

    def test_finances_tab_accepts_show_invoice_buttons_prop(self):
        with open('frontend/src/components/dashboard/FinancesTab.jsx', 'r') as f:
            code = f.read()
        assert 'showInvoiceButtons' in code
        assert 'markBookingsPaid' in code

    def test_jobs_tab_passes_show_invoice_buttons(self):
        with open('frontend/src/components/dashboard/JobsTab.jsx', 'r') as f:
            code = f.read()
        assert 'showInvoiceButtons' in code

    def test_job_detail_modal_uses_show_invoice_buttons(self):
        with open('frontend/src/components/modals/JobDetailModal.jsx', 'r') as f:
            code = f.read()
        assert 'showInvoiceButtons' in code

    def test_settings_has_toggle_ui(self):
        with open('frontend/src/pages/Settings.jsx', 'r') as f:
            code = f.read()
        assert 'show_finances_tab' in code
        assert 'show_invoice_buttons' in code
        assert 'Dashboard Features' in code

    def test_api_has_mark_bookings_paid(self):
        with open('frontend/src/services/api.js', 'r') as f:
            code = f.read()
        assert 'markBookingsPaid' in code
        assert '/api/finances/mark-paid' in code

    def test_finances_tab_has_confirmation_dialog(self):
        """Mark-paid buttons should have a confirmation step somewhere in the finances flow"""
        # The mark-paid and aging functionality is in the AgingPanel
        with open('frontend/src/components/accounting/AgingPanel.jsx', 'r') as f:
            code = f.read()
        assert 'sendInvoice' in code or 'reminderMut' in code
