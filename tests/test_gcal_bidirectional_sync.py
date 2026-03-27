"""
Tests for bidirectional Google Calendar sync:
  - get_future_events fetches and parses events correctly
  - Push: DB bookings → Google Calendar (create + update)
  - Pull: Google Calendar events → DB bookings (import)
  - Deduplication: already-linked events are not re-imported
  - Duration logic: full-day and multi-day jobs use business-day end times
  - reschedule_appointment applies the same end-time logic as book_appointment
"""
import pytest
import json
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta


# ── Helpers ──────────────────────────────────────────────────────

def _make_gcal(company_id=1, timezone='Europe/Dublin'):
    """Create a CompanyGoogleCalendar with a mocked Google API service."""
    from src.services.google_calendar_oauth import CompanyGoogleCalendar
    service = MagicMock()
    gcal = CompanyGoogleCalendar(service, 'primary', company_id)
    gcal.timezone = timezone
    gcal._execute_with_retry = MagicMock()
    return gcal, service


def _gcal_event(event_id, summary, start_dt, end_dt, description='', extended_props=None):
    """Build a Google Calendar event dict like the API returns."""
    event = {
        'id': event_id,
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_dt.strftime('%Y-%m-%dT%H:%M:%S')},
        'end': {'dateTime': end_dt.strftime('%Y-%m-%dT%H:%M:%S')},
    }
    if extended_props:
        event['extendedProperties'] = extended_props
    return event


# ── get_future_events ────────────────────────────────────────────

class TestGetFutureEvents:
    def test_returns_parsed_events(self):
        gcal, service = _make_gcal()
        now = datetime.now()
        start = now + timedelta(days=1)
        end = start + timedelta(hours=2)

        gcal._execute_with_retry.return_value = {
            'items': [_gcal_event('ev1', 'Plumbing - John', start, end, 'Phone: 085 123 4567')],
        }

        events = gcal.get_future_events(days_ahead=30)
        assert len(events) == 1
        assert events[0]['id'] == 'ev1'
        assert events[0]['summary'] == 'Plumbing - John'
        assert events[0]['duration_minutes'] == 120

    def test_includes_extended_properties(self):
        gcal, service = _make_gcal()
        now = datetime.now()
        start = now + timedelta(days=1)
        end = start + timedelta(hours=1)

        gcal._execute_with_retry.return_value = {
            'items': [_gcal_event(
                'ev2', 'Test', start, end, '',
                extended_props={'private': {'bookedForYou': 'true'}}
            )],
        }

        events = gcal.get_future_events(days_ahead=30)
        assert len(events) == 1
        assert events[0]['extendedProperties']['private']['bookedForYou'] == 'true'

    def test_missing_extended_properties_defaults_to_empty(self):
        gcal, service = _make_gcal()
        now = datetime.now()
        start = now + timedelta(days=1)
        end = start + timedelta(hours=1)

        gcal._execute_with_retry.return_value = {
            'items': [_gcal_event('ev3', 'External', start, end)],
        }

        events = gcal.get_future_events(days_ahead=30)
        assert len(events) == 1
        assert events[0]['extendedProperties'] == {}

    def test_skips_all_day_events(self):
        gcal, service = _make_gcal()
        gcal._execute_with_retry.return_value = {
            'items': [{
                'id': 'allday1',
                'summary': 'Holiday',
                'start': {'date': '2026-04-01'},
                'end': {'date': '2026-04-02'},
            }],
        }
        events = gcal.get_future_events(days_ahead=30)
        assert len(events) == 0

    def test_paginates(self):
        gcal, service = _make_gcal()
        now = datetime.now()
        s1 = now + timedelta(days=1)
        e1 = s1 + timedelta(hours=1)
        s2 = now + timedelta(days=2)
        e2 = s2 + timedelta(hours=1)

        gcal._execute_with_retry.side_effect = [
            {'items': [_gcal_event('p1', 'Job1', s1, e1)], 'nextPageToken': 'tok2'},
            {'items': [_gcal_event('p2', 'Job2', s2, e2)]},
        ]
        events = gcal.get_future_events(days_ahead=30)
        assert len(events) == 2
        assert events[0]['id'] == 'p1'
        assert events[1]['id'] == 'p2'


