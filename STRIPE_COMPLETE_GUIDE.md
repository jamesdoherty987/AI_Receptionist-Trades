# BookedForYou Complete Stripe Setup Guide

This guide covers everything you need to set up Stripe for:
1. **Your Platform Subscription** - Charging €59/month to your users
2. **Stripe Connect** - Enabling your users (tradespeople) to receive payments from their customers

---

## Part 1: Platform Subscription Setup (Your €59/Month Revenue)

### 1.1 Create a Stripe Account

1. Go to [https://dashboard.stripe.com/register](https://dashboard.stripe.com/register)
2. Create your account (use your business email)
3. Complete the business verification process

### 1.2 Get Your API Keys

1. In Stripe Dashboard, go to **Developers → API Keys**
2. You need two keys:
   - **Publishable key** (starts with `pk_test_` or `pk_live_`)
   - **Secret key** (starts with `sk_test_` or `sk_live_`)

⚠️ **Important**: Use `test` keys for development, `live` keys for production

### 1.3 Create Your Subscription Product

#### In Stripe Dashboard:

1. Go to **Products → Add Product**
2. Create your product:
   - **Name**: `BookedForYou Pro`
   - **Description**: `AI-powered receptionist service for tradespeople`
3. Add a price:
   - **Pricing model**: Recurring
   - **Amount**: €59.00
   - **Billing period**: Monthly
   - **Currency**: EUR
4. Click **Save product**
5. **Copy the Price ID** (looks like `price_1ABC...`)

### 1.4 Configure Environment Variables

Create or update your `.env` file:

```env
# Stripe Keys (use live keys for production)
STRIPE_SECRET_KEY=sk_live_your_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_live_your_publishable_key_here

# Price ID from step 1.3
STRIPE_PRICE_ID=price_your_price_id_here

# Webhook secret (set up in section 1.5)
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here

# Your frontend URL
FRONTEND_URL=https://your-app.com
```

### 1.5 Set Up Webhooks

Webhooks let Stripe notify your app about subscription events.

#### For Production:

1. Go to **Developers → Webhooks** in Stripe Dashboard
2. Click **Add endpoint**
3. **Endpoint URL**: `https://your-domain.com/stripe/webhook`
4. **Events to listen to** (click "Select events"):
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `invoice.payment_failed`
5. Click **Add endpoint**
6. **Copy the Signing secret** (starts with `whsec_`)
7. Add it to your `.env` as `STRIPE_WEBHOOK_SECRET`

#### For Local Development:

Use Stripe CLI to forward webhooks:

```bash
# Install Stripe CLI
# macOS: brew install stripe/stripe-cli/stripe
# Windows: scoop install stripe

# Login to your Stripe account
stripe login

# Forward webhooks to your local server
stripe listen --forward-to localhost:5000/stripe/webhook
```

The CLI will give you a webhook signing secret to use locally.

### 1.6 Test the Subscription Flow

1. Start your app locally
2. Go to Settings → Subscription
3. Click "Subscribe Now"
4. Use test card: `4242 4242 4242 4242`, any future date, any CVC
5. Complete the checkout
6. Verify you're redirected back and subscription is active

### 1.7 Production Checklist for Subscriptions

- [ ] Switch from test keys to live keys in production
- [ ] Update webhook endpoint URL in Stripe Dashboard
- [ ] Test with a real card (you can refund yourself)
- [ ] Set up email notifications in Stripe Dashboard
- [ ] Configure tax settings if required (Settings → Tax)

---

## Part 2: Stripe Connect Setup (Users Receive Payments)

Stripe Connect enables your users (the tradespeople) to receive payments directly from their customers.

### 2.1 Enable Stripe Connect

1. Go to [https://dashboard.stripe.com/connect/onboarding-options](https://dashboard.stripe.com/connect/onboarding-options)
2. Click **Get started with Connect**
3. Complete the Connect onboarding for your platform
4. You'll be asked about:
   - Business type (platform/marketplace)
   - How funds flow (customer pays → connected account)
   - Countries you'll operate in

### 2.2 Choose Account Type (Already Configured)

Your platform uses **Express accounts** which:
- ✅ Stripe handles identity verification
- ✅ Stripe provides a hosted dashboard
- ✅ Minimal integration work for you
- ✅ Best for trades/service businesses

### 2.3 Configure Connect Settings

1. Go to **Settings → Connect settings**
2. **Branding**:
   - Upload your logo
   - Set your brand color
   - This shows during user onboarding
3. **Payout settings**:
   - Configure default payout schedule
   - Usually "Standard" (automatic daily payouts)
4. **Capabilities to request**:
   - Card payments ✓
   - Bank transfers ✓ (optional)

### 2.4 Add Connect Webhook Endpoint

1. Go to **Developers → Webhooks**
2. Click **Add endpoint**
3. **Endpoint URL**: `https://your-domain.com/stripe/connect/webhook`
4. Under "Listen to", select **Events on connected accounts**
5. Select these events:
   - `account.updated`
   - `account.application.deauthorized`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `payout.paid`
   - `payout.failed`
6. Add the endpoint
7. Copy the webhook secret and add to `.env`:

```env
STRIPE_CONNECT_WEBHOOK_SECRET=whsec_your_connect_webhook_secret
```

### 2.5 Configure Redirect URLs

In **Settings → Connect settings → Redirects**:

Set these URLs (adjust for your domain):

- **Refresh URL**: `https://your-app.com/settings?connect=refresh`
- **Return URL**: `https://your-app.com/settings?connect=return`

These are used when users complete or abandon Stripe onboarding.

### 2.6 Environment Variables (Complete)

```env
# Platform Subscription
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_PUBLISHABLE_KEY=pk_live_xxx
STRIPE_PRICE_ID=price_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Stripe Connect (optional - uses same keys)
STRIPE_CONNECT_WEBHOOK_SECRET=whsec_xxx

# Optional: Platform fee (e.g., 0.02 = 2%)
STRIPE_PLATFORM_FEE_PERCENT=0.02

# Your URLs
FRONTEND_URL=https://your-app.com
```

---

## Part 3: How It All Works

### User Journey

#### New User Signs Up:
1. Creates account → 14-day free trial starts
2. After trial → Pays €59/month subscription
3. Goes to Settings → Receive Payments → Connects Stripe
4. Stripe verifies their identity (~5 minutes)
5. Now ready to receive payments!

#### Customer Pays an Invoice:
1. User sends invoice to their customer
2. Invoice contains Stripe payment link
3. Customer pays with card
4. Money goes to user's connected account
5. Stripe automatically deposits to their bank

### Money Flow Diagram

```
Customer → Pays Invoice → Stripe → Connected Account → User's Bank
                            ↓
                    (Optional Platform Fee)
                            ↓
                      Your Platform Account
```

---

## Part 4: Testing Stripe Connect

### Test the Connect Flow

1. Log in as a test user
2. Go to Settings → Receive Payments
3. Click "Connect with Stripe"
4. Use test data:
   - Phone: `000 000 0000`
   - SSN last 4: `0000`
   - Any test bank account
5. Complete onboarding
6. Status should show "Active"

### Test Payment to Connected Account

```bash
# In Stripe CLI or API:
stripe payment_intents create \
  --amount 5000 \
  --currency eur \
  --transfer_data[destination]=acct_connected_account_id \
  --confirm=true \
  --payment_method=pm_card_visa
```

### Test Cards

| Card Number | Description |
|-------------|-------------|
| 4242 4242 4242 4242 | Successful payment |
| 4000 0000 0000 0002 | Declined |
| 4000 0000 0000 3220 | 3D Secure required |

---

## Part 5: Going Live

### Pre-Launch Checklist

#### Stripe Dashboard
- [ ] Complete business verification
- [ ] Add bank account for payouts
- [ ] Switch to Live mode
- [ ] Copy Live API keys

#### Environment
- [ ] Update all `test` keys to `live` keys
- [ ] Update webhook endpoints with production URLs
- [ ] Test webhook connectivity

#### Connect
- [ ] Complete Connect onboarding
- [ ] Set up Connect branding (logo, colors)
- [ ] Configure payout schedules
- [ ] Test connected account creation with a real user

#### App
- [ ] Remove test mode indicators
- [ ] Update success/error messages
- [ ] Test complete flow with live card

### Switching to Live Mode

1. **Stripe Dashboard**: Toggle "Test mode" to off (top-right)
2. **Get Live Keys**: Developers → API Keys
3. **Update `.env`**:
   ```env
   STRIPE_SECRET_KEY=sk_live_xxx  # No more sk_test_!
   STRIPE_PUBLISHABLE_KEY=pk_live_xxx
   ```
4. **Update Webhooks**: Create new endpoints for live mode
5. **Deploy** your updated environment

---

## Part 6: Common Issues & Troubleshooting

### "Webhook signature verification failed"

**Cause**: Wrong webhook secret or payload modified

**Fix**:
1. Get fresh webhook secret from Stripe Dashboard
2. Ensure you're reading the raw request body
3. Check you're using the right secret (platform vs connect)

### "Account not yet ready for charges"

**Cause**: Connected account hasn't completed verification

**Fix**:
- Check `charges_enabled` in account status
- Direct user to complete onboarding
- Check `requirements.currently_due` for missing info

### "Transfer destination invalid"

**Cause**: Trying to transfer to an incomplete account

**Fix**:
- Verify the connected account ID exists
- Check the account is in your platform
- Ensure `payouts_enabled` is true

### Subscription not activating

**Cause**: Webhook not received or processed

**Fix**:
1. Check Stripe Dashboard → Webhooks → Recent events
2. Verify webhook secret is correct
3. Check your server logs for errors
4. Ensure endpoint returns 200 status

---

## Part 7: API Endpoints Reference

### Subscription Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/subscription/status` | GET | Get current subscription status |
| `/api/subscription/checkout` | POST | Create checkout session |
| `/api/subscription/manage` | POST | Get Stripe billing portal URL |
| `/stripe/webhook` | POST | Handle Stripe webhooks |

### Connect Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/connect/status` | GET | Get Connect account status |
| `/api/connect/create` | POST | Create Express account |
| `/api/connect/onboarding-link` | POST | Get onboarding URL |
| `/api/connect/dashboard-link` | POST | Get Express dashboard URL |
| `/api/connect/disconnect` | POST | Unlink account |
| `/api/connect/balance` | GET | Get account balance |
| `/api/connect/payouts` | GET | Get recent payouts |
| `/stripe/connect/webhook` | POST | Handle Connect webhooks |

---

## Part 8: Quick Reference

### Test Card Numbers
```
Success:         4242 4242 4242 4242
Decline:         4000 0000 0000 0002
3D Secure:       4000 0000 0000 3220
```

### Webhook Events to Handle

**Subscriptions:**
- `checkout.session.completed` - User completed checkout
- `customer.subscription.updated` - Subscription status changed
- `customer.subscription.deleted` - User cancelled
- `invoice.paid` - Payment successful
- `invoice.payment_failed` - Payment failed

**Connect:**
- `account.updated` - Connected account status changed
- `account.application.deauthorized` - User disconnected
- `payment_intent.succeeded` - Customer payment succeeded

### Key URLs

```
Stripe Dashboard:     https://dashboard.stripe.com
Connect Settings:     https://dashboard.stripe.com/settings/connect
API Keys:             https://dashboard.stripe.com/apikeys
Webhooks:             https://dashboard.stripe.com/webhooks
```

---

## Need Help?

- **Stripe Documentation**: https://stripe.com/docs
- **Connect Guide**: https://stripe.com/docs/connect
- **Stripe Support**: https://support.stripe.com

---

*Last updated: Created for BookedForYou platform*
