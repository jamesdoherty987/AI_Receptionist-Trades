"""
Test Job Photos Upload/Delete API endpoints

Tests the photo upload and delete functionality for job cards:
1. Upload photo - validation, R2 upload, photo_urls array update
2. Delete photo - removal from R2 and photo_urls array
3. Edge cases - missing data, wrong booking, photo not found
4. GET booking includes photo_urls
"""
import pytest
import sys
import os
import json
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost/test')
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing')


@pytest.fixture
def app_client():
    """Create Flask test client with mocked database"""
    from src.app import app
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'

    mock_db = MagicMock()
    mock_db.get_company.return_value = {
        'id': 1,
        'company_name': 'Test Co',
        'subscription_tier': 'professional',
        'subscription_status': 'active',
        'trial_end': (datetime.now() + timedelta(days=30)).isoformat()
    }

    with patch('src.app.get_database', return_value=mock_db):
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['company_id'] = 1
                sess['email'] = 'test@test.com'

            yield client, mock_db


def _make_booking(photo_urls=None):
    """Helper to create a mock booking dict"""
    return {
        'id': 42,
        'company_id': 1,
        'client_id': 10,
        'appointment_time': '2026-04-01T10:00:00',
        'service_type': 'Plumbing',
        'status': 'scheduled',
        'phone_number': '+353851234567',
        'email': 'client@test.com',
        'charge': 150.0,
        'payment_status': 'unpaid',
        'address': '123 Main St',
        'eircode': 'D01 X2Y3',
        'property_type': 'House',
        'customer_name': 'John Doe',
        'address_audio_url': None,
        'photo_urls': photo_urls or [],
        'created_at': '2026-03-20T09:00:00',
        'duration_minutes': 60,
        'urgency': 'scheduled',
        'payment_method': None,
        'calendar_event_id': 'db_42',
        'requires_callout': False,
    }


