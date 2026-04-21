"""
Stripe Integration Service for Subscription Management
Handles customer creation, checkout sessions, webhooks, and subscription management
"""
import os
import stripe
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Initialize Stripe with API key
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Subscription configuration
TRIAL_DAYS = 14

# Plan definitions — two tiers
PLANS = {
    'dashboard': {
        'price_id': os.getenv('STRIPE_PRICE_ID_DASHBOARD'),
        'monthly_price_eur': float(os.getenv('DASHBOARD_MONTHLY_PRICE', '99')),
        'name': 'BookedForYou Dashboard',
        'description': 'Business Management Dashboard — Jobs, Scheduling, Invoicing & More',
    },
    'pro': {
        'price_id': os.getenv('STRIPE_PRICE_ID_PRO') or os.getenv('STRIPE_PRICE_ID'),
        'monthly_price_eur': float(os.getenv('PRO_MONTHLY_PRICE', '249')),
        'name': 'BookedForYou Pro',
        'description': 'AI Receptionist & Business Management — All Features',
    },
}

# Legacy fallback
SUBSCRIPTION_PRICE_ID = os.getenv('STRIPE_PRICE_ID')


def is_stripe_configured() -> bool:
    """Check if Stripe is properly configured"""
    # Re-read API key from environment if not set (handles late env loading)
    if not stripe.api_key:
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    return bool(stripe.api_key and stripe.api_key.startswith(('sk_test_', 'sk_live_')))


def get_or_create_customer(email: str, company_name: str, company_id: int) -> Optional[str]:
    """
    Get existing Stripe customer or create a new one
    Returns the Stripe customer ID
    """
    if not is_stripe_configured():
        print("⚠️ Stripe not configured")
        return None
    
    try:
        # Search for existing customer by email
        customers = stripe.Customer.list(email=email, limit=1)
        
        if customers.data:
            customer = customers.data[0]
            # Update metadata if needed
            stripe.Customer.modify(
                customer.id,
                metadata={'company_id': str(company_id), 'company_name': company_name}
            )
            return customer.id
        
        # Create new customer
        customer = stripe.Customer.create(
            email=email,
            name=company_name,
            metadata={
                'company_id': str(company_id),
                'company_name': company_name
            }
        )
        
        print(f"[SUCCESS] Created Stripe customer: {customer.id} for {email}")
        return customer.id
        
    except stripe.error.StripeError as e:
        print(f"[ERROR] Stripe error creating customer: {e}")
        return None


def create_checkout_session(
    company_id: int,
    email: str,
    company_name: str,
    success_url: str,
    cancel_url: str,
    with_trial: bool = True,
    plan: str = 'pro',
    custom_price_id: str = None
) -> Optional[Dict[str, str]]:
    """
    Create a Stripe Checkout Session for subscription.
    
    Args:
        company_id: The company's database ID
        email: Customer email
        company_name: Company name
        success_url: URL to redirect on successful payment
        cancel_url: URL to redirect on cancelled payment
        with_trial: Whether to include 14-day trial
        plan: 'dashboard' or 'pro'
        custom_price_id: Optional per-account Stripe price ID override
    
    Returns:
        Dict with 'session_id', 'url', 'customer_id', 'plan' or None on error
    """
    if not is_stripe_configured():
        return None
    
    if plan not in PLANS:
        print(f"[ERROR] Invalid plan: {plan}")
        return None
    
    plan_config = PLANS[plan]
    
    try:
        # Get or create customer
        customer_id = get_or_create_customer(email, company_name, company_id)
        
        if not customer_id:
            return None
        
        # Build session parameters
        session_params = {
            'customer': customer_id,
            'payment_method_types': ['card'],
            'mode': 'subscription',
            'success_url': success_url + '?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': cancel_url,
            'metadata': {
                'company_id': str(company_id),
                'plan': plan
            },
            'allow_promotion_codes': True,
            'billing_address_collection': 'required',
            'customer_update': {
                'address': 'auto',
                'name': 'auto'
            }
        }
        
        # Use custom price, existing price ID, or create inline price
        effective_price_id = custom_price_id or plan_config['price_id']
        if effective_price_id:
            session_params['line_items'] = [{
                'price': effective_price_id,
                'quantity': 1
            }]
        else:
            # Create inline price (useful for testing / before Stripe products are created)
            session_params['line_items'] = [{
                'price_data': {
                    'currency': 'eur',
                    'unit_amount': int(plan_config['monthly_price_eur'] * 100),
                    'recurring': {
                        'interval': 'month'
                    },
                    'product_data': {
                        'name': plan_config['name'],
                        'description': plan_config['description']
                    }
                },
                'quantity': 1
            }]
        
        # Always include subscription_data with metadata for webhook handling
        subscription_data = {
            'metadata': {
                'company_id': str(company_id),
                'plan': plan
            }
        }
        
        # Add trial period if requested
        if with_trial:
            subscription_data['trial_period_days'] = TRIAL_DAYS
        
        session_params['subscription_data'] = subscription_data
        
        session = stripe.checkout.Session.create(**session_params)
        
        print(f"[SUCCESS] Created checkout session: {session.id} for customer: {customer_id} (plan: {plan})")
        return {
            'session_id': session.id,
            'url': session.url,
            'customer_id': customer_id,
            'plan': plan
        }
        
    except stripe.error.StripeError as e:
        print(f"[ERROR] Stripe error creating checkout session: {e}")
        return None


