"""
Global test fixtures.

Auto-mock external services so no test can accidentally:
- Send real Twilio SMS (costs money per message)
- Call OpenAI API (costs money, adds 10s+ latency per test)
"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _block_real_sms():
    """Prevent any test from sending real Twilio SMS."""
    mock_sms = MagicMock()
    mock_sms.client = None  # Looks unconfigured → send methods return False
    with patch("src.services.sms_reminder.get_sms_service", return_value=mock_sms):
        yield mock_sms


@pytest.fixture(autouse=True)
def _block_real_openai():
    """Prevent tests from making real OpenAI API calls (client_description_generator)."""
    with patch("src.services.client_description_generator.update_client_description", return_value=True):
        yield