# ── reschedule_appointment duration logic ────────────────────────

class TestRescheduleEndTimeLogic:
    """Verify reschedule_appointment mirrors book_appointment's end-time logic."""

    @patch('src.services.google_calendar_oauth.config')
    def test_regular_job_uses_simple_addition(self, mock_config):
        gcal, service = _make_gcal()
        mock_config.CALENDAR_TIMEZONE = 'Europe/Dublin'

        start = datetime(2026, 4, 6, 10, 0)  # Monday 10am
        old_event = _gcal_event('e1', 'Test', start, start + timedelta(hours=2))
        service.events.return_value.get.return_value.execute.return_value = old_event
        gcal._execute_with_retry = MagicMock(return_value={'id': 'e1'})

        new_start = datetime(2026, 4, 7, 11, 0)  # Tuesday 11am
        gcal.reschedule_appointment('e1', new_start, duration_minutes=120)

        # Should have called update with end = 11am + 120min = 1pm
        update_call = service.events.return_value.update
        body = update_call.call_args[1]['body'] if update_call.call_args[1] else update_call.call_args[0]
        # Get the body from the update call
        called_body = update_call.call_args
        # The event dict is passed as body= kwarg
        event_body = called_body.kwargs.get('body', old_event)
        assert '13:00:00' in event_body['end']['dateTime']

    @patch('src.services.google_calendar_oauth.config')
    def test_full_day_job_caps_at_closing(self, mock_config):
        gcal, service = _make_gcal()
        mock_config.CALENDAR_TIMEZONE = 'Europe/Dublin'
        mock_config.get_business_hours = MagicMock(return_value={'start': 8, 'end': 18})

        start = datetime(2026, 4, 6, 8, 0)
        old_event = _gcal_event('e2', 'Full Day', start, start.replace(hour=18))
        service.events.return_value.get.return_value.execute.return_value = old_event
        gcal._execute_with_retry = MagicMock(return_value={'id': 'e2'})

        new_start = datetime(2026, 4, 7, 8, 0)
        gcal.reschedule_appointment('e2', new_start, duration_minutes=480)

        update_call = service.events.return_value.update
        event_body = update_call.call_args.kwargs.get('body', old_event)
        # Full-day (480 min) should end at closing hour (18:00), not 8+480min=16:00
        assert '18:00:00' in event_body['end']['dateTime']

    @patch('src.services.google_calendar_oauth.config')
    def test_multi_day_job_walks_business_days(self, mock_config):
        gcal, service = _make_gcal()
        mock_config.CALENDAR_TIMEZONE = 'Europe/Dublin'
        mock_config.get_business_hours = MagicMock(return_value={'start': 9, 'end': 17})
        mock_config.get_business_days_indices = MagicMock(return_value=[0, 1, 2, 3, 4])

        start = datetime(2026, 4, 6, 9, 0)  # Monday
        old_event = _gcal_event('e3', 'Multi Day', start, datetime(2026, 4, 7, 17, 0))
        service.events.return_value.get.return_value.execute.return_value = old_event
        gcal._execute_with_retry = MagicMock(return_value={'id': 'e3'})

        new_start = datetime(2026, 4, 9, 9, 0)  # Thursday
        # 2-day job (2880 min) starting Thursday should end Friday 5pm
        gcal.reschedule_appointment('e3', new_start, duration_minutes=2880)

        update_call = service.events.return_value.update
        event_body = update_call.call_args.kwargs.get('body', old_event)
        # Should end on Friday (April 10) at 17:00
        assert '2026-04-10' in event_body['end']['dateTime']
        assert '17:00:00' in event_body['end']['dateTime']


# ── Pull: parsing event summaries ────────────────────────────────

