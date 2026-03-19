"""
Tests for SMS day-before reminder functionality.
Covers: send_day_before_reminder method, send_day_before_reminders scheduler function,
        and start_sms_reminder_scheduler.
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# send_day_before_reminder (instance method)
# ---------------------------------------------------------------------------

class TestSendDayBeforeReminder:
    """Tests for SMSReminderService.send_day_before_reminder"""

    def _make_service(self, client=True):
        """Create an SMSReminderService with mocked Twilio client."""
        with patch("src.services.sms_reminder.Client") as MockClient:
            from src.services.sms_reminder import SMSReminderService
            svc = SMSReminderService(
                account_sid="AC_TEST",
                auth_token="TOKEN",
                from_number="+15551234567",
            )
            if not client:
                svc.client = None
            return svc

    def test_basic_reminder_sent(self):
        svc = self._make_service()
        svc.client.messages.create = MagicMock(return_value=MagicMock(sid="SM123"))

        appt = datetime(2026, 3, 20, 10, 0)
        result = svc.send_day_before_reminder(
            to_number="+353851234567",
            appointment_time=appt,
            customer_name="John",
            service_type="Boiler Repair",
            company_name="ABC Plumbing",
        )

        assert result is True
        call_args = svc.client.messages.create.call_args
        body = call_args.kwargs["body"]
        assert "ABC Plumbing" in body
        assert "Boiler Repair" in body
        assert "John" in body
        assert "10:00 AM" in body

    def test_no_emojis_in_message(self):
        svc = self._make_service()
        svc.client.messages.create = MagicMock(return_value=MagicMock(sid="SM123"))

        appt = datetime(2026, 3, 20, 14, 30)
        svc.send_day_before_reminder(
            to_number="+353851234567",
            appointment_time=appt,
            customer_name="Jane",
            service_type="Drain Cleaning",
            company_name="FixIt Co",
            worker_names=["Mike"],
        )

        body = svc.client.messages.create.call_args.kwargs["body"]
        # No emojis anywhere
        for char in body:
            assert ord(char) < 0x1F600 or ord(char) > 0x1F64F, f"Found emoji: {char}"
        # Specifically no location/worker emojis
        assert "\U0001f4cd" not in body  # 📍
        assert "\U0001f477" not in body  # 👷

    def test_no_location_in_message(self):
        svc = self._make_service()
        svc.client.messages.create = MagicMock(return_value=MagicMock(sid="SM123"))

        appt = datetime(2026, 3, 20, 9, 0)
        svc.send_day_before_reminder(
            to_number="+353851234567",
            appointment_time=appt,
            customer_name="Jane",
            service_type="Painting",
            company_name="PaintPro",
        )

        body = svc.client.messages.create.call_args.kwargs["body"]
        assert "Location" not in body

    def test_worker_names_included(self):
        svc = self._make_service()
        svc.client.messages.create = MagicMock(return_value=MagicMock(sid="SM123"))

        appt = datetime(2026, 3, 20, 11, 0)
        svc.send_day_before_reminder(
            to_number="+353851234567",
            appointment_time=appt,
            customer_name="Tom",
            service_type="Plumbing",
            company_name="QuickFix",
            worker_names=["Alice", "Bob"],
        )

        body = svc.client.messages.create.call_args.kwargs["body"]
        assert "Alice, Bob" in body
        assert "Assigned:" in body

    def test_no_workers_omits_assigned_line(self):
        svc = self._make_service()
        svc.client.messages.create = MagicMock(return_value=MagicMock(sid="SM123"))

        appt = datetime(2026, 3, 20, 8, 0)
        svc.send_day_before_reminder(
            to_number="+353851234567",
            appointment_time=appt,
            customer_name="Sam",
        )

        body = svc.client.messages.create.call_args.kwargs["body"]
        assert "Assigned" not in body

    def test_default_company_name(self):
        svc = self._make_service()
        svc.client.messages.create = MagicMock(return_value=MagicMock(sid="SM123"))

        appt = datetime(2026, 3, 20, 8, 0)
        svc.send_day_before_reminder(
            to_number="+353851234567",
            appointment_time=appt,
            customer_name="Sam",
        )

        body = svc.client.messages.create.call_args.kwargs["body"]
        assert "Your service provider" in body

    def test_returns_false_when_no_client(self):
        svc = self._make_service(client=False)
        result = svc.send_day_before_reminder(
            to_number="+353851234567",
            appointment_time=datetime.now(),
            customer_name="X",
        )
        assert result is False

    def test_returns_false_on_twilio_error(self):
        from twilio.base.exceptions import TwilioRestException

        svc = self._make_service()
        svc.client.messages.create.side_effect = TwilioRestException(400, "http://x", msg="fail")

        result = svc.send_day_before_reminder(
            to_number="+353851234567",
            appointment_time=datetime.now(),
            customer_name="X",
        )
        assert result is False

    def test_cancel_reschedule_line_present(self):
        svc = self._make_service()
        svc.client.messages.create = MagicMock(return_value=MagicMock(sid="SM1"))

        svc.send_day_before_reminder(
            to_number="+353851234567",
            appointment_time=datetime(2026, 3, 20, 10, 0),
            customer_name="Pat",
        )

        body = svc.client.messages.create.call_args.kwargs["body"]
        assert "cancel or reschedule" in body.lower()


# ---------------------------------------------------------------------------
# send_day_before_reminders (module-level scheduler function)
# ---------------------------------------------------------------------------

class TestSendDayBeforeReminders:
    """Tests for the send_day_before_reminders() batch function."""

    def _mock_db_bookings(self, bookings):
        """Return a mock db whose connection returns the given bookings."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = bookings

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_db = MagicMock()
        mock_db.get_connection.return_value = mock_conn
        return mock_db

    @patch("src.services.sms_reminder.get_sms_service")
    @patch("src.services.database.get_database")
    def test_sends_reminders_for_tomorrows_bookings(self, mock_get_db, mock_get_sms):
        from src.services.sms_reminder import send_day_before_reminders

        tomorrow = datetime.now() + timedelta(days=1)
        appt_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)

        bookings = [
            {
                "id": 1,
                "appointment_time": appt_time,
                "service_type": "Boiler Repair",
                "phone_number": "+353851111111",
                "company_id": 1,
                "client_name": "John",
                "client_phone": "+353851111111",
                "company_name": "ABC Plumbing",
                "worker_names": ["Mike"],
            }
        ]

        mock_get_db.return_value = self._mock_db_bookings(bookings)

        mock_sms = MagicMock()
        mock_sms.client = True
        mock_sms.send_day_before_reminder.return_value = True
        mock_get_sms.return_value = mock_sms

        count = send_day_before_reminders()

        assert count == 1
        mock_sms.send_day_before_reminder.assert_called_once()
        call_kwargs = mock_sms.send_day_before_reminder.call_args.kwargs
        assert call_kwargs["customer_name"] == "John"
        assert call_kwargs["company_name"] == "ABC Plumbing"
        assert call_kwargs["service_type"] == "Boiler Repair"
        assert call_kwargs["worker_names"] == ["Mike"]
        assert "address" not in call_kwargs

    @patch("src.services.sms_reminder.get_sms_service")
    @patch("src.services.database.get_database")
    def test_skips_bookings_without_phone(self, mock_get_db, mock_get_sms):
        from src.services.sms_reminder import send_day_before_reminders

        bookings = [
            {
                "id": 2,
                "appointment_time": datetime.now() + timedelta(days=1),
                "service_type": "Cleaning",
                "phone_number": None,
                "company_id": 1,
                "client_name": "NoPhone",
                "client_phone": None,
                "company_name": "Co",
                "worker_names": [],
            }
        ]

        mock_get_db.return_value = self._mock_db_bookings(bookings)
        mock_sms = MagicMock()
        mock_sms.client = True
        mock_get_sms.return_value = mock_sms

        count = send_day_before_reminders()

        assert count == 0
        mock_sms.send_day_before_reminder.assert_not_called()

    @patch("src.services.sms_reminder.get_sms_service")
    @patch("src.services.database.get_database")
    def test_returns_zero_when_no_bookings(self, mock_get_db, mock_get_sms):
        from src.services.sms_reminder import send_day_before_reminders

        mock_get_db.return_value = self._mock_db_bookings([])
        mock_sms = MagicMock()
        mock_sms.client = True
        mock_get_sms.return_value = mock_sms

        count = send_day_before_reminders()
        assert count == 0

    @patch("src.services.sms_reminder.get_sms_service")
    @patch("src.services.database.get_database")
    def test_returns_zero_when_twilio_not_configured(self, mock_get_db, mock_get_sms):
        from src.services.sms_reminder import send_day_before_reminders

        mock_sms = MagicMock()
        mock_sms.client = None
        mock_get_sms.return_value = mock_sms

        count = send_day_before_reminders()
        assert count == 0

    @patch("src.services.sms_reminder.get_sms_service")
    @patch("src.services.database.get_database")
    def test_falls_back_to_client_phone(self, mock_get_db, mock_get_sms):
        from src.services.sms_reminder import send_day_before_reminders

        bookings = [
            {
                "id": 3,
                "appointment_time": datetime.now() + timedelta(days=1),
                "service_type": "Painting",
                "phone_number": None,
                "company_id": 1,
                "client_name": "Fallback",
                "client_phone": "+353859999999",
                "company_name": "PaintCo",
                "worker_names": [],
            }
        ]

        mock_get_db.return_value = self._mock_db_bookings(bookings)
        mock_sms = MagicMock()
        mock_sms.client = True
        mock_sms.send_day_before_reminder.return_value = True
        mock_get_sms.return_value = mock_sms

        count = send_day_before_reminders()
        assert count == 1
        assert mock_sms.send_day_before_reminder.call_args.kwargs["to_number"] == "+353859999999"

    @patch("src.services.sms_reminder.get_sms_service")
    @patch("src.services.database.get_database")
    def test_handles_string_appointment_time(self, mock_get_db, mock_get_sms):
        from src.services.sms_reminder import send_day_before_reminders

        bookings = [
            {
                "id": 4,
                "appointment_time": "2026-03-20 14:00:00",
                "service_type": "Electrical",
                "phone_number": "+353851234567",
                "company_id": 1,
                "client_name": "StrTime",
                "client_phone": None,
                "company_name": "ElecCo",
                "worker_names": None,
            }
        ]

        mock_get_db.return_value = self._mock_db_bookings(bookings)
        mock_sms = MagicMock()
        mock_sms.client = True
        mock_sms.send_day_before_reminder.return_value = True
        mock_get_sms.return_value = mock_sms

        count = send_day_before_reminders()
        assert count == 1
        appt = mock_sms.send_day_before_reminder.call_args.kwargs["appointment_time"]
        assert isinstance(appt, datetime)


# ---------------------------------------------------------------------------
# start_sms_reminder_scheduler
# ---------------------------------------------------------------------------

class TestStartSmsReminderScheduler:
    """Tests for the background scheduler thread."""

    @patch("src.services.sms_reminder.send_day_before_reminders")
    def test_scheduler_starts_daemon_thread(self, mock_send):
        from src.services.sms_reminder import start_sms_reminder_scheduler

        thread = start_sms_reminder_scheduler(check_hour=0)
        assert thread.daemon is True
        assert thread.is_alive()


# ---------------------------------------------------------------------------
# normalize_phone_number (used by the reminder)
# ---------------------------------------------------------------------------

class TestNormalizePhoneForReminder:
    def test_irish_local_number(self):
        from src.services.sms_reminder import normalize_phone_number
        assert normalize_phone_number("0851234567") == "+353851234567"

    def test_already_international(self):
        from src.services.sms_reminder import normalize_phone_number
        assert normalize_phone_number("+353851234567") == "+353851234567"

    def test_strips_whitespace_and_dashes(self):
        from src.services.sms_reminder import normalize_phone_number
        assert normalize_phone_number("085-123 4567") == "+353851234567"