class TestUploadJobPhoto:
    """Test POST /api/bookings/<id>/photos"""

    def test_upload_photo_success(self, app_client):
        client, mock_db = app_client
        mock_db.get_booking.return_value = _make_booking()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.get_connection.return_value = mock_conn

        fake_image = 'data:image/jpeg;base64,/9j/4AAQSkZJRg=='

        with patch('src.app.upload_base64_image_to_r2', return_value='https://r2.example.com/photo1.jpg') as mock_upload:
            resp = client.post('/api/bookings/42/photos',
                               data=json.dumps({'image': fake_image}),
                               content_type='application/json')

        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True
        assert data['photo_url'] == 'https://r2.example.com/photo1.jpg'
        assert 'https://r2.example.com/photo1.jpg' in data['photo_urls']
        mock_upload.assert_called_once_with(fake_image, 1, file_type='job_photos')
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_upload_photo_appends_to_existing(self, app_client):
        client, mock_db = app_client
        existing_photos = ['https://r2.example.com/old1.jpg', 'https://r2.example.com/old2.jpg']
        mock_db.get_booking.return_value = _make_booking(photo_urls=existing_photos)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.get_connection.return_value = mock_conn

        with patch('src.app.upload_base64_image_to_r2', return_value='https://r2.example.com/new.jpg'):
            resp = client.post('/api/bookings/42/photos',
                               data=json.dumps({'image': 'data:image/png;base64,abc123'}),
                               content_type='application/json')

        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data['photo_urls']) == 3
        assert data['photo_urls'][-1] == 'https://r2.example.com/new.jpg'

    def test_upload_photo_missing_image(self, app_client):
        client, mock_db = app_client
        mock_db.get_booking.return_value = _make_booking()

        resp = client.post('/api/bookings/42/photos',
                           data=json.dumps({}),
                           content_type='application/json')

        assert resp.status_code == 400
        assert 'Invalid image data' in resp.get_json()['error']

    def test_upload_photo_invalid_image_data(self, app_client):
        client, mock_db = app_client
        mock_db.get_booking.return_value = _make_booking()

        resp = client.post('/api/bookings/42/photos',
                           data=json.dumps({'image': 'not-an-image'}),
                           content_type='application/json')

        assert resp.status_code == 400
        assert 'Invalid image data' in resp.get_json()['error']

    def test_upload_photo_booking_not_found(self, app_client):
        client, mock_db = app_client
        mock_db.get_booking.return_value = None

        resp = client.post('/api/bookings/999/photos',
                           data=json.dumps({'image': 'data:image/jpeg;base64,abc'}),
                           content_type='application/json')

        assert resp.status_code == 404

    def test_upload_photo_r2_failure(self, app_client):
        client, mock_db = app_client
        mock_db.get_booking.return_value = _make_booking()

        # R2 fails and returns the base64 data back
        with patch('src.app.upload_base64_image_to_r2', return_value='data:image/jpeg;base64,abc'):
            resp = client.post('/api/bookings/42/photos',
                               data=json.dumps({'image': 'data:image/jpeg;base64,abc'}),
                               content_type='application/json')

        assert resp.status_code == 500
        assert 'Failed to upload photo' in resp.get_json()['error']

    def test_upload_photo_r2_returns_empty(self, app_client):
        client, mock_db = app_client
        mock_db.get_booking.return_value = _make_booking()

        with patch('src.app.upload_base64_image_to_r2', return_value=''):
            resp = client.post('/api/bookings/42/photos',
                               data=json.dumps({'image': 'data:image/jpeg;base64,abc'}),
                               content_type='application/json')

        assert resp.status_code == 500

    def test_upload_photo_db_error(self, app_client):
        client, mock_db = app_client
        mock_db.get_booking.return_value = _make_booking()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB error")
        mock_conn.cursor.return_value = mock_cursor
        mock_db.get_connection.return_value = mock_conn

        with patch('src.app.upload_base64_image_to_r2', return_value='https://r2.example.com/photo.jpg'):
            resp = client.post('/api/bookings/42/photos',
                               data=json.dumps({'image': 'data:image/jpeg;base64,abc'}),
                               content_type='application/json')

        assert resp.status_code == 500
        assert 'Failed to save photo' in resp.get_json()['error']
        mock_conn.rollback.assert_called_once()

    def test_upload_photo_handles_string_photo_urls(self, app_client):
        """If photo_urls is somehow a JSON string instead of a list, handle it"""
        client, mock_db = app_client
        booking = _make_booking()
        booking['photo_urls'] = '["https://r2.example.com/old.jpg"]'
        mock_db.get_booking.return_value = booking

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.get_connection.return_value = mock_conn

        with patch('src.app.upload_base64_image_to_r2', return_value='https://r2.example.com/new.jpg'):
            resp = client.post('/api/bookings/42/photos',
                               data=json.dumps({'image': 'data:image/jpeg;base64,abc'}),
                               content_type='application/json')

        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data['photo_urls']) == 2


