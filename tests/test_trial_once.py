"""
Tests for one-time trial enforcement.
Ensures a company can only use the free trial once.
"""
import os
import sys
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()


class TestGetSubscriptionInfoHasUsedTrial:
    """Test that get_subscription_info returns has_used_trial correctly"""

    def test_has_used_trial_false_by_default(self):
        from src.app import get_subscription_info

        company = {
            'subscription_tier': 'none',
            'subscription_status': 'inactive',
            'trial_start': None,
            'trial_end': None,
            'subscription_current_period_end': None,
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
        }
        info = get_subscription_info(company)
        assert info['has_used_trial'] is False

    def test_has_used_trial_false_when_zero(self):
        from src.app import get_subscription_info

        company = {
            'subscription_tier': 'none',
            'subscription_status': 'inactive',
            'trial_start': None,
            'trial_end': None,
            'has_used_trial': 0,
            'subscription_current_period_end': None,
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
        }
        info = get_subscription_info(company)
        assert info['has_used_trial'] is False

    def test_has_used_trial_true_when_set(self):
        from src.app import get_subscription_info

        company = {
            'subscription_tier': 'trial',
            'subscription_status': 'active',
            'trial_start': (datetime.now() - timedelta(days=20)).isoformat(),
            'trial_end': (datetime.now() - timedelta(days=6)).isoformat(),
            'has_used_trial': 1,
            'subscription_current_period_end': None,
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
        }
        info = get_subscription_info(company)
        assert info['has_used_trial'] is True

    def test_active_trial_with_has_used_trial_set(self):
        from src.app import get_subscription_info

        trial_end = datetime.now() + timedelta(days=10)
        company = {
            'subscription_tier': 'trial',
            'subscription_status': 'active',
            'trial_start': datetime.now().isoformat(),
            'trial_end': trial_end.isoformat(),
            'has_used_trial': 1,
            'subscription_current_period_end': None,
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
        }
        info = get_subscription_info(company)
        assert info['is_active'] is True
        assert info['has_used_trial'] is True


class TestStartTrialEndpoint:
    """Test the start-trial endpoint enforces one-time trial"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database"""
        mock = MagicMock()
        return mock

    @pytest.fixture
    def app_client(self, mock_db):
        """Create a test client with mocked database"""
        from src.app import app
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret'

        with patch('src.app.get_database', return_value=mock_db):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess['company_id'] = 1
                    sess['email'] = 'test@example.com'
                yield client

    def test_first_trial_succeeds(self, app_client, mock_db):
        """A company with no prior trial should be able to start one"""
        mock_db.get_company.return_value = {
            'id': 1,
            'email': 'test@example.com',
            'subscription_tier': 'none',
            'subscription_status': 'inactive',
            'trial_start': None,
            'trial_end': None,
            'has_used_trial': 0,
            'subscription_current_period_end': None,
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
        }

        response = app_client.post('/api/subscription/start-trial')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'trial_end' in data

        # Verify update_company was called with has_used_trial=1
        mock_db.update_company.assert_called_once()
        call_kwargs = mock_db.update_company.call_args
        assert call_kwargs[1]['has_used_trial'] == 1
        assert call_kwargs[1]['subscription_tier'] == 'trial'

    def test_second_trial_blocked(self, app_client, mock_db):
        """A company that already used the trial should be blocked"""
        mock_db.get_company.return_value = {
            'id': 1,
            'email': 'test@example.com',
            'subscription_tier': 'none',
            'subscription_status': 'inactive',
            'trial_start': (datetime.now() - timedelta(days=20)).isoformat(),
            'trial_end': (datetime.now() - timedelta(days=6)).isoformat(),
            'has_used_trial': 1,
            'subscription_current_period_end': None,
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
        }

        response = app_client.post('/api/subscription/start-trial')
        assert response.status_code == 400
        data = response.get_json()
        assert 'already been used' in data['error']
        mock_db.update_company.assert_not_called()

    def test_expired_trial_cannot_restart(self, app_client, mock_db):
        """An expired trial with has_used_trial=1 cannot be restarted"""
        mock_db.get_company.return_value = {
            'id': 1,
            'email': 'test@example.com',
            'subscription_tier': 'trial',
            'subscription_status': 'active',
            'trial_start': (datetime.now() - timedelta(days=20)).isoformat(),
            'trial_end': (datetime.now() - timedelta(days=6)).isoformat(),
            'has_used_trial': 1,
            'subscription_current_period_end': None,
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
        }

        response = app_client.post('/api/subscription/start-trial')
        assert response.status_code == 400
        data = response.get_json()
        assert 'already been used' in data['error']
        # update_company may be called to fix stale subscription_status,
        # but must NOT be called with trial-starting params
        for call in mock_db.update_company.call_args_list:
            kwargs = call[1] if call[1] else {}
            assert kwargs.get('subscription_tier') != 'trial', "Trial should not be restarted"

    def test_active_pro_cannot_start_trial(self, app_client, mock_db):
        """A pro user should not be able to start a trial"""
        mock_db.get_company.return_value = {
            'id': 1,
            'email': 'test@example.com',
            'subscription_tier': 'pro',
            'subscription_status': 'active',
            'trial_start': None,
            'trial_end': None,
            'has_used_trial': 0,
            'subscription_current_period_end': (datetime.now() + timedelta(days=30)).isoformat(),
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': 'cus_123',
            'stripe_subscription_id': 'sub_123',
        }

        response = app_client.post('/api/subscription/start-trial')
        assert response.status_code == 400
        data = response.get_json()
        assert 'Pro subscription' in data['error']
        mock_db.update_company.assert_not_called()

    def test_active_trial_cannot_start_another(self, app_client, mock_db):
        """A user with an active trial should not be able to start another"""
        mock_db.get_company.return_value = {
            'id': 1,
            'email': 'test@example.com',
            'subscription_tier': 'trial',
            'subscription_status': 'active',
            'trial_start': datetime.now().isoformat(),
            'trial_end': (datetime.now() + timedelta(days=10)).isoformat(),
            'has_used_trial': 1,
            'subscription_current_period_end': None,
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
        }

        response = app_client.post('/api/subscription/start-trial')
        assert response.status_code == 400
        mock_db.update_company.assert_not_called()
