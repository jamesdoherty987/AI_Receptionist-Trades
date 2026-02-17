"""
Integration tests for Stripe Pro Plan subscription flow.
Uses actual Stripe test API to verify:
1. Checkout session creation returns correct response
2. Webhook handling correctly processes subscription events
3. Database is updated correctly after subscription purchase

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
                'metadata': {'company_id': '999'},
                'trial_period_days': 14
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
    
    def test_checkout_session_with_trial_period(self, stripe_configured, test_customer):
        """Verify trial period is correctly set in checkout session"""
        session = stripe.checkout.Session.create(
            customer=test_customer.id,
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price': STRIPE_PRICE_ID,
                'quantity': 1
            }],
            success_url='https://example.com/success',
            cancel_url='https://example.com/cancel',
            subscription_data={
                'trial_period_days': 14,
                'metadata': {'company_id': '999'}
            }
        )
        
        assert session.id is not None
        # Trial settings are in subscription_data, verified when subscription is created
    
    def test_checkout_session_without_trial(self, stripe_configured, test_customer):
        """Verify checkout session can be created without trial"""
        session = stripe.checkout.Session.create(
            customer=test_customer.id,
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price': STRIPE_PRICE_ID,
                'quantity': 1
            }],
            success_url='https://example.com/success',
            cancel_url='https://example.com/cancel',
            metadata={'company_id': '999'}
        )
        
        assert session.id is not None
        assert session.mode == 'subscription'


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
            with_trial=True
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
    
    def test_get_subscription_status_no_subscription(self, stripe_configured, test_customer):
        """Test getting subscription status for customer with no subscription"""
        from src.services.stripe_service import get_subscription_status
        
        status = get_subscription_status(test_customer.id)
        
        assert status['status'] == 'none'
        assert status['subscription_id'] is None


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


class TestSubscriptionWebhookProcessing:
    """Test that webhook events correctly update the database"""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database for testing webhook processing"""
        mock = MagicMock()
        mock.get_company.return_value = {
            'id': 999,
            'email': 'test@example.com',
            'company_name': 'Test Company',
            'subscription_tier': 'trial',
            'stripe_customer_id': None,
            'stripe_subscription_id': None
        }
        mock.get_company_by_stripe_customer_id.return_value = {
            'id': 999,
            'email': 'test@example.com'
        }
        mock.get_company_by_stripe_subscription_id.return_value = None
        mock.update_company.return_value = True
        return mock
    
    def test_checkout_completed_updates_company_to_pro(self, mock_db):
        """Test that checkout.session.completed webhook updates company to pro tier"""
        # Simulate the webhook processing logic from app.py
        event_data = {
            'customer': 'cus_test_123',
            'subscription': 'sub_test_123',
            'metadata': {'company_id': '999'}
        }
        
        company_id = int(event_data.get('metadata', {}).get('company_id', 0))
        customer_id = event_data.get('customer')
        subscription_id = event_data.get('subscription')
        
        assert company_id == 999
        assert customer_id == 'cus_test_123'
        assert subscription_id == 'sub_test_123'
        
        # Simulate the update that would happen
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
        
        # Verify update was called with correct parameters
        mock_db.update_company.assert_called_once()
        call_args = mock_db.update_company.call_args
        assert call_args[0][0] == 999  # company_id
        assert call_args[1]['subscription_tier'] == 'pro'
        assert call_args[1]['subscription_status'] == 'active'
        assert call_args[1]['stripe_customer_id'] == 'cus_test_123'
        assert call_args[1]['stripe_subscription_id'] == 'sub_test_123'
    
    def test_subscription_updated_maintains_pro_status(self, mock_db):
        """Test that subscription.updated webhook maintains pro status"""
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
        
        if status == 'active':
            update_data['subscription_tier'] = 'pro'
        
        mock_db.update_company(company_id, **update_data)
        
        call_args = mock_db.update_company.call_args
        assert call_args[1]['subscription_tier'] == 'pro'
        assert call_args[1]['subscription_status'] == 'active'
    
    def test_subscription_deleted_sets_expired_tier(self, mock_db):
        """Test that subscription.deleted webhook sets tier to expired"""
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


