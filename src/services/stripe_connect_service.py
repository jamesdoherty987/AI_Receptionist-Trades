"""
Stripe Connect Service for Platform Payments
Enables users (tradespeople) to receive payments from their customers
Uses Stripe Connect Express for simplified onboarding
"""
import os
import stripe
from datetime import datetime
from typing import Optional, Dict, Any

# Initialize Stripe with API key
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Platform fee percentage (optional - set to 0 for no platform fee)
PLATFORM_FEE_PERCENT = float(os.getenv('STRIPE_PLATFORM_FEE_PERCENT', '0'))

# Get the client ID for Connect OAuth (set in Stripe Dashboard)
STRIPE_CLIENT_ID = os.getenv('STRIPE_CLIENT_ID', '')


def is_connect_configured() -> bool:
    """Check if Stripe Connect is properly configured"""
    return bool(stripe.api_key and stripe.api_key.startswith(('sk_test_', 'sk_live_')))


def create_connect_account(
    company_id: int,
    email: str,
    company_name: str,
    country: str = 'IE'  # Default to Ireland
) -> Optional[Dict[str, Any]]:
    """
    Create a Stripe Connect Express account for a user
    
    Args:
        company_id: The company's database ID
        email: User's email
        company_name: Business name
        country: Two-letter country code (default: IE for Ireland)
    
    Returns:
        Dict with 'account_id' or None on error
    """
    if not is_connect_configured():
        print("⚠️ Stripe not configured")
        return None
    
    try:
        account = stripe.Account.create(
            type='express',  # Express accounts have simplified onboarding
            country=country,
            email=email,
            business_type='individual',  # Can be 'individual' or 'company'
            capabilities={
                'card_payments': {'requested': True},
                'transfers': {'requested': True},
            },
            business_profile={
                'name': company_name,
                'product_description': 'Trade services',
            },
            metadata={
                'company_id': str(company_id),
                'platform': 'BookedForYou'
            }
        )
        
        print(f"✅ Created Stripe Connect account: {account.id}")
        return {
            'account_id': account.id,
            'details_submitted': account.details_submitted,
            'charges_enabled': account.charges_enabled,
            'payouts_enabled': account.payouts_enabled
        }
        
    except stripe.error.StripeError as e:
        print(f"❌ Stripe Connect error: {e}")
        return None


def create_account_link(
    account_id: str,
    refresh_url: str,
    return_url: str
) -> Optional[str]:
    """
    Create an account link for onboarding flow
    This redirects the user to Stripe to complete their account setup
    
    Args:
        account_id: Stripe Connect account ID
        refresh_url: URL if the link expires (user needs new link)
        return_url: URL to return to after onboarding
    
    Returns:
        Onboarding URL or None on error
    """
    if not is_connect_configured():
        return None
    
    try:
        account_link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type='account_onboarding',
        )
        
        return account_link.url
        
    except stripe.error.StripeError as e:
        print(f"❌ Stripe error creating account link: {e}")
        return None


def create_login_link(account_id: str) -> Optional[str]:
    """
    Create a login link for the user to access their Stripe Express dashboard
    
    Args:
        account_id: Stripe Connect account ID
    
    Returns:
        Dashboard login URL or None on error
    """
    if not is_connect_configured() or not account_id:
        return None
    
    try:
        login_link = stripe.Account.create_login_link(account_id)
        return login_link.url
        
    except stripe.error.StripeError as e:
        print(f"❌ Stripe error creating login link: {e}")
        return None


def get_account_status(account_id: str) -> Dict[str, Any]:
    """
    Get the current status of a Connect account
    
    Returns:
        Dict with account status details
    """
    default_response = {
        'exists': False,
        'details_submitted': False,
        'charges_enabled': False,
        'payouts_enabled': False,
        'requirements': [],
        'currently_due': [],
        'errors': []
    }
    
    if not is_connect_configured() or not account_id:
        return default_response
    
    try:
        account = stripe.Account.retrieve(account_id)
        
        return {
            'exists': True,
            'details_submitted': account.details_submitted,
            'charges_enabled': account.charges_enabled,
            'payouts_enabled': account.payouts_enabled,
            'requirements': account.requirements.eventually_due if account.requirements else [],
            'currently_due': account.requirements.currently_due if account.requirements else [],
            'errors': [err.reason for err in (account.requirements.errors or [])] if account.requirements else [],
            'default_currency': account.default_currency,
            'country': account.country,
            'email': account.email
        }
        
    except stripe.error.StripeError as e:
        print(f"❌ Stripe error getting account: {e}")
        return default_response