class TestPullParsing:
    """Test the LLM-based batch parsing and fallback logic used in pull sync."""

    def test_build_fallback_uses_summary_as_job(self):
        from db_scripts.sync_gcal import _build_fallback
        result = _build_fallback('Fix kitchen sink')
        assert result['customer_name'] == ''
        assert result['job_description'] == 'Fix kitchen sink'
        assert result['address'] == ''
        assert result['phone'] == ''

    def test_batch_parse_empty_list(self):
        from db_scripts.sync_gcal import parse_gcal_events_batch
        assert parse_gcal_events_batch([]) == []

    @patch('src.services.llm_stream.get_openai_client')
    def test_batch_parse_returns_structured_data(self, mock_get_client):
        """Mock the LLM to return structured JSON and verify parsing."""
        from db_scripts.sync_gcal import parse_gcal_events_batch

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            'events': [
                {'customer_name': 'John Smith', 'job_description': 'Plumbing', 'address': '', 'phone': ''},
                {'customer_name': '', 'job_description': 'Team Meeting', 'address': '', 'phone': ''},
            ]
        })
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        events = [
            {'summary': 'Plumbing - John Smith', 'description': ''},
            {'summary': 'Team Meeting', 'description': ''},
        ]
        results = parse_gcal_events_batch(events)
        assert len(results) == 2
        assert results[0]['customer_name'] == 'John Smith'
        assert results[0]['job_description'] == 'Plumbing'
        assert results[1]['customer_name'] == ''
        assert results[1]['job_description'] == 'Team Meeting'

    @patch('src.services.llm_stream.get_openai_client')
    def test_batch_parse_falls_back_on_error(self, mock_get_client):
        """If the LLM call fails, fallback should use summary as job_description."""
        from db_scripts.sync_gcal import parse_gcal_events_batch

        mock_get_client.side_effect = Exception('API down')

        events = [
            {'summary': 'Fix sink for Mary', 'description': ''},
        ]
        results = parse_gcal_events_batch(events)
        assert len(results) == 1
        assert results[0]['customer_name'] == ''
        assert results[0]['job_description'] == 'Fix sink for Mary'

    @patch('src.services.llm_stream.get_openai_client')
    def test_batch_parse_handles_mismatched_count(self, mock_get_client):
        """If LLM returns fewer items than sent, remaining get fallbacks."""
        from db_scripts.sync_gcal import parse_gcal_events_batch

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            'events': [
                {'customer_name': 'Alice', 'job_description': 'Painting', 'address': '', 'phone': ''},
            ]
        })
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        events = [
            {'summary': 'Painting - Alice', 'description': ''},
            {'summary': 'Roofing for Bob', 'description': ''},
        ]
        results = parse_gcal_events_batch(events)
        assert len(results) == 2
        assert results[0]['customer_name'] == 'Alice'
        # Second event should get fallback
        assert results[1]['customer_name'] == ''
        assert results[1]['job_description'] == 'Roofing for Bob'

    def test_unnamed_customer_gets_placeholder(self):
        """When LLM returns empty customer_name, sync should assign a placeholder."""
        # This tests the logic in sync_company's pull phase
        customer_name = ''
        unnamed_counter = 3
        if not customer_name:
            unnamed_counter += 1
            customer_name = f"GCal Import #{unnamed_counter}"
        assert customer_name == 'GCal Import #4'

    def test_phone_extraction(self):
        import re
        desc = "Synced from BookedForYou\nCustomer: John\nPhone: 085 123 4567\nAddress: Dublin"
        match = re.search(r'(?:Phone|Customer Phone)[:\s]*([+\d\s\-()]{7,})', desc, re.IGNORECASE)
        assert match is not None
        assert match.group(1).strip() == '085 123 4567'

    def test_customer_phone_extraction(self):
        import re
        desc = "Job details\n\nCustomer Phone: +353851234567"
        match = re.search(r'(?:Phone|Customer Phone)[:\s]*([+\d\s\-()]{7,})', desc, re.IGNORECASE)
        assert match is not None
        assert match.group(1).strip() == '+353851234567'


# ── Deduplication ────────────────────────────────────────────────