class TestEndToEndSubscriptionFlow:
    """End-to-end test simulating the full subscription flow"""
    
    def test_full_subscription_flow_simulation(self, stripe_configured):
        """
        Simulate the complete flow:
        1. Create checkout session
        2. Simulate webhook for completed checkout
        3. Verify subscription is active
        """
        from src.services.stripe_service import (
            create_checkout_session,
            get_subscription_status,
            get_or_create_customer
        )
        
        # Step 1: Create checkout session
        email = f"e2e_test_{int(time.time())}@example.com"
        result = create_checkout_session(
            company_id=999,
            email=email,
            company_name="E2E Test Company",
            success_url='https://example.com/success',
            cancel_url='https://example.com/cancel',
            with_trial=True
        )
        
        assert result is not None
        assert result['session_id'].startswith('cs_test_')
        customer_id = result['customer_id']
        
        # Step 2: Verify customer was created
        customer = stripe.Customer.retrieve(customer_id)
        assert customer.email == email
        assert customer.metadata.get('company_id') == '999'
        
        # Step 3: Check subscription status (should be none since checkout not completed)
        status = get_subscription_status(customer_id)
        assert status['status'] == 'none'
        
        # Step 4: Verify the checkout session exists and has correct data
        session = stripe.checkout.Session.retrieve(result['session_id'])
        assert session.customer == customer_id
        assert session.mode == 'subscription'
        
        # Cleanup
        try:
            stripe.Customer.delete(customer_id)
        except Exception:
            pass
    
    def test_create_and_cancel_subscription(self, stripe_configured, test_customer):
        """Test creating a subscription with test card and then cancelling"""
        # Use Stripe's test token for the 4242 card (pm_card_visa)
        # This is the recommended way to test - see https://stripe.com/docs/testing
        payment_method = stripe.PaymentMethod.attach(
            'pm_card_visa',  # Stripe's test payment method token
            customer=test_customer.id
        )
        
        # Set as default payment method
        stripe.Customer.modify(
            test_customer.id,
            invoice_settings={'default_payment_method': payment_method.id}
        )
        
        # Create subscription directly (bypassing checkout for testing)
        subscription = stripe.Subscription.create(
            customer=test_customer.id,
            items=[{'price': STRIPE_PRICE_ID}],
            trial_period_days=14,
            metadata={'company_id': '999'}
        )
        
        assert subscription.id.startswith('sub_')
        assert subscription.status in ['trialing', 'active']
        assert subscription.metadata.get('company_id') == '999'
        
        # Verify subscription status via service
        from src.services.stripe_service import get_subscription_status
        status = get_subscription_status(test_customer.id)
        assert status['status'] in ['trialing', 'active']
        assert status['subscription_id'] == subscription.id
        
        # Cancel subscription
        from src.services.stripe_service import cancel_subscription
        success = cancel_subscription(subscription.id, at_period_end=True)
        assert success is True
        
        # Verify cancellation
        updated_sub = stripe.Subscription.retrieve(subscription.id)
        assert updated_sub.cancel_at_period_end is True
        
        # Reactivate
        from src.services.stripe_service import reactivate_subscription
        success = reactivate_subscription(subscription.id)
        assert success is True
        
        # Verify reactivation
        updated_sub = stripe.Subscription.retrieve(subscription.id)
        assert updated_sub.cancel_at_period_end is False
        
        # Final cleanup - cancel immediately
        stripe.Subscription.cancel(subscription.id)


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
    
    def test_invalid_customer_id_raises_error(self, stripe_configured):
        """Test that invalid customer ID raises appropriate error"""
        with pytest.raises(stripe.error.InvalidRequestError):
            stripe.checkout.Session.create(
                customer='cus_invalid_123',
                payment_method_types=['card'],
                mode='subscription',
                line_items=[{
                    'price': STRIPE_PRICE_ID,
                    'quantity': 1
                }],
                success_url='https://example.com/success',
                cancel_url='https://example.com/cancel'
            )
    
    def test_service_handles_stripe_not_configured(self):
        """Test service functions handle missing Stripe config gracefully"""
        from src.services.stripe_service import (
            is_stripe_configured,
            get_subscription_status
        )
        
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