def delete_connect_account(account_id: str) -> bool:
    """
    Delete a Connect account (for disconnecting)
    Note: This is usually not reversible
    
    Args:
        account_id: Stripe Connect account ID
    
    Returns:
        True if successful
    """
    if not is_connect_configured() or not account_id:
        return False
    
    try:
        # For Express accounts, we can't delete them, but we can reject the connection
        # The account will remain but not be connected to our platform
        account = stripe.Account.delete(account_id)
        print(f"✅ Deleted Connect account: {account_id}")
        return True
        
    except stripe.error.StripeError as e:
        print(f"❌ Stripe error deleting account: {e}")
        return False


def create_payment_intent_for_invoice(
    amount_cents: int,
    currency: str,
    connected_account_id: str,
    description: str,
    customer_email: str,
    metadata: Dict[str, str] = None,
    application_fee_percent: float = None
) -> Optional[Dict[str, Any]]:
    """
    Create a PaymentIntent for an invoice using the connected account
    
    Args:
        amount_cents: Amount in cents (e.g., 5000 for €50.00)
        currency: Currency code (e.g., 'eur')
        connected_account_id: The tradesperson's Stripe Connect account ID
        description: Description for the payment
        customer_email: Customer's email for receipt
        metadata: Additional metadata (e.g., invoice_id, booking_id)
        application_fee_percent: Optional platform fee percentage
    
    Returns:
        Dict with payment_intent details or None
    """
    if not is_connect_configured() or not connected_account_id:
        return None
    
    try:
        # Calculate application fee if specified
        application_fee_amount = None
        fee_percent = application_fee_percent if application_fee_percent is not None else PLATFORM_FEE_PERCENT
        if fee_percent > 0:
            application_fee_amount = int(amount_cents * (fee_percent / 100))
        
        # Create payment intent params
        intent_params = {
            'amount': amount_cents,
            'currency': currency.lower(),
            'description': description,
            'receipt_email': customer_email,
            'metadata': metadata or {},
            'automatic_payment_methods': {'enabled': True},
        }
        
        # Add application fee if any
        if application_fee_amount and application_fee_amount > 0:
            intent_params['application_fee_amount'] = application_fee_amount
        
        # Create the PaymentIntent on the connected account
        payment_intent = stripe.PaymentIntent.create(
            **intent_params,
            stripe_account=connected_account_id  # Charge goes to connected account
        )
        
        print(f"✅ Created PaymentIntent: {payment_intent.id} for connected account {connected_account_id}")
        
        return {
            'payment_intent_id': payment_intent.id,
            'client_secret': payment_intent.client_secret,
            'amount': amount_cents,
            'currency': currency,
            'status': payment_intent.status
        }
        
    except stripe.error.StripeError as e:
        print(f"❌ Stripe error creating payment intent: {e}")
        return None


def create_payment_link(
    amount_cents: int,
    currency: str,
    connected_account_id: str,
    product_name: str,
    description: str = None,
    metadata: Dict[str, str] = None,
    success_url: str = None,
    cancel_url: str = None
) -> Optional[Dict[str, Any]]:
    """
    Create a Stripe Payment Link for easy invoice payments
    The customer can click this link to pay
    
    Args:
        amount_cents: Amount in cents
        currency: Currency code
        connected_account_id: The tradesperson's Stripe Connect account ID
        product_name: Name shown on checkout
        description: Description of the service
        metadata: Additional metadata
        success_url: Redirect after successful payment
        cancel_url: Redirect if cancelled
    
    Returns:
        Dict with 'url' and 'id' or None
    """
    if not is_connect_configured() or not connected_account_id:
        return None
    
    try:
        # Create a price for this one-time payment
        price = stripe.Price.create(
            unit_amount=amount_cents,
            currency=currency.lower(),
            product_data={
                'name': product_name,
                'description': description or 'Service payment',
            },
            stripe_account=connected_account_id
        )
        
        # Create the payment link
        link_params = {
            'line_items': [{'price': price.id, 'quantity': 1}],
            'metadata': metadata or {},
        }
        
        if success_url:
            link_params['after_completion'] = {
                'type': 'redirect',
                'redirect': {'url': success_url}
            }
        
        payment_link = stripe.PaymentLink.create(
            **link_params,
            stripe_account=connected_account_id
        )
        
        print(f"✅ Created Payment Link: {payment_link.url}")
        
        return {
            'id': payment_link.id,
            'url': payment_link.url,
            'active': payment_link.active
        }
        
    except stripe.error.StripeError as e:
        print(f"❌ Stripe error creating payment link: {e}")
        return None