def get_plan_from_price_id(price_id: str) -> str:
    """Map a Stripe price ID back to a plan name. Falls back to 'pro'."""
    if not price_id:
        return 'pro'
    for plan_name, config in PLANS.items():
        if config['price_id'] and config['price_id'] == price_id:
            return plan_name
    # Legacy: if the price_id matches the old STRIPE_PRICE_ID env var, it's pro
    if SUBSCRIPTION_PRICE_ID and price_id == SUBSCRIPTION_PRICE_ID:
        return 'pro'
    return 'pro'


def create_billing_portal_session(customer_id: str, return_url: str) -> Optional[str]:
    """
    Create a Stripe Customer Portal session for managing subscription
    
    Args:
        customer_id: Stripe customer ID
        return_url: URL to return to after portal session
    
    Returns:
        Portal session URL or None on error
    """
    if not is_stripe_configured() or not customer_id:
        return None
    
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url
        )
        
        return session.url
        
    except stripe.error.StripeError as e:
        print(f"[ERROR] Stripe error creating portal session: {e}")
        return None


def get_subscription_status(customer_id: str) -> Dict[str, Any]:
    """
    Get the current subscription status for a customer
    
    Returns:
        Dict with subscription details:
        - status: 'active', 'trialing', 'canceled', 'past_due', 'unpaid', 'none'
        - trial_end: datetime or None
        - current_period_end: datetime or None
        - cancel_at_period_end: bool
        - subscription_id: str or None
    """
    default_response = {
        'status': 'none',
        'trial_end': None,
        'current_period_end': None,
        'cancel_at_period_end': False,
        'subscription_id': None
    }
    
    if not is_stripe_configured() or not customer_id:
        return default_response
    
    try:
        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            status='all',
            limit=1
        )
        
        if not subscriptions.data:
            return default_response
        
        sub = subscriptions.data[0]
        
        return {
            'status': sub.status,
            'trial_end': datetime.fromtimestamp(sub.trial_end) if sub.trial_end else None,
            'current_period_end': datetime.fromtimestamp(sub.current_period_end) if sub.current_period_end else None,
            'cancel_at_period_end': sub.cancel_at_period_end,
            'subscription_id': sub.id
        }
        
    except stripe.error.StripeError as e:
        print(f"[ERROR] Stripe error getting subscription: {e}")
        return default_response


