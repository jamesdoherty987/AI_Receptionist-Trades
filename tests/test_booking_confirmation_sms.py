"""
Tests for booking confirmation SMS.
Covers:
  - send_booking_confirmation method (unit tests with mocked Twilio)
  - New customer booking triggers confirmation SMS
  - Returning customer booking triggers confirmation SMS
  - Missing phone number skips SMS gracefully
  - Twilio failure doesn't break the booking
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime


# ---------------------------------------------------------------------------
# Unit tests for send_booking_confirmation
# ---------------------------------------------------------------------------

class TestSendBookingConfirmation:
    """Test the send_booking_confirmation method on SMSReminderService."""

    def _make_service(self, client=None, from_number="+46764650412"):
        from src.services.sms_reminder import SMSReminderService
        svc = SMSReminderService.__new__(SMSReminderService)
        svc.client = client
        svc.from_number = from_number
        return svc

    def test_sends_sms_with_all_fields(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(sid="SM123")
        svc = self._make_service(client=mock_client)

        result = svc.send_booking_confirmation(
            to_number="0852635954",
            appointment_time=datetime(2026, 3, 25, 10, 0),
            customer_name="John Smith",
            service_type="Plumbing Repair",
            company_name="JP Plumbing",
            employee_names=["Mike", "Dave"],
            address="123 Main St, Dublin",
        )

        assert result is True
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "+353852635954" in call_kwargs["to"]
        assert "John Smith" in call_kwargs["body"]
        assert "Plumbing Repair" in call_kwargs["body"]
        assert "JP Plumbing" in call_kwargs["body"]
        assert "Mike" in call_kwargs["body"]
        assert "123 Main St" in call_kwargs["body"]
        assert "confirmed" in call_kwargs["body"].lower()

    def test_sends_sms_minimal_fields(self):
        """New customer scenario — no employees, no address, no company name."""
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(sid="SM456")
        svc = self._make_service(client=mock_client)

        result = svc.send_booking_confirmation(
            to_number="0852635954",
            appointment_time=datetime(2026, 3, 26, 14, 30),
            customer_name="Jane Doe",
            service_type="General Appointment",
        )

        assert result is True
        body = mock_client.messages.create.call_args[1]["body"]
        assert "Jane Doe" in body
        assert "General Appointment" in body
        assert "Your service provider" in body  # default company name

    def test_returns_false_when_no_client(self):
        svc = self._make_service(client=None)
        result = svc.send_booking_confirmation(
            to_number="0852635954",
            appointment_time=datetime(2026, 3, 25, 10, 0),
            customer_name="Test",
        )
        assert result is False

    def test_returns_false_on_twilio_error(self):
        from twilio.base.exceptions import TwilioRestException
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = TwilioRestException(
            status=400, uri="/test", msg="Bad request"
        )
        svc = self._make_service(client=mock_client)

        result = svc.send_booking_confirmation(
            to_number="0852635954",
            appointment_time=datetime(2026, 3, 25, 10, 0),
            customer_name="Test",
        )
        assert result is False

    def test_returns_false_on_generic_error(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("network down")
        svc = self._make_service(client=mock_client)

        result = svc.send_booking_confirmation(
            to_number="0852635954",
            appointment_time=datetime(2026, 3, 25, 10, 0),
            customer_name="Test",
        )
        assert result is False


# ---------------------------------------------------------------------------
# Integration: book_job triggers confirmation SMS
# ---------------------------------------------------------------------------

class TestBookJobSendsConfirmation:
    """Verify book_job calls send_booking_confirmation for new & returning customers."""

    def _make_services(self, has_employees=False, company_name="Test Co"):
        mock_cal = MagicMock()
        mock_cal.check_availability.return_value = True
        mock_cal.book_appointment.return_value = {"id": "evt_1"}

        mock_db = MagicMock()
        mock_db.has_employees.return_value = has_employees
        mock_db.find_or_create_client.return_value = 42
        mock_db.add_booking.return_value = 100
        mock_db.get_company.return_value = {"company_name": company_name}
        mock_db.get_client.return_value = {"name": "Test", "email": None}

        if has_employees:
            mock_db.find_available_employees_for_slot.return_value = [
                {"id": 1, "name": "Employee A"}
            ]

        return {
            "google_calendar": mock_cal,
            "db": mock_db,
            "company_id": 1,
        }

    @patch("src.services.calendar_tools.match_service")
    @patch("src.utils.date_parser.parse_datetime")
    @patch("src.services.sms_reminder.get_sms_service")
    def test_new_customer_gets_confirmation_sms(self, mock_get_sms, mock_parse, mock_match):
        from src.services.calendar_tools import execute_tool_call

        mock_parse.return_value = datetime(2026, 3, 25, 10, 0)
        mock_match.return_value = {
            "matched_name": "Plumbing",
            "service": {"duration_minutes": 60, "employees_required": 1, "price": 100, "employee_restrictions": None},
        }

        mock_sms = MagicMock()
        mock_sms.client = True
        mock_get_sms.return_value = mock_sms

        services = self._make_services(has_employees=False, company_name="JP Plumbing")
        result = execute_tool_call("book_job", {
            "customer_name": "New Customer",
            "phone": "0852635954",
            "job_address": "456 Oak Ave, Dublin",
            "job_description": "fix leaky tap",
            "appointment_datetime": "Wednesday at 10am",
            "urgency_level": "scheduled",
        }, services)

        assert result["success"] is True
        mock_sms.send_booking_confirmation.assert_called_once()
        call_kwargs = mock_sms.send_booking_confirmation.call_args[1]
        assert call_kwargs["to_number"] == "0852635954"
        assert call_kwargs["customer_name"] == "New Customer"
        assert call_kwargs["company_name"] == "JP Plumbing"

    @patch("src.services.calendar_tools.match_service")
    @patch("src.utils.date_parser.parse_datetime")
    @patch("src.services.sms_reminder.get_sms_service")
    def test_returning_customer_gets_confirmation_sms(self, mock_get_sms, mock_parse, mock_match):
        from src.services.calendar_tools import execute_tool_call

        mock_parse.return_value = datetime(2026, 3, 25, 14, 0)
        mock_match.return_value = {
            "matched_name": "Electrical",
            "service": {"duration_minutes": 120, "employees_required": 1, "price": 200, "employee_restrictions": None},
        }

        mock_sms = MagicMock()
        mock_sms.client = True
        mock_get_sms.return_value = mock_sms

        services = self._make_services(has_employees=True, company_name="Sparks Electric")
        # Returning customer — find_or_create_client returns existing ID
        services["db"].find_or_create_client.return_value = 7

        result = execute_tool_call("book_job", {
            "customer_name": "Returning Customer",
            "phone": "0852635954",
            "job_address": "789 Elm St, Cork",
            "job_description": "rewire kitchen",
            "appointment_datetime": "Wednesday at 2pm",
            "urgency_level": "scheduled",
        }, services)

        assert result["success"] is True
        mock_sms.send_booking_confirmation.assert_called_once()
        call_kwargs = mock_sms.send_booking_confirmation.call_args[1]
        assert call_kwargs["customer_name"] == "Returning Customer"
        assert call_kwargs["company_name"] == "Sparks Electric"
        assert call_kwargs["employee_names"] == ["Employee A"]

    @patch("src.services.calendar_tools.match_service")
    @patch("src.utils.date_parser.parse_datetime")
    @patch("src.services.sms_reminder.get_sms_service")
    def test_no_phone_skips_sms(self, mock_get_sms, mock_parse, mock_match):
        """book_job requires phone, so missing phone returns an error before SMS is attempted."""
        from src.services.calendar_tools import execute_tool_call

        mock_parse.return_value = datetime(2026, 3, 25, 10, 0)
        mock_match.return_value = {
            "matched_name": "General",
            "service": {"duration_minutes": 60, "employees_required": 1, "price": 50, "employee_restrictions": None},
        }

        mock_sms = MagicMock()
        mock_sms.client = True
        mock_get_sms.return_value = mock_sms

        services = self._make_services()
        result = execute_tool_call("book_job", {
            "customer_name": "No Phone Person",
            "phone": None,
            "job_address": "1 Test Rd",
            "job_description": "general work",
            "appointment_datetime": "Wednesday at 10am",
            "urgency_level": "scheduled",
        }, services)

        # book_job requires phone — booking fails before SMS is ever attempted
        assert result["success"] is False
        mock_sms.send_booking_confirmation.assert_not_called()

    @patch("src.services.calendar_tools.match_service")
    @patch("src.utils.date_parser.parse_datetime")
    @patch("src.services.sms_reminder.get_sms_service")
    def test_sms_failure_doesnt_break_booking(self, mock_get_sms, mock_parse, mock_match):
        from src.services.calendar_tools import execute_tool_call

        mock_parse.return_value = datetime(2026, 3, 25, 10, 0)
        mock_match.return_value = {
            "matched_name": "General",
            "service": {"duration_minutes": 60, "employees_required": 1, "price": 50, "employee_restrictions": None},
        }

        mock_sms = MagicMock()
        mock_sms.client = True
        mock_sms.send_booking_confirmation.side_effect = RuntimeError("Twilio down")
        mock_get_sms.return_value = mock_sms

        services = self._make_services()
        result = execute_tool_call("book_job", {
            "customer_name": "Unlucky Person",
            "phone": "0852635954",
            "job_address": "1 Test Rd",
            "job_description": "general work",
            "appointment_datetime": "Wednesday at 10am",
            "urgency_level": "scheduled",
        }, services)

        # Booking succeeds even though SMS blew up
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Integration: book_appointment triggers confirmation SMS
# ---------------------------------------------------------------------------

class TestBookAppointmentSendsConfirmation:
    """Verify book_appointment calls send_booking_confirmation."""

    def _make_services(self, company_name="Salon Pro"):
        mock_cal = MagicMock()
        mock_cal.check_availability.return_value = True
        mock_cal.book_appointment.return_value = {"id": "evt_2"}

        mock_db = MagicMock()
        mock_db.has_employees.return_value = False
        mock_db.find_or_create_client.return_value = 55
        mock_db.add_booking.return_value = 200
        mock_db.get_company.return_value = {"company_name": company_name}

        return {
            "google_calendar": mock_cal,
            "db": mock_db,
            "company_id": 2,
        }

    @patch("src.services.calendar_tools.match_service")
    @patch("src.utils.date_parser.parse_datetime")
    @patch("src.services.sms_reminder.get_sms_service")
    def test_new_customer_appointment_confirmation(self, mock_get_sms, mock_parse, mock_match):
        from src.services.calendar_tools import execute_tool_call

        mock_parse.return_value = datetime(2026, 3, 26, 11, 0)
        mock_match.return_value = {
            "matched_name": "Haircut",
            "service": {"duration_minutes": 30, "employees_required": 1, "employee_restrictions": None},
        }

        mock_sms = MagicMock()
        mock_sms.client = True
        mock_get_sms.return_value = mock_sms

        services = self._make_services()
        result = execute_tool_call("book_appointment", {
            "customer_name": "New Salon Client",
            "phone": "0852635954",
            "appointment_datetime": "Thursday at 11am",
            "reason": "haircut",
        }, services)

        assert result["success"] is True
        mock_sms.send_booking_confirmation.assert_called_once()
        call_kwargs = mock_sms.send_booking_confirmation.call_args[1]
        assert call_kwargs["customer_name"] == "New Salon Client"
        assert call_kwargs["company_name"] == "Salon Pro"

    @patch("src.services.calendar_tools.match_service")
    @patch("src.utils.date_parser.parse_datetime")
    @patch("src.services.sms_reminder.get_sms_service")
    def test_returning_customer_appointment_confirmation(self, mock_get_sms, mock_parse, mock_match):
        from src.services.calendar_tools import execute_tool_call

        mock_parse.return_value = datetime(2026, 3, 26, 15, 0)
        mock_match.return_value = {
            "matched_name": "Colour",
            "service": {"duration_minutes": 90, "employees_required": 1, "employee_restrictions": None},
        }

        mock_sms = MagicMock()
        mock_sms.client = True
        mock_get_sms.return_value = mock_sms

        services = self._make_services()
        # Returning customer
        services["db"].find_or_create_client.return_value = 12

        result = execute_tool_call("book_appointment", {
            "customer_name": "Regular Client",
            "phone": "0852635954",
            "appointment_datetime": "Thursday at 3pm",
            "reason": "colour treatment",
        }, services)

        assert result["success"] is True
        mock_sms.send_booking_confirmation.assert_called_once()
        assert mock_sms.send_booking_confirmation.call_args[1]["customer_name"] == "Regular Client"
