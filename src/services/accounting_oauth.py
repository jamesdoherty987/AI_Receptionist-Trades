"""
OAuth2 flows for Xero and QuickBooks accounting integrations.
Follows the same pattern as google_calendar_oauth.py — stores tokens
in the companies table and handles refresh automatically.
"""
import os
import json
import logging
import time
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

import requests

from src.utils.config import config

logger = logging.getLogger(__name__)

# ─── In-memory state store (maps state → company_id) ───
_oauth_states: Dict[str, Tuple[int, float]] = {}
STATE_TTL = 600  # 10 minutes


def _clean_expired_states():
    now = time.time()
    expired = [k for k, (_, ts) in _oauth_states.items() if now - ts > STATE_TTL]
    for k in expired:
        del _oauth_states[k]


def _store_state(company_id: int) -> str:
    _clean_expired_states()
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = (company_id, time.time())
    return state


def _pop_state(state: str) -> Optional[int]:
    _clean_expired_states()
    entry = _oauth_states.pop(state, None)
    return entry[0] if entry else None


# ═══════════════════════════════════════════════════════════
#  XERO
# ═══════════════════════════════════════════════════════════

XERO_AUTH_URL = 'https://login.xero.com/identity/connect/authorize'
XERO_TOKEN_URL = 'https://identity.xero.com/connect/token'
XERO_CONNECTIONS_URL = 'https://api.xero.com/connections'
XERO_SCOPES = 'openid profile email accounting.transactions accounting.contacts offline_access'


def _get_xero_config():
    client_id = os.getenv('XERO_CLIENT_ID')
    client_secret = os.getenv('XERO_CLIENT_SECRET')
    if not client_id or not client_secret:
        raise ValueError("XERO_CLIENT_ID and XERO_CLIENT_SECRET must be set")
    return client_id, client_secret


def get_xero_redirect_uri() -> str:
    base = config.PUBLIC_URL or 'http://localhost:5000'
    return f"{base.rstrip('/')}/api/accounting/xero/callback"


def start_xero_oauth(company_id: int) -> str:
    client_id, _ = _get_xero_config()
    state = _store_state(company_id)
    redirect_uri = get_xero_redirect_uri()
    from urllib.parse import urlencode
    params = urlencode({
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': XERO_SCOPES,
        'state': state,
    })
    return f"{XERO_AUTH_URL}?{params}"


def handle_xero_callback(code: str, state: str, db) -> int:
    company_id = _pop_state(state)
    if not company_id:
        raise ValueError("Invalid or expired OAuth state")

    client_id, client_secret = _get_xero_config()
    redirect_uri = get_xero_redirect_uri()

    # Exchange code for tokens
    resp = requests.post(XERO_TOKEN_URL, data={
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret,
    }, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    resp.raise_for_status()
    tokens = resp.json()

    # Get tenant ID from connections endpoint
    conn_resp = requests.get(XERO_CONNECTIONS_URL, headers={
        'Authorization': f"Bearer {tokens['access_token']}",
        'Content-Type': 'application/json',
    })
    conn_resp.raise_for_status()
    connections = conn_resp.json()
    if not connections:
        raise ValueError("No Xero organisations found. Please connect at least one organisation in Xero.")

    tenant_id = connections[0]['tenantId']
    org_name = connections[0].get('tenantName', 'Xero Organisation')

    # Store credentials
    creds = {
        'access_token': tokens['access_token'],
        'refresh_token': tokens.get('refresh_token'),
        'expires_at': time.time() + tokens.get('expires_in', 1800),
        'token_type': tokens.get('token_type', 'Bearer'),
        'org_name': org_name,
    }

    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE companies SET
                xero_credentials_json = %s,
                xero_tenant_id = %s,
                accounting_provider = 'xero',
                accounting_sync_enabled = TRUE,
                last_accounting_sync = NOW()
            WHERE id = %s""",
            (json.dumps(creds), tenant_id, company_id)
        )
        conn.commit()
    finally:
        db.return_connection(conn)

    return company_id


def refresh_xero_token(company_id: int, db) -> Optional[str]:
    """Refresh Xero access token if expired. Returns valid access_token."""
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT xero_credentials_json, xero_tenant_id FROM companies WHERE id = %s",
            (company_id,)
        )
        row = cursor.fetchone()
    finally:
        db.return_connection(conn)

    if not row or not row.get('xero_credentials_json'):
        return None

    creds = json.loads(row['xero_credentials_json'])
    if time.time() < creds.get('expires_at', 0) - 60:
        return creds['access_token']

    # Refresh
    client_id, client_secret = _get_xero_config()
    resp = requests.post(XERO_TOKEN_URL, data={
        'grant_type': 'refresh_token',
        'refresh_token': creds['refresh_token'],
        'client_id': client_id,
        'client_secret': client_secret,
    })
    if resp.status_code != 200:
        logger.error(f"Xero token refresh failed: {resp.text}")
        return None

    tokens = resp.json()
    creds['access_token'] = tokens['access_token']
    creds['refresh_token'] = tokens.get('refresh_token', creds['refresh_token'])
    creds['expires_at'] = time.time() + tokens.get('expires_in', 1800)

    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE companies SET xero_credentials_json = %s WHERE id = %s",
            (json.dumps(creds), company_id)
        )
        conn.commit()
    finally:
        db.return_connection(conn)

    return creds['access_token']


def disconnect_xero(company_id: int, db):
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE companies SET
                xero_credentials_json = NULL,
                xero_tenant_id = NULL,
                accounting_provider = 'builtin',
                accounting_sync_enabled = FALSE
            WHERE id = %s""",
            (company_id,)
        )
        conn.commit()
    finally:
        db.return_connection(conn)