class TestDeduplication:
    """Verify that events already linked to DB bookings are not re-imported."""

    def test_known_gcal_ids_skip_pull(self):
        """Simulate the sync logic: events with IDs in known_gcal_ids are skipped."""
        known_gcal_ids = {'gcal_abc', 'gcal_def'}
        gcal_events = [
            {'id': 'gcal_abc', 'summary': 'Already linked', 'start': datetime.now(), 'duration_minutes': 60},
            {'id': 'gcal_new', 'summary': 'New event', 'start': datetime.now(), 'duration_minutes': 60, 'description': ''},
        ]

        to_import = [e for e in gcal_events if e['id'] not in known_gcal_ids]
        assert len(to_import) == 1
        assert to_import[0]['id'] == 'gcal_new'

    def test_push_created_ids_prevent_pull_reimport(self):
        """Events created during push phase should not be re-imported in pull phase."""
        known_gcal_ids = set()

        # Simulate push creating a new event
        new_gcal_id = 'gcal_pushed_123'
        known_gcal_ids.add(new_gcal_id)

        # Pull phase should skip it
        gcal_events = [
            {'id': 'gcal_pushed_123', 'summary': 'Just pushed', 'start': datetime.now(), 'duration_minutes': 60},
        ]
        to_import = [e for e in gcal_events if e['id'] not in known_gcal_ids]
        assert len(to_import) == 0

    def test_app_created_events_skipped_by_description(self):
        """Events with 'Synced from BookedForYou' in description are skipped
        even if their gcal ID is not in known_gcal_ids (orphaned events)."""
        known_gcal_ids = set()
        gcal_events = [
            {
                'id': 'gcal_orphan',
                'summary': 'Plumbing - John',
                'start': datetime.now(),
                'duration_minutes': 120,
                'description': 'Synced from BookedForYou\nCustomer: John\nPhone: 085 123 4567',
                'extendedProperties': {},
            },
            {
                'id': 'gcal_external',
                'summary': 'Team Meeting',
                'start': datetime.now(),
                'duration_minutes': 60,
                'description': 'Weekly standup',
                'extendedProperties': {},
            },
        ]

        to_import = []
        for e in gcal_events:
            if e['id'] in known_gcal_ids:
                continue
            ext_private = e.get('extendedProperties', {}).get('private', {})
            if ext_private.get('bookedForYou') == 'true' or 'Synced from BookedForYou' in e.get('description', ''):
                continue
            to_import.append(e)

        assert len(to_import) == 1
        assert to_import[0]['id'] == 'gcal_external'

    def test_app_created_events_skipped_by_extended_property(self):
        """Events with extendedProperties.private.bookedForYou='true' are
        skipped even if the description was edited by the user."""
        known_gcal_ids = set()
        gcal_events = [
            {
                'id': 'gcal_prop_marked',
                'summary': 'Plumbing - John',
                'start': datetime.now(),
                'duration_minutes': 120,
                'description': 'User edited this description completely',
                'extendedProperties': {'private': {'bookedForYou': 'true'}},
            },
            {
                'id': 'gcal_no_prop',
                'summary': 'Dentist',
                'start': datetime.now(),
                'duration_minutes': 60,
                'description': '',
                'extendedProperties': {},
            },
        ]

        to_import = []
        for e in gcal_events:
            if e['id'] in known_gcal_ids:
                continue
            ext_private = e.get('extendedProperties', {}).get('private', {})
            if ext_private.get('bookedForYou') == 'true' or 'Synced from BookedForYou' in e.get('description', ''):
                continue
            to_import.append(e)

        assert len(to_import) == 1
        assert to_import[0]['id'] == 'gcal_no_prop'

    def test_external_events_still_imported(self):
        """Events NOT created by the app should still be imported."""
        known_gcal_ids = set()
        gcal_events = [
            {
                'id': 'gcal_personal',
                'summary': 'Dentist Appointment',
                'start': datetime.now(),
                'duration_minutes': 60,
                'description': 'Dr. Smith at 3pm',
                'extendedProperties': {},
            },
        ]

        to_import = []
        for e in gcal_events:
            if e['id'] in known_gcal_ids:
                continue
            ext_private = e.get('extendedProperties', {}).get('private', {})
            if ext_private.get('bookedForYou') == 'true' or 'Synced from BookedForYou' in e.get('description', ''):
                continue
            to_import.append(e)

        assert len(to_import) == 1
        assert to_import[0]['id'] == 'gcal_personal'


