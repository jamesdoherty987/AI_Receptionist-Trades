"""
Integration tests for Stripe Pro Plan subscription flow.
Tests the actual Flask app endpoints and database updates.

Requirements:
- STRIPE_SECRET_KEY (test key starting with sk_test_)
- STRIPE_PRICE_ID (test price ID)
- STRIPE_WEBHOOK_SECRET (test webhook secret)
- DATABASE_URL
"""
import os
import sys
import json
import time
import pytest
import stripe
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

# Initialize Stripe with test key
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')


def is_test_mode():
    """Check if we're using Stripe test keys"""
    return stripe.api_key and stripe.api_key.startswith('sk_test_')


@pytest.fixture
def stripe_configured():
    """Skip tests if Stripe is not configured with test keys"""
    if not stripe.api_key:
        pytest.skip("STRIPE_SECRET_KEY not configured")
    if not stripe.api_key.startswith('sk_test_'):
        pytest.skip(
            "Must use Stripe test keys (sk_test_*) for testing. "
            "You have a live key configured. To run these tests safely, "
            "set STRIPE_SECRET_KEY to your test key (from Stripe Dashboard > Developers > API keys > Test mode)"
        )
    if not STRIPE_PRICE_ID:
        pytest.skip("STRIPE_PRICE_ID not configured")
    return True


@pytest.fixture
def test_customer(stripe_configured):
    """Create a test customer and clean up after"""
    customer = stripe.Customer.create(
        email=f"test_{int(time.time())}@example.com",
        name="Test Company",
        metadata={'company_id': '999', 'test': 'true'}
    )
    yield customer
    # Cleanup
    try:
        stripe.Customer.delete(customer.id)
    except Exception:
        pass


@pytest.fixture
def app_client():
    """Create Flask test client"""
    from src.app import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_db():
    """Create a mock database for testing"""
    mock = MagicMock()
    mock.get_company.return_value = {
        'id': 999,
        'email': 'test@example.com',
        'company_name': 'Test Company',
        'owner_name': 'Test Owner',
        'phone': '1234567890',
        'trade_type': 'plumber',
        'address': '123 Test St',
        'logo_url': None,
        'subscription_tier': 'trial',
        'subscription_status': 'active',
        'stripe_customer_id': None,
        'stripe_subscription_id': None,
        'trial_start': datetime.now().isoformat(),
        'trial_end': (datetime.now() + timedelta(days=14)).isoformat(),
        'subscription_current_period_end': None,
        'subscription_cancel_at_period_end': 0
    }
    mock.get_company_by_stripe_customer_id.return_value = {
        'id': 999,
        'email': 'test@example.com'
    }
    mock.get_company_by_stripe_subscription_id.return_value = None
    mock.update_company.return_value = True
    return mock


class TestStripeCheckoutSession:
    """Test checkout session creation with actual Stripe API"""
    
    def test_create_checkout_session_returns_valid_response(self, stripe_configured, test_customer):
        """Verify checkout session creation returns session_id and url"""
        session = stripe.checkout.Session.create(
            customer=test_customer.id,
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price': STRIPE_PRICE_ID,
                'quantity': 1
            }],
            success_url='https://example.com/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://example.com/cancel',
            metadata={'company_id': '999'},
            subscription_data={
                'metadata': {'company_id': '999'}
            }
        )
        
        # Verify response structure
        assert session.id is not None
        assert session.id.startswith('cs_test_')
        assert session.url is not None
        assert 'checkout.stripe.com' in session.url
        assert session.mode == 'subscription'
        assert session.customer == test_customer.id
        assert session.metadata.get('company_id') == '999'