def get_xero_status(company_id: int, db) -> dict:
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """SELECT xero_credentials_json, xero_tenant_id,
                      accounting_provider, last_accounting_sync
               FROM companies WHERE id = %s""",
            (company_id,)
        )
        row = cursor.fetchone()
    finally:
        db.return_connection(conn)

    if not row or not row.get('xero_credentials_json'):
        return {'connected': False, 'provider': 'xero'}

    creds = json.loads(row['xero_credentials_json'])
    return {
        'connected': True,
        'provider': 'xero',
        'org_name': creds.get('org_name', ''),
        'tenant_id': row.get('xero_tenant_id'),
        'last_sync': row.get('last_accounting_sync').isoformat() if row.get('last_accounting_sync') else None,
    }


# ═══════════════════════════════════════════════════════════
#  QUICKBOOKS
# ═══════════════════════════════════════════════════════════

QB_AUTH_URL = 'https://appcenter.intuit.com/connect/oauth2'
QB_TOKEN_URL = 'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer'
QB_SCOPES = 'com.intuit.quickbooks.accounting'


def _get_quickbooks_config():
    client_id = os.getenv('QUICKBOOKS_CLIENT_ID')
    client_secret = os.getenv('QUICKBOOKS_CLIENT_SECRET')
    if not client_id or not client_secret:
        raise ValueError("QUICKBOOKS_CLIENT_ID and QUICKBOOKS_CLIENT_SECRET must be set")
    return client_id, client_secret


def get_quickbooks_redirect_uri() -> str:
    base = config.PUBLIC_URL or 'http://localhost:5000'
    return f"{base.rstrip('/')}/api/accounting/quickbooks/callback"


def start_quickbooks_oauth(company_id: int) -> str:
    client_id, _ = _get_quickbooks_config()
    state = _store_state(company_id)
    redirect_uri = get_quickbooks_redirect_uri()
    from urllib.parse import urlencode
    params = urlencode({
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': QB_SCOPES,
        'response_type': 'code',
        'state': state,
    })
    return f"{QB_AUTH_URL}?{params}"