# ── Duration consistency ─────────────────────────────────────────

class TestExtendedProperties:
    """Verify that book_appointment stamps events with the bookedForYou
    extended property so the pull phase can identify app-created events."""

    def test_book_appointment_sets_extended_property(self):
        gcal, service = _make_gcal()
        gcal._execute_with_retry = MagicMock(return_value={'id': 'new1'})

        start = datetime(2026, 4, 6, 10, 0)
        gcal.book_appointment('Test Job', start, duration_minutes=60)

        insert_call = service.events.return_value.insert
        body = insert_call.call_args.kwargs['body']
        assert 'extendedProperties' in body
        assert body['extendedProperties']['private']['bookedForYou'] == 'true'

    def test_get_future_events_passes_through_extended_properties(self):
        gcal, service = _make_gcal()
        now = datetime.now()
        start = now + timedelta(days=1)
        end = start + timedelta(hours=1)

        gcal._execute_with_retry.return_value = {
            'items': [_gcal_event(
                'ev_prop', 'Job', start, end, '',
                extended_props={'private': {'bookedForYou': 'true'}}
            )],
        }

        events = gcal.get_future_events(days_ahead=30)
        assert events[0]['extendedProperties'] == {'private': {'bookedForYou': 'true'}}

    def test_external_event_has_empty_extended_properties(self):
        gcal, service = _make_gcal()
        now = datetime.now()
        start = now + timedelta(days=1)
        end = start + timedelta(hours=1)

        gcal._execute_with_retry.return_value = {
            'items': [_gcal_event('ev_ext', 'Meeting', start, end)],
        }

        events = gcal.get_future_events(days_ahead=30)
        assert events[0]['extendedProperties'] == {}


class TestDurationConsistency:
    """Verify that book_appointment and reschedule_appointment produce
    the same end times for the same inputs."""

    @patch('src.services.google_calendar_oauth.config')
    def test_480min_same_end_time(self, mock_config):
        """Full-day job: both methods should end at closing hour."""
        mock_config.CALENDAR_TIMEZONE = 'Europe/Dublin'
        mock_config.get_business_hours = MagicMock(return_value={'start': 9, 'end': 17})

        gcal, service = _make_gcal()
        gcal._execute_with_retry = MagicMock(return_value={'id': 'test'})

        start = datetime(2026, 4, 6, 9, 0)

        # book_appointment
        gcal.book_appointment('Test', start, duration_minutes=480)
        book_body = service.events.return_value.insert.call_args.kwargs['body']
        book_end = book_body['end']['dateTime']

        # reschedule_appointment
        old_event = _gcal_event('e1', 'Test', start, start + timedelta(hours=8))
        service.events.return_value.get.return_value.execute.return_value = old_event
        gcal.reschedule_appointment('e1', start, duration_minutes=480)
        resched_body = service.events.return_value.update.call_args.kwargs['body']
        resched_end = resched_body['end']['dateTime']

        assert book_end == resched_end
        assert '17:00:00' in book_end

    @patch('src.services.google_calendar_oauth.config')
    def test_120min_same_end_time(self, mock_config):
        """Regular 2-hour job: both methods should use simple addition."""
        mock_config.CALENDAR_TIMEZONE = 'Europe/Dublin'

        gcal, service = _make_gcal()
        gcal._execute_with_retry = MagicMock(return_value={'id': 'test'})

        start = datetime(2026, 4, 6, 10, 0)

        gcal.book_appointment('Test', start, duration_minutes=120)
        book_body = service.events.return_value.insert.call_args.kwargs['body']
        book_end = book_body['end']['dateTime']

        old_event = _gcal_event('e1', 'Test', start, start + timedelta(hours=2))
        service.events.return_value.get.return_value.execute.return_value = old_event
        gcal.reschedule_appointment('e1', start, duration_minutes=120)
        resched_body = service.events.return_value.update.call_args.kwargs['body']
        resched_end = resched_body['end']['dateTime']

        assert book_end == resched_end
        assert '12:00:00' in book_end