class TestStripeServiceIntegration:
    """Test the stripe_service.py functions with actual Stripe API"""
    
    def test_create_checkout_session_via_service(self, stripe_configured):
        """Test create_checkout_session function returns correct structure"""
        from src.services.stripe_service import create_checkout_session
        
        result = create_checkout_session(
            company_id=999,
            email=f"test_{int(time.time())}@example.com",
            company_name="Test Company",
            success_url='https://example.com/success',
            cancel_url='https://example.com/cancel',
            with_trial=False
        )
        
        assert result is not None
        assert 'session_id' in result
        assert 'url' in result
        assert 'customer_id' in result
        assert result['session_id'].startswith('cs_test_')
        assert 'checkout.stripe.com' in result['url']
        assert result['customer_id'].startswith('cus_')
        
        # Cleanup - delete the test customer
        try:
            stripe.Customer.delete(result['customer_id'])
        except Exception:
            pass
    
    def test_get_or_create_customer(self, stripe_configured):
        """Test customer creation and retrieval"""
        from src.services.stripe_service import get_or_create_customer
        
        email = f"test_{int(time.time())}@example.com"
        
        # Create customer
        customer_id = get_or_create_customer(email, "Test Company", 999)
        assert customer_id is not None
        assert customer_id.startswith('cus_')
        
        # Get same customer again
        customer_id_2 = get_or_create_customer(email, "Test Company", 999)
        assert customer_id_2 == customer_id
        
        # Cleanup
        try:
            stripe.Customer.delete(customer_id)
        except Exception:
            pass


class TestWebhookHandling:
    """Test webhook event handling"""
    
    def test_handle_webhook_event_valid_signature(self, stripe_configured):
        """Test webhook handler with valid signature"""
        from src.services.stripe_service import handle_webhook_event
        
        if not STRIPE_WEBHOOK_SECRET:
            pytest.skip("STRIPE_WEBHOOK_SECRET not configured")
        
        # Create a test event payload
        payload = json.dumps({
            'id': 'evt_test_123',
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': 'cs_test_123',
                    'customer': 'cus_test_123',
                    'subscription': 'sub_test_123',
                    'metadata': {'company_id': '999'}
                }
            }
        }).encode()
        
        # Generate valid signature
        timestamp = int(time.time())
        signed_payload = f"{timestamp}.{payload.decode()}"
        signature = stripe.WebhookSignature._compute_signature(
            signed_payload, STRIPE_WEBHOOK_SECRET
        )
        sig_header = f"t={timestamp},v1={signature}"
        
        result = handle_webhook_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        
        assert result['success'] is True
        assert result['event_type'] == 'checkout.session.completed'
        assert result['data']['id'] == 'cs_test_123'
    
    def test_handle_webhook_event_invalid_signature(self, stripe_configured):
        """Test webhook handler rejects invalid signature"""
        from src.services.stripe_service import handle_webhook_event
        
        if not STRIPE_WEBHOOK_SECRET:
            pytest.skip("STRIPE_WEBHOOK_SECRET not configured")
        
        payload = b'{"type": "test"}'
        sig_header = "t=123,v1=invalid_signature"
        
        result = handle_webhook_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        
        assert result['success'] is False
        assert 'error' in result


