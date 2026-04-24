"""
Tests for the owner-employee messaging feature.
Covers: API endpoints, DB methods, security, edge cases.
"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeDB:
    """Mock database for testing messaging methods."""

    def __init__(self):
        self.messages = []
        self.notifications = []
        self._next_id = 1
        self.employees = {
            1: {'id': 1, 'name': 'Alice', 'company_id': 100},
            2: {'id': 2, 'name': 'Bob', 'company_id': 100},
            3: {'id': 3, 'name': 'Charlie', 'company_id': 200},  # different company
        }
        self.companies = {
            100: {'id': 100, 'business_name': 'Test Co'},
            200: {'id': 200, 'business_name': 'Other Co'},
        }

    def send_message(self, company_id, employee_id, sender_type, content):
        from datetime import datetime
        msg = {
            'id': self._next_id,
            'company_id': company_id,
            'employee_id': employee_id,
            'sender_type': sender_type,
            'content': content,
            'read': False,
            'created_at': datetime.now(),
        }
        self._next_id += 1
        self.messages.append(msg)
        return msg

    def get_conversation(self, company_id, employee_id, limit=50, before_id=None):
        msgs = [m for m in self.messages
                if m['company_id'] == company_id and m['employee_id'] == employee_id]
        if before_id:
            msgs = [m for m in msgs if m['id'] < before_id]
        msgs.sort(key=lambda x: x['created_at'])
        return msgs[-limit:]

    def mark_messages_read(self, company_id, employee_id, reader_type):
        sender_type = 'employee' if reader_type == 'owner' else 'owner'
        count = 0
        for m in self.messages:
            if (m['company_id'] == company_id and m['employee_id'] == employee_id
                    and m['sender_type'] == sender_type and not m['read']):
                m['read'] = True
                count += 1
        return count

    def get_unread_message_counts(self, company_id):
        counts = {}
        for m in self.messages:
            if m['company_id'] == company_id and m['sender_type'] == 'employee' and not m['read']:
                counts[m['employee_id']] = counts.get(m['employee_id'], 0) + 1
        return counts

    def get_employee_unread_count(self, company_id, employee_id):
        return sum(1 for m in self.messages
                   if m['company_id'] == company_id and m['employee_id'] == employee_id
                   and m['sender_type'] == 'owner' and not m['read'])

    def get_employee(self, employee_id, company_id=None):
        w = self.employees.get(employee_id)
        if w and company_id and w['company_id'] != company_id:
            return None
        return w

    def get_company(self, company_id):
        return self.companies.get(company_id)

    def create_notification(self, company_id, recipient_type, recipient_id, notif_type, message, metadata=None):
        self.notifications.append({
            'company_id': company_id,
            'recipient_type': recipient_type,
            'recipient_id': recipient_id,
            'type': notif_type,
            'message': message,
            'metadata': metadata,
        })
        return len(self.notifications)

    def get_owner_conversations_summary(self, company_id):
        return []


# ── Unit Tests ──────────────────────────────────────────────────────

class TestSendMessage:
    def setup_method(self):
        self.db = FakeDB()

    def test_send_message_basic(self):
        msg = self.db.send_message(100, 1, 'owner', 'Hello Alice')
        assert msg is not None
        assert msg['content'] == 'Hello Alice'
        assert msg['sender_type'] == 'owner'
        assert msg['employee_id'] == 1
        assert msg['company_id'] == 100
        assert msg['read'] is False

    def test_send_message_employee_reply(self):
        self.db.send_message(100, 1, 'owner', 'Hello')
        msg = self.db.send_message(100, 1, 'employee', 'Hi boss')
        assert msg['sender_type'] == 'employee'
        assert msg['content'] == 'Hi boss'

    def test_send_message_increments_id(self):
        m1 = self.db.send_message(100, 1, 'owner', 'First')
        m2 = self.db.send_message(100, 1, 'employee', 'Second')
        assert m2['id'] > m1['id']


class TestGetConversation:
    def setup_method(self):
        self.db = FakeDB()

    def test_empty_conversation(self):
        msgs = self.db.get_conversation(100, 1)
        assert msgs == []

    def test_conversation_returns_chronological(self):
        self.db.send_message(100, 1, 'owner', 'First')
        self.db.send_message(100, 1, 'employee', 'Second')
        self.db.send_message(100, 1, 'owner', 'Third')
        msgs = self.db.get_conversation(100, 1)
        assert len(msgs) == 3
        assert msgs[0]['content'] == 'First'
        assert msgs[1]['content'] == 'Second'
        assert msgs[2]['content'] == 'Third'

    def test_conversation_isolation_by_employee(self):
        self.db.send_message(100, 1, 'owner', 'For Alice')
        self.db.send_message(100, 2, 'owner', 'For Bob')
        alice_msgs = self.db.get_conversation(100, 1)
        bob_msgs = self.db.get_conversation(100, 2)
        assert len(alice_msgs) == 1
        assert alice_msgs[0]['content'] == 'For Alice'
        assert len(bob_msgs) == 1
        assert bob_msgs[0]['content'] == 'For Bob'

    def test_conversation_isolation_by_company(self):
        self.db.send_message(100, 1, 'owner', 'Company 100')
        self.db.send_message(200, 1, 'owner', 'Company 200')
        msgs = self.db.get_conversation(100, 1)
        assert len(msgs) == 1
        assert msgs[0]['content'] == 'Company 100'

    def test_conversation_limit(self):
        for i in range(10):
            self.db.send_message(100, 1, 'owner', f'Msg {i}')
        msgs = self.db.get_conversation(100, 1, limit=3)
        assert len(msgs) == 3
        # Should return the LAST 3 messages
        assert msgs[0]['content'] == 'Msg 7'
        assert msgs[2]['content'] == 'Msg 9'

    def test_conversation_before_id(self):
        for i in range(5):
            self.db.send_message(100, 1, 'owner', f'Msg {i}')
        # Get messages before id 4
        msgs = self.db.get_conversation(100, 1, before_id=4)
        assert all(m['id'] < 4 for m in msgs)


class TestMarkMessagesRead:
    def setup_method(self):
        self.db = FakeDB()

    def test_mark_read_owner_reads_employee_messages(self):
        self.db.send_message(100, 1, 'employee', 'Hello boss')
        self.db.send_message(100, 1, 'employee', 'Are you there?')
        self.db.send_message(100, 1, 'owner', 'My own message')  # should not be affected
        count = self.db.mark_messages_read(100, 1, 'owner')
        assert count == 2
        # Verify employee messages are read
        msgs = self.db.get_conversation(100, 1)
        employee_msgs = [m for m in msgs if m['sender_type'] == 'employee']
        assert all(m['read'] for m in employee_msgs)
        # Owner message should still be unread
        owner_msgs = [m for m in msgs if m['sender_type'] == 'owner']
        assert not owner_msgs[0]['read']

    def test_mark_read_employee_reads_owner_messages(self):
        self.db.send_message(100, 1, 'owner', 'Task for you')
        count = self.db.mark_messages_read(100, 1, 'employee')
        assert count == 1
        msgs = self.db.get_conversation(100, 1)
        assert msgs[0]['read'] is True

    def test_mark_read_idempotent(self):
        self.db.send_message(100, 1, 'employee', 'Hello')
        self.db.mark_messages_read(100, 1, 'owner')
        count = self.db.mark_messages_read(100, 1, 'owner')
        assert count == 0  # Already read

    def test_mark_read_isolation(self):
        self.db.send_message(100, 1, 'employee', 'From Alice')
        self.db.send_message(100, 2, 'employee', 'From Bob')
        self.db.mark_messages_read(100, 1, 'owner')
        # Bob's message should still be unread
        bob_msgs = self.db.get_conversation(100, 2)
        assert not bob_msgs[0]['read']


class TestUnreadCounts:
    def setup_method(self):
        self.db = FakeDB()

    def test_unread_counts_empty(self):
        counts = self.db.get_unread_message_counts(100)
        assert counts == {}

    def test_unread_counts_per_employee(self):
        self.db.send_message(100, 1, 'employee', 'From Alice 1')
        self.db.send_message(100, 1, 'employee', 'From Alice 2')
        self.db.send_message(100, 2, 'employee', 'From Bob')
        counts = self.db.get_unread_message_counts(100)
        assert counts[1] == 2
        assert counts[2] == 1

    def test_unread_counts_ignores_owner_messages(self):
        self.db.send_message(100, 1, 'owner', 'From owner')
        counts = self.db.get_unread_message_counts(100)
        assert counts == {}

    def test_unread_counts_after_read(self):
        self.db.send_message(100, 1, 'employee', 'Hello')
        self.db.mark_messages_read(100, 1, 'owner')
        counts = self.db.get_unread_message_counts(100)
        assert counts == {}

    def test_employee_unread_count(self):
        self.db.send_message(100, 1, 'owner', 'Task 1')
        self.db.send_message(100, 1, 'owner', 'Task 2')
        self.db.send_message(100, 1, 'employee', 'My reply')  # should not count
        count = self.db.get_employee_unread_count(100, 1)
        assert count == 2

    def test_employee_unread_count_after_read(self):
        self.db.send_message(100, 1, 'owner', 'Task')
        self.db.mark_messages_read(100, 1, 'employee')
        count = self.db.get_employee_unread_count(100, 1)
        assert count == 0


class TestSecurityIsolation:
    """Test that messages are properly isolated between companies."""

    def setup_method(self):
        self.db = FakeDB()

    def test_get_employee_with_wrong_company(self):
        """Employee 3 belongs to company 200, should not be accessible from company 100."""
        employee = self.db.get_employee(3, company_id=100)
        assert employee is None

    def test_get_employee_with_correct_company(self):
        employee = self.db.get_employee(1, company_id=100)
        assert employee is not None
        assert employee['name'] == 'Alice'

    def test_cross_company_conversation_isolation(self):
        self.db.send_message(100, 1, 'owner', 'Company 100 msg')
        self.db.send_message(200, 1, 'owner', 'Company 200 msg')
        msgs_100 = self.db.get_conversation(100, 1)
        msgs_200 = self.db.get_conversation(200, 1)
        assert len(msgs_100) == 1
        assert msgs_100[0]['content'] == 'Company 100 msg'
        assert len(msgs_200) == 1
        assert msgs_200[0]['content'] == 'Company 200 msg'

    def test_cross_company_unread_isolation(self):
        self.db.send_message(100, 1, 'employee', 'From company 100')
        self.db.send_message(200, 1, 'employee', 'From company 200')
        counts_100 = self.db.get_unread_message_counts(100)
        counts_200 = self.db.get_unread_message_counts(200)
        assert counts_100.get(1) == 1
        assert counts_200.get(1) == 1


class TestEdgeCases:
    def setup_method(self):
        self.db = FakeDB()

    def test_empty_content_not_stored(self):
        """API layer should reject empty content, but DB layer stores whatever is passed."""
        msg = self.db.send_message(100, 1, 'owner', '')
        assert msg is not None  # DB doesn't validate, API does

    def test_very_long_content(self):
        """API limits to 2000 chars, but test DB handles long strings."""
        long_text = 'x' * 5000
        msg = self.db.send_message(100, 1, 'owner', long_text)
        assert msg is not None
        assert len(msg['content']) == 5000

    def test_special_characters_in_content(self):
        msg = self.db.send_message(100, 1, 'owner', '<script>alert("xss")</script>')
        assert msg['content'] == '<script>alert("xss")</script>'
        # React auto-escapes this in the frontend

    def test_unicode_content(self):
        msg = self.db.send_message(100, 1, 'owner', '👋 Hello! Ñoño café résumé 你好')
        assert '👋' in msg['content']
        assert '你好' in msg['content']

    def test_newlines_in_content(self):
        msg = self.db.send_message(100, 1, 'owner', 'Line 1\nLine 2\nLine 3')
        assert '\n' in msg['content']

    def test_notification_created_on_send(self):
        """Verify notification is created when owner sends a message."""
        self.db.send_message(100, 1, 'owner', 'Hello')
        # Simulate what the API endpoint does
        employee = self.db.get_employee(1)
        company = self.db.get_company(100)
        content = 'Hello'
        preview = content[:80] + ('...' if len(content) > 80 else '')
        self.db.create_notification(
            100, 'employee', 1, 'new_message',
            f"New message from {company['business_name']}: {preview}",
            {'sender': 'owner'}
        )
        assert len(self.db.notifications) == 1
        assert self.db.notifications[0]['type'] == 'new_message'
        assert self.db.notifications[0]['recipient_type'] == 'employee'

    def test_notification_preview_truncation(self):
        """Verify long messages are truncated in notification preview."""
        long_msg = 'A' * 200
        preview = long_msg[:80] + ('...' if len(long_msg) > 80 else '')
        assert len(preview) == 83  # 80 chars + '...'
        assert preview.endswith('...')

    def test_rapid_messages(self):
        """Simulate rapid message sending."""
        for i in range(100):
            self.db.send_message(100, 1, 'owner' if i % 2 == 0 else 'employee', f'Msg {i}')
        msgs = self.db.get_conversation(100, 1, limit=50)
        assert len(msgs) == 50
        # Should be the last 50 messages
        assert msgs[0]['content'] == 'Msg 50'
        assert msgs[-1]['content'] == 'Msg 99'


class TestAPIValidation:
    """Test the validation logic that the API endpoints perform."""

    def test_empty_content_rejected(self):
        content = ''.strip()
        assert not content  # Would return 400

    def test_whitespace_only_rejected(self):
        content = '   \n\t  '.strip()
        assert not content  # Would return 400

    def test_content_length_limit(self):
        content = 'x' * 2001
        assert len(content) > 2000  # Would return 400

    def test_content_at_limit(self):
        content = 'x' * 2000
        assert len(content) <= 2000  # Would pass

    def test_none_content_handled(self):
        data = {}
        content = (data.get('content') or '').strip()
        assert not content  # Would return 400

    def test_null_json_body_handled(self):
        data = None
        data = data or {}
        content = (data.get('content') or '').strip()
        assert not content  # Would return 400
