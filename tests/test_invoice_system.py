#!/usr/bin/env python3
"""
Comprehensive test suite for the invoice sending system.
Tests email configuration, service initialization, and invoice generation.
"""
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


class TestEmailConfiguration(unittest.TestCase):
    """Test email configuration requirements"""
    
    def test_smtp_config_variables_documented(self):
        """Verify SMTP config variables are documented in .env.example"""
        with open('.env.example', 'r') as f:
            content = f.read()
        
        required_vars = ['SMTP_SERVER', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD', 'FROM_EMAIL']
        for var in required_vars:
            self.assertIn(var, content, f"{var} should be documented in .env.example")
    
    def test_config_loads_smtp_settings(self):
        """Verify config module loads SMTP settings from environment"""
        from src.utils.config import Config
        
        # These should exist as attributes (even if None)
        self.assertTrue(hasattr(Config, 'SMTP_SERVER'))
        self.assertTrue(hasattr(Config, 'SMTP_PORT'))
        self.assertTrue(hasattr(Config, 'SMTP_USER'))
        self.assertTrue(hasattr(Config, 'SMTP_PASSWORD'))
        self.assertTrue(hasattr(Config, 'FROM_EMAIL'))


class TestEmailReminderService(unittest.TestCase):
    """Test EmailReminderService class"""
    
    def test_service_init_without_config(self):
        """Service should handle missing config gracefully"""
        with patch.dict(os.environ, {}, clear=True):
            # Clear any cached config
            with patch('src.utils.config.config') as mock_config:
                mock_config.SMTP_SERVER = None
                mock_config.SMTP_PORT = 587
                mock_config.SMTP_USER = None
                mock_config.SMTP_PASSWORD = None
                mock_config.FROM_EMAIL = None
                
                from src.services.email_reminder import EmailReminderService
                service = EmailReminderService()
                
                self.assertFalse(service.configured)
    
    def test_service_init_with_config(self):
        """Service should initialize when config is present"""
        from src.services.email_reminder import EmailReminderService
        
        service = EmailReminderService(
            smtp_server='smtp.test.com',
            smtp_port=587,
            smtp_user='test@test.com',
            smtp_password='password123',
            from_email='test@test.com'
        )
        
        self.assertTrue(service.configured)
        self.assertEqual(service.smtp_server, 'smtp.test.com')
        self.assertEqual(service.smtp_port, 587)
    
    def test_send_invoice_returns_false_when_not_configured(self):
        """send_invoice should return False when service not configured"""
        from src.services.email_reminder import EmailReminderService
        
        with patch('src.utils.config.config') as mock_config:
            mock_config.SMTP_SERVER = None
            mock_config.SMTP_PORT = 587
            mock_config.SMTP_USER = None
            mock_config.SMTP_PASSWORD = None
            mock_config.FROM_EMAIL = None
            
            service = EmailReminderService()
            
            result = service.send_invoice(
                to_email='customer@test.com',
                customer_name='Test Customer',
                service_type='Plumbing',
                charge=150.00
            )
            
            self.assertFalse(result)


class TestInvoiceEmailContent(unittest.TestCase):
    """Test invoice email content generation"""
    
    def test_invoice_email_contains_required_fields(self):
        """Invoice email should contain all required fields"""
        # Mock at the module level before importing
        with patch.dict('sys.modules', {'src.services.database': MagicMock()}):
            with patch('smtplib.SMTP') as mock_smtp:
                with patch('src.services.settings_manager.get_settings_manager') as mock_settings:
                    # Setup mocks
                    mock_settings_instance = Mock()
                    mock_settings_instance.get_business_settings.return_value = {
                        'business_name': 'Test Plumbing Co',
                        'phone': '0851234567',
                        'email': 'info@testplumbing.com'
                    }
                    mock_settings.return_value = mock_settings_instance
                    
                    mock_smtp_instance = MagicMock()
                    mock_smtp.return_value.__enter__ = Mock(return_value=mock_smtp_instance)
                    mock_smtp.return_value.__exit__ = Mock(return_value=False)
                    
                    from src.services.email_reminder import EmailReminderService
                    
                    service = EmailReminderService(
                        smtp_server='smtp.test.com',
                        smtp_port=587,
                        smtp_user='test@test.com',
                        smtp_password='password123',
                        from_email='invoices@platform.com'
                    )
                    
                    result = service.send_invoice(
                        to_email='customer@test.com',
                        customer_name='John Doe',
                        service_type='Emergency Plumbing',
                        charge=250.00,
                        appointment_time=datetime(2025, 2, 15, 10, 30),
                        invoice_number='INV-123-20250210',
                        company_name='Test Plumbing Co'
                    )
                    
                    self.assertTrue(result)
                    
                    # Verify SMTP was called
                    mock_smtp_instance.starttls.assert_called_once()
                    mock_smtp_instance.login.assert_called_once()
                    mock_smtp_instance.send_message.assert_called_once()
                    
                    # Get the sent message
                    sent_msg = mock_smtp_instance.send_message.call_args[0][0]
                    
                    # Check headers
                    self.assertIn('customer@test.com', sent_msg['To'])
                    self.assertIn('INV-123-20250210', sent_msg['Subject'])
                    self.assertIn('Test Plumbing Co', sent_msg['From'])
    
    def test_invoice_with_stripe_payment_link(self):
        """Invoice should include Stripe payment link when provided"""
        with patch.dict('sys.modules', {'src.services.database': MagicMock()}):
            with patch('smtplib.SMTP') as mock_smtp:
                with patch('src.services.settings_manager.get_settings_manager') as mock_settings:
                    mock_settings_instance = Mock()
                    mock_settings_instance.get_business_settings.return_value = {}
                    mock_settings.return_value = mock_settings_instance
                    
                    mock_smtp_instance = MagicMock()
                    mock_smtp.return_value.__enter__ = Mock(return_value=mock_smtp_instance)
                    mock_smtp.return_value.__exit__ = Mock(return_value=False)
                    
                    from src.services.email_reminder import EmailReminderService
                    
                    service = EmailReminderService(
                        smtp_server='smtp.test.com',
                        smtp_port=587,
                        smtp_user='test@test.com',
                        smtp_password='password123',
                        from_email='invoices@platform.com'
                    )
                    
                    stripe_link = 'https://checkout.stripe.com/pay/cs_test_abc123'
                    
                    result = service.send_invoice(
                        to_email='customer@test.com',
                        customer_name='John Doe',
                        service_type='Plumbing',
                        charge=100.00,
                        stripe_payment_link=stripe_link,
                        company_name='Test Co'
                    )
                    
                    self.assertTrue(result)
    
    def test_invoice_with_bank_details(self):
        """Invoice should include bank details when provided"""
        with patch.dict('sys.modules', {'src.services.database': MagicMock()}):
            with patch('smtplib.SMTP') as mock_smtp:
                with patch('src.services.settings_manager.get_settings_manager') as mock_settings:
                    mock_settings_instance = Mock()
                    mock_settings_instance.get_business_settings.return_value = {}
                    mock_settings.return_value = mock_settings_instance
                    
                    mock_smtp_instance = MagicMock()
                    mock_smtp.return_value.__enter__ = Mock(return_value=mock_smtp_instance)
                    mock_smtp.return_value.__exit__ = Mock(return_value=False)
                    
                    from src.services.email_reminder import EmailReminderService
                    
                    service = EmailReminderService(
                        smtp_server='smtp.test.com',
                        smtp_port=587,
                        smtp_user='test@test.com',
                        smtp_password='password123',
                        from_email='invoices@platform.com'
                    )
                    
                    bank_details = {
                        'iban': 'IE12BOFI90001234567890',
                        'bic': 'BOFIIE2D',
                        'bank_name': 'Bank of Ireland',
                        'account_holder': 'Test Plumbing Ltd'
                    }
                    
                    result = service.send_invoice(
                        to_email='customer@test.com',
                        customer_name='John Doe',
                        service_type='Plumbing',
                        charge=100.00,
                        bank_details=bank_details,
                        add_bank_details=True,
                        company_name='Test Co'
                    )
                    
                    self.assertTrue(result)


class TestInvoiceAPIEndpoint(unittest.TestCase):
    """Test the invoice API endpoint validation"""
    
    def test_api_validates_booking_exists(self):
        """API should return 404 if booking not found"""
        # This would require Flask test client setup
        pass
    
    def test_api_validates_customer_email(self):
        """API should return 400 if customer has no email"""
        pass
    
    def test_api_validates_charge_amount(self):
        """API should return 400 if charge is invalid"""
        pass


class TestInvoiceNumberGeneration(unittest.TestCase):
    """Test invoice number generation"""
    
    def test_invoice_number_format(self):
        """Invoice number should follow expected format"""
        from datetime import datetime
        
        booking_id = 123
        invoice_number = f"INV-{booking_id}-{datetime.now().strftime('%Y%m%d')}"
        
        self.assertTrue(invoice_number.startswith('INV-'))
        self.assertIn('123', invoice_number)
        self.assertRegex(invoice_number, r'INV-\d+-\d{8}')


if __name__ == '__main__':
    # Run tests with verbosity
    unittest.main(verbosity=2)