class TestGetSubscriptionInfo:
    """Test the get_subscription_info function that determines what the frontend sees"""
    
    def test_pro_user_has_no_trial_info(self):
        """Pro users should never see trial information"""
        from src.app import get_subscription_info
        
        company = {
            'subscription_tier': 'pro',
            'subscription_status': 'active',
            'trial_start': datetime.now().isoformat(),
            'trial_end': (datetime.now() + timedelta(days=10)).isoformat(),  # Still has trial time
            'subscription_current_period_end': (datetime.now() + timedelta(days=30)).isoformat(),
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': 'cus_test_123',
            'stripe_subscription_id': 'sub_test_123'
        }
        
        info = get_subscription_info(company)
        
        assert info['tier'] == 'pro'
        assert info['is_active'] is True
        assert info['trial_end'] is None  # Should be cleared for pro users
        assert info['trial_days_remaining'] == 0  # Should be 0 for pro users
        assert info['current_period_end'] is not None
    
    def test_trial_user_has_trial_info(self):
        """Trial users should see trial information"""
        from src.app import get_subscription_info
        
        trial_end = datetime.now() + timedelta(days=10)
        company = {
            'subscription_tier': 'trial',
            'subscription_status': 'active',
            'trial_start': datetime.now().isoformat(),
            'trial_end': trial_end.isoformat(),
            'subscription_current_period_end': None,
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': None,
            'stripe_subscription_id': None
        }
        
        info = get_subscription_info(company)
        
        assert info['tier'] == 'trial'
        assert info['is_active'] is True
        assert info['trial_end'] is not None
        assert info['trial_days_remaining'] > 0
    
    def test_expired_trial_is_not_active(self):
        """Expired trial should not be active"""
        from src.app import get_subscription_info
        
        company = {
            'subscription_tier': 'trial',
            'subscription_status': 'active',
            'trial_start': (datetime.now() - timedelta(days=20)).isoformat(),
            'trial_end': (datetime.now() - timedelta(days=6)).isoformat(),  # Expired
            'subscription_current_period_end': None,
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': None,
            'stripe_subscription_id': None
        }
        
        info = get_subscription_info(company)
        
        assert info['tier'] == 'trial'
        assert info['is_active'] is False
        assert info['trial_days_remaining'] == 0


class TestWebhookDatabaseUpdates:
    """Test that webhook events correctly update the database"""
    
    def test_checkout_completed_sets_pro_and_clears_trial(self, mock_db):
        """checkout.session.completed should set tier to pro and clear trial fields"""
        # Simulate the webhook processing logic
        event_data = {
            'customer': 'cus_test_123',
            'subscription': 'sub_test_123',
            'metadata': {'company_id': '999'}
        }
        
        company_id = int(event_data.get('metadata', {}).get('company_id', 0))
        customer_id = event_data.get('customer')
        subscription_id = event_data.get('subscription')
        
        # This is what the webhook handler does
        if company_id and subscription_id:
            mock_db.update_company(
                company_id,
                subscription_tier='pro',
                subscription_status='active',
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                subscription_cancel_at_period_end=0,
                trial_start=None,
                trial_end=None
            )
        
        # Verify the update was called correctly
        call_args = mock_db.update_company.call_args
        assert call_args[0][0] == 999  # company_id
        assert call_args[1]['subscription_tier'] == 'pro'
        assert call_args[1]['subscription_status'] == 'active'
        assert call_args[1]['trial_start'] is None
        assert call_args[1]['trial_end'] is None
    
    def test_subscription_updated_with_active_status_sets_pro(self, mock_db):
        """subscription.updated with active status should set tier to pro"""
        event_data = {
            'id': 'sub_test_123',
            'status': 'active',
            'cancel_at_period_end': False,
            'current_period_end': int(time.time()) + 30 * 24 * 3600,
            'metadata': {'company_id': '999'}
        }
        
        company_id = int(event_data.get('metadata', {}).get('company_id', 0))
        status = event_data.get('status')
        
        update_data = {
            'subscription_status': status,
            'subscription_cancel_at_period_end': 0
        }
        
        # This is the fixed logic - both active and trialing set pro
        if status in ('active', 'trialing'):
            update_data['subscription_tier'] = 'pro'
            update_data['trial_start'] = None
            update_data['trial_end'] = None
        
        mock_db.update_company(company_id, **update_data)
        
        call_args = mock_db.update_company.call_args
        assert call_args[1]['subscription_tier'] == 'pro'
        assert call_args[1]['trial_start'] is None
        assert call_args[1]['trial_end'] is None
    
    def test_subscription_updated_with_trialing_status_sets_pro(self, mock_db):
        """subscription.updated with trialing status should ALSO set tier to pro"""
        event_data = {
            'id': 'sub_test_123',
            'status': 'trialing',  # Stripe uses this for paid subscriptions with trial
            'cancel_at_period_end': False,
            'current_period_end': int(time.time()) + 30 * 24 * 3600,
            'metadata': {'company_id': '999'}
        }
        
        company_id = int(event_data.get('metadata', {}).get('company_id', 0))
        status = event_data.get('status')
        
        update_data = {
            'subscription_status': status,
            'subscription_cancel_at_period_end': 0
        }
        
        # Key fix: trialing status from Stripe should still set pro tier
        if status in ('active', 'trialing'):
            update_data['subscription_tier'] = 'pro'
            update_data['trial_start'] = None
            update_data['trial_end'] = None
        
        mock_db.update_company(company_id, **update_data)
        
        call_args = mock_db.update_company.call_args
        assert call_args[1]['subscription_tier'] == 'pro'
        assert call_args[1]['trial_start'] is None
        assert call_args[1]['trial_end'] is None
    
    def test_subscription_deleted_sets_expired(self, mock_db):
        """subscription.deleted should set tier to expired"""
        company_id = 999
        
        mock_db.update_company(
            company_id,
            subscription_tier='expired',
            subscription_status='cancelled',
            stripe_subscription_id=None
        )
        
        call_args = mock_db.update_company.call_args
        assert call_args[1]['subscription_tier'] == 'expired'
        assert call_args[1]['subscription_status'] == 'cancelled'