def get_account_balance(account_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the balance for a connected account
    
    Returns:
        Dict with balance information
    """
    if not is_connect_configured() or not account_id:
        return None
    
    try:
        balance = stripe.Balance.retrieve(stripe_account=account_id)
        
        # Format available and pending balances
        available = []
        pending = []
        
        for bal in balance.available:
            available.append({
                'amount': bal.amount / 100,  # Convert from cents
                'currency': bal.currency.upper()
            })
        
        for bal in balance.pending:
            pending.append({
                'amount': bal.amount / 100,
                'currency': bal.currency.upper()
            })
        
        return {
            'available': available,
            'pending': pending
        }
        
    except stripe.error.StripeError as e:
        print(f"❌ Stripe error getting balance: {e}")
        return None


def get_account_payouts(account_id: str, limit: int = 10) -> list:
    """
    Get recent payouts for a connected account
    
    Returns:
        List of payout objects
    """
    if not is_connect_configured() or not account_id:
        return []
    
    try:
        payouts = stripe.Payout.list(
            limit=limit,
            stripe_account=account_id
        )
        
        return [{
            'id': payout.id,
            'amount': payout.amount / 100,
            'currency': payout.currency.upper(),
            'status': payout.status,
            'arrival_date': datetime.fromtimestamp(payout.arrival_date).isoformat() if payout.arrival_date else None,
            'created': datetime.fromtimestamp(payout.created).isoformat()
        } for payout in payouts.data]
        
    except stripe.error.StripeError as e:
        print(f"❌ Stripe error getting payouts: {e}")
        return []


def handle_connect_webhook_event(event_type: str, data: Dict) -> Dict[str, Any]:
    """
    Handle Stripe Connect webhook events
    
    Args:
        event_type: The type of event
        data: Event data
    
    Returns:
        Dict with processing result
    """
    result = {
        'processed': False,
        'event_type': event_type,
        'action': None
    }
    
    try:
        if event_type == 'account.updated':
            # Connected account was updated (e.g., completed onboarding)
            account_id = data.get('id')
            details_submitted = data.get('details_submitted', False)
            charges_enabled = data.get('charges_enabled', False)
            payouts_enabled = data.get('payouts_enabled', False)
            
            result['processed'] = True
            result['action'] = 'update_account_status'
            result['account_id'] = account_id
            result['details_submitted'] = details_submitted
            result['charges_enabled'] = charges_enabled
            result['payouts_enabled'] = payouts_enabled
            
            print(f"📨 Account updated: {account_id} - charges: {charges_enabled}, payouts: {payouts_enabled}")
            
        elif event_type == 'account.application.deauthorized':
            # User disconnected their account from your platform
            account_id = data.get('id')
            result['processed'] = True
            result['action'] = 'disconnect_account'
            result['account_id'] = account_id
            
            print(f"📨 Account disconnected: {account_id}")
            
        elif event_type == 'payment_intent.succeeded':
            # A payment was successful (on a connected account)
            payment_intent_id = data.get('id')
            amount = data.get('amount', 0) / 100
            result['processed'] = True
            result['action'] = 'payment_received'
            result['payment_intent_id'] = payment_intent_id
            result['amount'] = amount
            
            print(f"📨 Payment succeeded: {payment_intent_id} - €{amount:.2f}")
            
        elif event_type == 'payout.paid':
            # A payout was sent to the connected account's bank
            payout_id = data.get('id')
            amount = data.get('amount', 0) / 100
            result['processed'] = True
            result['action'] = 'payout_completed'
            result['payout_id'] = payout_id
            result['amount'] = amount
            
            print(f"📨 Payout completed: {payout_id} - €{amount:.2f}")
    
    except Exception as e:
        print(f"❌ Error processing Connect webhook: {e}")
        result['error'] = str(e)
    
    return result