def handle_quickbooks_callback(code: str, state: str, realm_id: str, db) -> int:
    company_id = _pop_state(state)
    if not company_id:
        raise ValueError("Invalid or expired OAuth state")

    client_id, client_secret = _get_quickbooks_config()
    redirect_uri = get_quickbooks_redirect_uri()

    import base64
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    resp = requests.post(QB_TOKEN_URL, data={
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
    }, headers={
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
    })
    resp.raise_for_status()
    tokens = resp.json()

    # Get company name from QuickBooks
    qb_base = os.getenv('QUICKBOOKS_API_BASE', 'https://quickbooks.api.intuit.com')
    company_name = 'QuickBooks Company'
    try:
        info_resp = requests.get(
            f"{qb_base}/v3/company/{realm_id}/companyinfo/{realm_id}",
            headers={
                'Authorization': f"Bearer {tokens['access_token']}",
                'Accept': 'application/json',
            }
        )
        if info_resp.status_code == 200:
            info = info_resp.json()
            company_name = info.get('CompanyInfo', {}).get('CompanyName', company_name)
    except Exception:
        pass

    creds = {
        'access_token': tokens['access_token'],
        'refresh_token': tokens.get('refresh_token'),
        'expires_at': time.time() + tokens.get('expires_in', 3600),
        'token_type': tokens.get('token_type', 'Bearer'),
        'company_name': company_name,
    }

    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE companies SET
                quickbooks_credentials_json = %s,
                quickbooks_realm_id = %s,
                accounting_provider = 'quickbooks',
                accounting_sync_enabled = TRUE,
                last_accounting_sync = NOW()
            WHERE id = %s""",
            (json.dumps(creds), realm_id, company_id)
        )
        conn.commit()
    finally:
        db.return_connection(conn)

    return company_id


def refresh_quickbooks_token(company_id: int, db) -> Optional[str]:
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT quickbooks_credentials_json, quickbooks_realm_id FROM companies WHERE id = %s",
            (company_id,)
        )
        row = cursor.fetchone()
    finally:
        db.return_connection(conn)

    if not row or not row.get('quickbooks_credentials_json'):
        return None

    creds = json.loads(row['quickbooks_credentials_json'])
    if time.time() < creds.get('expires_at', 0) - 60:
        return creds['access_token']

    client_id, client_secret = _get_quickbooks_config()
    import base64
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    resp = requests.post(QB_TOKEN_URL, data={
        'grant_type': 'refresh_token',
        'refresh_token': creds['refresh_token'],
    }, headers={
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
    })
    if resp.status_code != 200:
        logger.error(f"QuickBooks token refresh failed: {resp.text}")
        return None

    tokens = resp.json()
    creds['access_token'] = tokens['access_token']
    creds['refresh_token'] = tokens.get('refresh_token', creds['refresh_token'])
    creds['expires_at'] = time.time() + tokens.get('expires_in', 3600)

    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE companies SET quickbooks_credentials_json = %s WHERE id = %s",
            (json.dumps(creds), company_id)
        )
        conn.commit()
    finally:
        db.return_connection(conn)

    return creds['access_token']


def disconnect_quickbooks(company_id: int, db):
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE companies SET
                quickbooks_credentials_json = NULL,
                quickbooks_realm_id = NULL,
                accounting_provider = 'builtin',
                accounting_sync_enabled = FALSE
            WHERE id = %s""",
            (company_id,)
        )
        conn.commit()
    finally:
        db.return_connection(conn)


def get_quickbooks_status(company_id: int, db) -> dict:
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """SELECT quickbooks_credentials_json, quickbooks_realm_id,
                      accounting_provider, last_accounting_sync
               FROM companies WHERE id = %s""",
            (company_id,)
        )
        row = cursor.fetchone()
    finally:
        db.return_connection(conn)

    if not row or not row.get('quickbooks_credentials_json'):
        return {'connected': False, 'provider': 'quickbooks'}

    creds = json.loads(row['quickbooks_credentials_json'])
    return {
        'connected': True,
        'provider': 'quickbooks',
        'company_name': creds.get('company_name', ''),
        'realm_id': row.get('quickbooks_realm_id'),
        'last_sync': row.get('last_accounting_sync').isoformat() if row.get('last_accounting_sync') else None,
    }


# ═══════════════════════════════════════════════════════════
#  GENERIC HELPERS
# ═══════════════════════════════════════════════════════════

def get_accounting_status(company_id: int, db) -> dict:
    """Get the overall accounting integration status for a company."""
    conn = db.get_connection()
    try:
        from psycopg2.extras import RealDictCursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """SELECT accounting_provider, accounting_sync_enabled,
                      last_accounting_sync,
                      xero_credentials_json, xero_tenant_id,
                      quickbooks_credentials_json, quickbooks_realm_id
               FROM companies WHERE id = %s""",
            (company_id,)
        )
        row = cursor.fetchone()
    finally:
        db.return_connection(conn)

    if not row:
        return {'provider': 'builtin', 'connected': False}

    provider = row.get('accounting_provider') or 'builtin'
    result = {
        'provider': provider,
        'sync_enabled': row.get('accounting_sync_enabled', False),
        'last_sync': row['last_accounting_sync'].isoformat() if row.get('last_accounting_sync') else None,
    }

    if provider == 'xero' and row.get('xero_credentials_json'):
        creds = json.loads(row['xero_credentials_json'])
        result['connected'] = True
        result['org_name'] = creds.get('org_name', '')
    elif provider == 'quickbooks' and row.get('quickbooks_credentials_json'):
        creds = json.loads(row['quickbooks_credentials_json'])
        result['connected'] = True
        result['company_name'] = creds.get('company_name', '')
    else:
        result['connected'] = False

    return result


def set_accounting_provider(company_id: int, provider: str, db):
    """Switch accounting provider. 'builtin', 'xero', 'quickbooks', or 'disabled'."""
    valid = ('builtin', 'xero', 'quickbooks', 'disabled')
    if provider not in valid:
        raise ValueError(f"Invalid provider: {provider}. Must be one of {valid}")

    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE companies SET accounting_provider = %s WHERE id = %s",
            (provider, company_id)
        )
        conn.commit()
    finally:
        db.return_connection(conn)