class TestDeleteJobPhoto:
    """Test POST /api/bookings/<id>/photos/delete"""

    def test_delete_photo_success(self, app_client):
        client, mock_db = app_client
        photos = ['https://r2.example.com/photo1.jpg', 'https://r2.example.com/photo2.jpg']
        mock_db.get_booking.return_value = _make_booking(photo_urls=photos)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.get_connection.return_value = mock_conn

        with patch('src.services.storage_r2.delete_company_file', return_value=True) as mock_delete:
            resp = client.post('/api/bookings/42/photos/delete',
                               data=json.dumps({'photo_url': 'https://r2.example.com/photo1.jpg'}),
                               content_type='application/json')

        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True
        assert len(data['photo_urls']) == 1
        assert 'https://r2.example.com/photo2.jpg' in data['photo_urls']
        assert 'https://r2.example.com/photo1.jpg' not in data['photo_urls']

    def test_delete_photo_not_found_on_job(self, app_client):
        client, mock_db = app_client
        mock_db.get_booking.return_value = _make_booking(photo_urls=['https://r2.example.com/other.jpg'])

        resp = client.post('/api/bookings/42/photos/delete',
                           data=json.dumps({'photo_url': 'https://r2.example.com/nonexistent.jpg'}),
                           content_type='application/json')

        assert resp.status_code == 404
        assert 'Photo not found' in resp.get_json()['error']

    def test_delete_photo_missing_url(self, app_client):
        client, mock_db = app_client
        mock_db.get_booking.return_value = _make_booking()

        resp = client.post('/api/bookings/42/photos/delete',
                           data=json.dumps({}),
                           content_type='application/json')

        assert resp.status_code == 400
        assert 'photo_url required' in resp.get_json()['error']

    def test_delete_photo_booking_not_found(self, app_client):
        client, mock_db = app_client
        mock_db.get_booking.return_value = None

        resp = client.post('/api/bookings/999/photos/delete',
                           data=json.dumps({'photo_url': 'https://r2.example.com/photo.jpg'}),
                           content_type='application/json')

        assert resp.status_code == 404

    def test_delete_photo_r2_failure_still_removes_from_db(self, app_client):
        """R2 delete failure is non-critical - photo should still be removed from DB"""
        client, mock_db = app_client
        photos = ['https://r2.example.com/photo1.jpg']
        mock_db.get_booking.return_value = _make_booking(photo_urls=photos)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.get_connection.return_value = mock_conn

        with patch('src.services.storage_r2.delete_company_file', side_effect=Exception("R2 down")):
            resp = client.post('/api/bookings/42/photos/delete',
                               data=json.dumps({'photo_url': 'https://r2.example.com/photo1.jpg'}),
                               content_type='application/json')

        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True
        assert len(data['photo_urls']) == 0

    def test_delete_photo_db_error(self, app_client):
        client, mock_db = app_client
        photos = ['https://r2.example.com/photo1.jpg']
        mock_db.get_booking.return_value = _make_booking(photo_urls=photos)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB error")
        mock_conn.cursor.return_value = mock_cursor
        mock_db.get_connection.return_value = mock_conn

        with patch('src.services.storage_r2.delete_company_file', return_value=True):
            resp = client.post('/api/bookings/42/photos/delete',
                               data=json.dumps({'photo_url': 'https://r2.example.com/photo1.jpg'}),
                               content_type='application/json')

        assert resp.status_code == 500
        mock_conn.rollback.assert_called_once()


class TestGetBookingIncludesPhotos:
    """Test that GET /api/bookings/<id> includes photo_urls"""

    def test_get_booking_returns_photo_urls(self, app_client):
        client, mock_db = app_client
        photos = ['https://r2.example.com/p1.jpg', 'https://r2.example.com/p2.jpg']
        mock_db.get_booking.return_value = _make_booking(photo_urls=photos)
        mock_db.get_appointment_notes.return_value = []
        mock_db.get_client.return_value = None

        resp = client.get('/api/bookings/42')

        data = resp.get_json()
        assert resp.status_code == 200
        assert data['photo_urls'] == photos

    def test_get_booking_returns_empty_array_when_no_photos(self, app_client):
        client, mock_db = app_client
        mock_db.get_booking.return_value = _make_booking(photo_urls=None)
        mock_db.get_appointment_notes.return_value = []
        mock_db.get_client.return_value = None

        resp = client.get('/api/bookings/42')

        data = resp.get_json()
        assert resp.status_code == 200
        assert data['photo_urls'] == []

    def test_get_booking_handles_missing_photo_urls_column(self, app_client):
        """Before migration, photo_urls column won't exist"""
        client, mock_db = app_client
        booking = _make_booking()
        del booking['photo_urls']  # Simulate column not existing
        mock_db.get_booking.return_value = booking
        mock_db.get_appointment_notes.return_value = []
        mock_db.get_client.return_value = None

        resp = client.get('/api/bookings/42')

        data = resp.get_json()
        assert resp.status_code == 200
        assert data['photo_urls'] == []