def upgrade_subscription(subscription_id: str, new_plan: str = 'pro', custom_price_id: str = None) -> Optional[Dict[str, Any]]:
    """
    Upgrade an existing subscription to a new plan by swapping the price.
    Prorates the charge immediately.
    """
    if not is_stripe_configured() or not subscription_id:
        return None

    if new_plan not in PLANS:
        print(f"[ERROR] Invalid plan for upgrade: {new_plan}")
        return None

    try:
        sub = stripe.Subscription.retrieve(subscription_id)
        if not sub or sub.status not in ('active', 'trialing'):
            print(f"[ERROR] Subscription {subscription_id} is not active (status={sub.status})")
            return None

        # Determine the new price ID
        new_price_id = custom_price_id or PLANS[new_plan]['price_id']
        if not new_price_id:
            print(f"[ERROR] No price ID configured for plan: {new_plan}")
            return None

        # Swap the first subscription item to the new price
        updated_sub = stripe.Subscription.modify(
            subscription_id,
            items=[{
                'id': sub['items']['data'][0].id,
                'price': new_price_id,
            }],
            proration_behavior='create_prorations',
            metadata={**dict(sub.metadata), 'plan': new_plan},
        )

        print(f"[SUCCESS] Upgraded subscription {subscription_id} to {new_plan}")
        return {
            'subscription_id': updated_sub.id,
            'plan': new_plan,
            'status': updated_sub.status,
        }

    except stripe.error.StripeError as e:
        print(f"[ERROR] Stripe error upgrading subscription: {e}")
        return None


def cancel_subscription(subscription_id: str, at_period_end: bool = True) -> bool:
    """
    Cancel a subscription
    
    Args:
        subscription_id: Stripe subscription ID
        at_period_end: If True, cancel at end of billing period. If False, cancel immediately.
    
    Returns:
        True if successful, False otherwise
    """
    if not is_stripe_configured() or not subscription_id:
        return False
    
    try:
        if at_period_end:
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
        else:
            stripe.Subscription.cancel(subscription_id)
        
        print(f"[SUCCESS] Cancelled subscription: {subscription_id}")
        return True
        
    except stripe.error.StripeError as e:
        print(f"[ERROR] Stripe error cancelling subscription: {e}")
        return False


def reactivate_subscription(subscription_id: str) -> bool:
    """
    Reactivate a subscription that was set to cancel at period end
    """
    if not is_stripe_configured() or not subscription_id:
        return False
    
    try:
        stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False
        )
        
        print(f"[SUCCESS] Reactivated subscription: {subscription_id}")
        return True
        
    except stripe.error.StripeError as e:
        print(f"[ERROR] Stripe error reactivating subscription: {e}")
        return False


def handle_webhook_event(payload: bytes, sig_header: str, webhook_secret: str) -> Dict[str, Any]:
    """
    Handle Stripe webhook events
    
    Args:
        payload: Raw request body
        sig_header: Stripe-Signature header
        webhook_secret: Webhook endpoint secret
    
    Returns:
        Dict with 'success' bool and 'event_type' or 'error'
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        return {'success': False, 'error': f'Invalid payload: {e}'}
    except stripe.error.SignatureVerificationError as e:
        return {'success': False, 'error': f'Invalid signature: {e}'}
    
    event_type = event['type']
    data = event['data']['object']
    
    print(f"[WEBHOOK] Received Stripe webhook: {event_type}")
    
    return {
        'success': True,
        'event_type': event_type,
        'data': data,
        'event_id': event['id']
    }


def get_customer_invoices(customer_id: str, limit: int = 10) -> list:
    """Get recent invoices for a customer"""
    if not is_stripe_configured() or not customer_id:
        return []
    
    try:
        invoices = stripe.Invoice.list(
            customer=customer_id,
            limit=limit
        )
        
        return [{
            'id': inv.id,
            'number': inv.number,
            'amount_paid': inv.amount_paid / 100,  # Convert from cents
            'currency': inv.currency.upper(),
            'status': inv.status,
            'created': datetime.fromtimestamp(inv.created),
            'invoice_pdf': inv.invoice_pdf,
            'hosted_invoice_url': inv.hosted_invoice_url
        } for inv in invoices.data]
        
    except stripe.error.StripeError as e:
        print(f"[ERROR] Stripe error getting invoices: {e}")
        return []