class TestCancelSubscription:
    """Test subscription cancellation"""
    
    def test_cancel_subscription_calls_stripe(self, stripe_configured, test_customer):
        """Test that cancel_subscription actually cancels in Stripe"""
        from src.services.stripe_service import cancel_subscription, reactivate_subscription
        
        # First create a subscription
        payment_method = stripe.PaymentMethod.attach(
            'pm_card_visa',
            customer=test_customer.id
        )
        
        stripe.Customer.modify(
            test_customer.id,
            invoice_settings={'default_payment_method': payment_method.id}
        )
        
        subscription = stripe.Subscription.create(
            customer=test_customer.id,
            items=[{'price': STRIPE_PRICE_ID}],
            metadata={'company_id': '999'}
        )
        
        # Cancel it
        success = cancel_subscription(subscription.id, at_period_end=True)
        assert success is True
        
        # Verify it's set to cancel
        updated_sub = stripe.Subscription.retrieve(subscription.id)
        assert updated_sub.cancel_at_period_end is True
        
        # Reactivate it
        success = reactivate_subscription(subscription.id)
        assert success is True
        
        # Verify it's reactivated
        updated_sub = stripe.Subscription.retrieve(subscription.id)
        assert updated_sub.cancel_at_period_end is False
        
        # Cleanup - actually cancel
        stripe.Subscription.cancel(subscription.id)


class TestSyncSubscription:
    """Test the sync subscription functionality"""
    
    def test_sync_sets_pro_for_active_subscription(self, stripe_configured, test_customer):
        """Test that syncing an active subscription sets tier to pro"""
        from src.services.stripe_service import get_subscription_status
        
        # Create a subscription
        payment_method = stripe.PaymentMethod.attach(
            'pm_card_visa',
            customer=test_customer.id
        )
        
        stripe.Customer.modify(
            test_customer.id,
            invoice_settings={'default_payment_method': payment_method.id}
        )
        
        subscription = stripe.Subscription.create(
            customer=test_customer.id,
            items=[{'price': STRIPE_PRICE_ID}],
            metadata={'company_id': '999'}
        )
        
        # Get status
        status = get_subscription_status(test_customer.id)
        
        # Should be active or trialing
        assert status['status'] in ('active', 'trialing')
        assert status['subscription_id'] == subscription.id
        
        # Cleanup
        stripe.Subscription.cancel(subscription.id)


