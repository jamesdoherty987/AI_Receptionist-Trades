# Stripe Subscription Setup Guide

This guide explains how to set up Stripe for handling subscriptions in BookedForYou.

## Overview

BookedForYou offers two subscription options:
1. **14-Day Free Trial** - Full access to all features, no credit card required
2. **Pro Plan (€59/month)** - Continued access after trial ends

## Stripe Dashboard Setup

### Step 1: Create a Stripe Account

1. Go to [stripe.com](https://stripe.com) and sign up
2. Complete your business verification
3. Switch to **Live mode** when ready for production (use **Test mode** for development)

### Step 2: Get Your API Keys

1. Go to **Developers → API Keys**
2. Copy your **Secret key** (starts with `sk_test_` or `sk_live_`)
3. Add to your `.env` file:
   ```env
   STRIPE_SECRET_KEY=sk_test_your_key_here
   ```

### Step 3: Create a Product and Price (Optional but Recommended)

While the app can create prices dynamically, it's better to create them in Stripe Dashboard for better tracking:

1. Go to **Products → Add Product**
2. Create a product:
   - **Name**: `BookedForYou Pro`
   - **Description**: `AI Receptionist & Business Management - All Features`
3. Add a price:
   - **Pricing model**: Recurring
   - **Amount**: €59.00
   - **Billing period**: Monthly
4. Copy the **Price ID** (starts with `price_`)
5. Add to your `.env` file:
   ```env
   STRIPE_PRICE_ID=price_your_price_id_here
   ```

### Step 4: Set Up Webhooks

Webhooks notify your app when subscription events occur (payments, cancellations, etc.)

#### For Local Development (using Stripe CLI):

1. Install Stripe CLI:
   ```bash
   # Windows (with Chocolatey)
   choco install stripe-cli
   
   # macOS
   brew install stripe/stripe-cli/stripe
   
   # Or download from: https://stripe.com/docs/stripe-cli
   ```

2. Login to Stripe CLI:
   ```bash
   stripe login
   ```

3. Forward webhooks to your local server:
   ```bash
   stripe listen --forward-to localhost:5000/stripe/webhook
   ```

4. The CLI will display a webhook signing secret (starts with `whsec_`). Add it to your `.env`:
   ```env
   STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
   ```

#### For Production:

1. Go to **Developers → Webhooks → Add endpoint**
2. Enter your endpoint URL: `https://your-domain.com/stripe/webhook`
3. Select events to listen to:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
4. After creating, click on the endpoint and reveal the **Signing secret**
5. Add to your production environment:
   ```env
   STRIPE_WEBHOOK_SECRET=whsec_your_production_webhook_secret
   ```

### Step 5: Configure Customer Portal

The Customer Portal allows users to manage their subscription (update payment, cancel, view invoices):

1. Go to **Settings → Billing → Customer portal**
2. Configure the portal:
   - Enable **Invoices** - Allow customers to view invoices
   - Enable **Payment methods** - Allow customers to update payment
   - Enable **Cancel subscription** - Allow customers to cancel
   - Set **Cancellation policy** to "At end of billing period"
3. Save changes

### Step 6: Set Up Your Business Details

1. Go to **Settings → Business settings**
2. Add your:
   - Business name
   - Support email
   - Business address
   - Tax ID (if applicable)

## Environment Variables Summary

```env
# Required
STRIPE_SECRET_KEY=sk_test_or_sk_live_your_key

# Required for webhooks
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Optional (recommended for production)
STRIPE_PRICE_ID=price_your_price_id

# Frontend URL for redirects
FRONTEND_URL=http://localhost:5173  # Or your production URL
```

## Testing

### Test Cards

Use these test card numbers in test mode:

| Card Number | Description |
|-------------|-------------|
| `4242 4242 4242 4242` | Successful payment |
| `4000 0000 0000 3220` | 3D Secure authentication |
| `4000 0000 0000 9995` | Declined payment |

Use any future expiry date and any 3-digit CVC.

### Test Subscription Flow

1. Sign up for a new account (starts 14-day trial automatically)
2. Go to Settings → Subscription & Billing
3. Click "Subscribe Now"
4. Complete checkout with a test card
5. Verify subscription is active

### Test Webhook Events

With Stripe CLI running (`stripe listen`), you can trigger test events:

```bash
# Trigger a test checkout completion
stripe trigger checkout.session.completed

# Trigger subscription updated
stripe trigger customer.subscription.updated

# Trigger payment failed
stripe trigger invoice.payment_failed
```

## Subscription Flow

### New User Signup
1. User creates account
2. 14-day trial starts automatically
3. User gets full access to all features
4. Trial banner shows days remaining

### Trial Expiration
1. Trial banner becomes urgent at 3 days left
2. When trial expires, user is redirected to Settings
3. User must subscribe to continue using the app

### Subscription
1. User clicks "Subscribe Now"
2. Stripe Checkout handles payment securely
3. On success, subscription is activated
4. User redirected back to Settings with success message

### Cancellation
1. User clicks "Cancel Subscription"
2. Subscription continues until end of billing period
3. User can reactivate before period ends
4. After period ends, access is revoked

## Troubleshooting

### Checkout not working
- Verify `STRIPE_SECRET_KEY` is correct
- Check browser console for errors
- Ensure CORS is configured for your frontend URL

### Webhooks not received
- Verify `STRIPE_WEBHOOK_SECRET` matches your endpoint
- Check webhook logs in Stripe Dashboard → Developers → Webhooks → Logs
- Ensure your server is accessible (for production)

### Subscription status not updating
- Check webhook endpoint is responding with 200
- Verify the company_id is in the subscription metadata
- Check server logs for database errors

## Production Checklist

- [ ] Switch to Live mode API keys
- [ ] Create production webhook endpoint
- [ ] Test full subscription flow with real card
- [ ] Verify Customer Portal is configured
- [ ] Set up invoice emails in Stripe
- [ ] Configure tax settings if applicable
- [ ] Test cancellation and reactivation flow