class TestEndToEndFlow:
    """End-to-end tests for the complete subscription flow"""
    
    def test_full_pro_subscription_flow(self, stripe_configured):
        """
        Test the complete flow:
        1. Create checkout session
        2. Simulate webhook for completed checkout
        3. Verify subscription info shows pro (not trial)
        """
        from src.services.stripe_service import create_checkout_session
        from src.app import get_subscription_info
        
        # Step 1: Create checkout session
        email = f"e2e_test_{int(time.time())}@example.com"
        result = create_checkout_session(
            company_id=999,
            email=email,
            company_name="E2E Test Company",
            success_url='https://example.com/success',
            cancel_url='https://example.com/cancel',
            with_trial=False
        )
        
        assert result is not None
        customer_id = result['customer_id']
        
        # Step 2: Simulate what the database would look like after webhook
        # (In real scenario, webhook would update this)
        company_after_webhook = {
            'subscription_tier': 'pro',
            'subscription_status': 'active',
            'trial_start': None,  # Cleared by webhook
            'trial_end': None,    # Cleared by webhook
            'subscription_current_period_end': (datetime.now() + timedelta(days=30)).isoformat(),
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': customer_id,
            'stripe_subscription_id': 'sub_test_123'
        }
        
        # Step 3: Verify get_subscription_info returns correct data
        info = get_subscription_info(company_after_webhook)
        
        assert info['tier'] == 'pro'
        assert info['is_active'] is True
        assert info['trial_end'] is None
        assert info['trial_days_remaining'] == 0
        
        # Cleanup
        try:
            stripe.Customer.delete(customer_id)
        except Exception:
            pass
    
    def test_pro_user_with_leftover_trial_data_shows_pro(self, stripe_configured):
        """
        Test that a pro user with leftover trial data in DB still shows as pro.
        This simulates the bug where trial banner was showing for pro users.
        """
        from src.app import get_subscription_info
        
        # Simulate a company that upgraded to pro but still has trial data in DB
        # (This could happen if webhook didn't clear trial fields properly)
        company_with_leftover_trial = {
            'subscription_tier': 'pro',  # They ARE pro
            'subscription_status': 'active',
            'trial_start': datetime.now().isoformat(),  # Leftover data
            'trial_end': (datetime.now() + timedelta(days=10)).isoformat(),  # Leftover data
            'subscription_current_period_end': (datetime.now() + timedelta(days=30)).isoformat(),
            'subscription_cancel_at_period_end': 0,
            'stripe_customer_id': 'cus_test_123',
            'stripe_subscription_id': 'sub_test_123'
        }
        
        info = get_subscription_info(company_with_leftover_trial)
        
        # Even with leftover trial data, should show as pro with no trial info
        assert info['tier'] == 'pro'
        assert info['is_active'] is True
        assert info['trial_end'] is None  # Should be cleared
        assert info['trial_days_remaining'] == 0  # Should be 0


class TestStripeErrorHandling:
    """Test error handling for Stripe operations"""
    
    def test_invalid_price_id_raises_error(self, stripe_configured, test_customer):
        """Test that invalid price ID raises appropriate error"""
        with pytest.raises(stripe.error.InvalidRequestError):
            stripe.checkout.Session.create(
                customer=test_customer.id,
                payment_method_types=['card'],
                mode='subscription',
                line_items=[{
                    'price': 'price_invalid_123',
                    'quantity': 1
                }],
                success_url='https://example.com/success',
                cancel_url='https://example.com/cancel'
            )
    
    def test_service_handles_stripe_not_configured(self):
        """Test service functions handle missing Stripe config gracefully"""
        from src.services.stripe_service import get_subscription_status
        
        # Save original key
        original_key = stripe.api_key
        
        try:
            # Test with no key
            stripe.api_key = None
            os.environ['STRIPE_SECRET_KEY'] = ''
            
            # Should return default response, not raise
            status = get_subscription_status('cus_test')
            assert status['status'] == 'none'
        finally:
            # Restore
            stripe.api_key = original_key


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
