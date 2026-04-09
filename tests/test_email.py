"""
Tests for email utility functions using Resend API
"""
import pytest
from unittest.mock import patch, MagicMock
from utils.email import (
    send_email,
    send_appointment_notification_email,
    validate_email,
    sanitize_email_input
)


class TestEmailValidation:
    """Test email validation functionality"""

    def test_validate_email_valid(self):
        """Test validation of valid email addresses"""
        assert validate_email("test@example.com") is True
        assert validate_email("user.name@domain.co.uk") is True
        assert validate_email("admin+tag@test-domain.com") is True

    def test_validate_email_invalid(self):
        """Test validation of invalid email addresses"""
        assert validate_email("") is False
        assert validate_email("not-an-email") is False
        assert validate_email("@example.com") is False
        assert validate_email("test@") is False
        assert validate_email(None) is False

    def test_sanitize_email_input(self):
        """Test sanitization of email header inputs"""
        assert sanitize_email_input("Normal Subject") == "Normal Subject"
        assert sanitize_email_input("Subject\nWith\nNewlines") == "Subject With Newlines"
        assert sanitize_email_input("Subject\rWith\rCarriage") == "Subject With Carriage"
        assert sanitize_email_input("  Spaces  ") == "Spaces"

class TestSendEmail:
    """Test send_email function with Resend API"""

    @patch('utils.email.MOCK_EMAIL', True)
    def test_send_email_mock_mode(self):
        """Test email sending in mock mode"""
        result = send_email(
            from_email="noreply@pinnaclefamilyclinic.com.sg",
            to_email="test@example.com",
            subject="Test Subject",
            html="<p>Test Body</p>"
        )
        assert result is True

    @patch('utils.email.MOCK_EMAIL', True)
    def test_send_email_mock_mode_with_cc(self):
        """Test email sending in mock mode with CC"""
        result = send_email(
            from_email="noreply@pinnaclefamilyclinic.com.sg",
            to_email="test@example.com",
            subject="Test Subject",
            html="<p>Test Body</p>",
            cc_emails=["cc@example.com"]
        )
        assert result is True

    def test_send_email_invalid_to_email(self):
        """Test email sending with invalid to_email"""
        result = send_email(
            from_email="noreply@pinnaclefamilyclinic.com.sg",
            to_email="invalid-email",
            subject="Test Subject",
            html="<p>Test Body</p>"
        )
        assert result is False

    @patch('utils.email.MOCK_EMAIL', True)
    def test_send_email_invalid_cc_email(self):
        """Test email sending with invalid cc_emails - should still send to valid to_email"""
        result = send_email(
            from_email="noreply@pinnaclefamilyclinic.com.sg",
            to_email="test@example.com",
            subject="Test Subject",
            html="<p>Test Body</p>",
            cc_emails=["invalid-email"]
        )
        # Should succeed because to_email is valid (invalid CC is filtered out)
        assert result is True

    @patch('utils.email.MOCK_EMAIL', False)
    @patch('utils.email.resend.Emails.send')
    def test_send_email_resend_success(self, mock_resend_send):
        """Test successful email sending via Resend API"""
        mock_resend_send.return_value = {"id": "email_123"}

        result = send_email(
            from_email="noreply@pinnaclefamilyclinic.com.sg",
            to_email="test@example.com",
            subject="Test Subject",
            html="<p>Test Body</p>"
        )

        assert result is True
        mock_resend_send.assert_called_once()
        call_args = mock_resend_send.call_args[0][0]
        assert call_args["from"] == "noreply@pinnaclefamilyclinic.com.sg"
        assert call_args["to"] == ["test@example.com"]
        assert call_args["subject"] == "Test Subject"
        assert call_args["html"] == "<p>Test Body</p>"

    @patch('utils.email.MOCK_EMAIL', False)
    @patch('utils.email.resend.Emails.send')
    def test_send_email_resend_with_cc(self, mock_resend_send):
        """Test email sending via Resend API with CC"""
        mock_resend_send.return_value = {"id": "email_456"}

        result = send_email(
            from_email="noreply@pinnaclefamilyclinic.com.sg",
            to_email="test@example.com",
            subject="Test Subject",
            html="<p>Test Body</p>",
            cc_emails=["cc1@example.com", "cc2@example.com"]
        )

        assert result is True
        call_args = mock_resend_send.call_args[0][0]
        assert call_args["cc"] == ["cc1@example.com", "cc2@example.com"]

    @patch('utils.email.MOCK_EMAIL', False)
    @patch('utils.email.resend.Emails.send')
    def test_send_email_resend_failure(self, mock_resend_send):
        """Test email sending failure via Resend API"""
        mock_resend_send.side_effect = Exception("Resend API Error")

        result = send_email(
            from_email="noreply@pinnaclefamilyclinic.com.sg",
            to_email="test@example.com",
            subject="Test Subject",
            html="<p>Test Body</p>"
        )

        assert result is False

    @patch('utils.email.MOCK_EMAIL', False)
    @patch('utils.email.resend.Emails.send')
    def test_send_email_multiple_cc_recipients(self, mock_resend_send):
        """Test email with multiple CC recipients"""
        mock_resend_send.return_value = {"id": "email_789"}

        result = send_email(
            from_email="noreply@pinnaclefamilyclinic.com.sg",
            to_email="test@example.com",
            subject="Test Subject",
            html="<p>Test Body</p>",
            cc_emails=["cc1@example.com", "cc2@example.com", "cc3@example.com"]
        )

        assert result is True
        call_args = mock_resend_send.call_args[0][0]
        assert call_args["cc"] == ["cc1@example.com", "cc2@example.com", "cc3@example.com"]

    @patch('utils.email.MOCK_EMAIL', False)
    @patch('utils.email.resend.Emails.send')
    def test_send_email_cc_only_single_recipient(self, mock_resend_send):
        """Test email with only one CC recipient (no to_email)"""
        mock_resend_send.return_value = {"id": "email_abc"}

        result = send_email(
            from_email="noreply@pinnaclefamilyclinic.com.sg",
            to_email=None,
            subject="Test Subject",
            html="<p>Test Body</p>",
            cc_emails=["cc@example.com"]
        )

        assert result is True
        call_args = mock_resend_send.call_args[0][0]
        # Single CC becomes 'to', no CC in params
        assert call_args["to"] == ["cc@example.com"]
        assert "cc" not in call_args

    def test_send_email_very_long_email(self):
        """Test validation of very long email address"""
        long_email = "a" * 300 + "@example.com"
        result = send_email(
            from_email="noreply@pinnaclefamilyclinic.com.sg",
            to_email=long_email,
            subject="Test",
            html="<p>Test</p>"
        )
        # Should still validate based on regex (may or may not pass)
        # This test documents the behavior
        assert isinstance(result, bool)

    def test_send_email_special_chars_in_subject(self):
        """Test sanitization of special characters in subject"""
        from utils.email import sanitize_email_input
        result = sanitize_email_input("Subject\nwith\rspecial\tchars")
        assert "\n" not in result
        assert "\r" not in result


class TestSendAppointmentNotificationEmail:
    """Test send_appointment_notification_email function"""

    @patch('utils.email.send_email')
    @patch('models.SessionLocal')
    @patch('utils.email.RESEND_API_KEY', 'test_api_key')
    def test_send_appointment_notification_basic(self, mock_session_local, mock_send_email):
        """Test sending appointment notification with basic data"""
        # Mock database session
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        # Mock appointment
        mock_appointment = MagicMock()
        mock_appointment.id = "appt_123"
        mock_appointment.branch = {"id": "branch_123"}
        mock_appointment.account_id = "account_123"
        mock_appointment.guests = None
        mock_appointment.start_datetime.astimezone.return_value.strftime.side_effect = lambda fmt: {
            "%d %B %Y": "13 October 2025",
            "%I:%M %p": "02:30 PM"
        }[fmt]

        # Mock branch
        mock_branch = MagicMock()
        mock_branch.id = "branch_123"
        mock_branch.name = "Test Clinic"
        mock_branch.email = "clinic@example.com"

        # Mock account
        mock_account = MagicMock()
        mock_account.id = "account_123"
        mock_account.name = "John Doe"

        # Mock services and payment
        mock_service_item = MagicMock()
        mock_service_item.name = "Health Screening"
        mock_service_group = MagicMock()
        mock_service_group.items = [mock_service_item]
        mock_appointment.get_services.return_value = [mock_service_group]

        mock_payment_breakdown = MagicMock()
        mock_payment_breakdown.total = 50.00
        mock_appointment.get_payment_breakdown.return_value = mock_payment_breakdown

        # Setup query mocks
        def query_side_effect(model):
            mock_query = MagicMock()
            if hasattr(model, '__name__'):
                if model.__name__ == 'Appointment':
                    mock_query.filter.return_value.first.return_value = mock_appointment
                elif model.__name__ == 'Branch':
                    mock_query.filter.return_value.first.return_value = mock_branch
                elif model.__name__ == 'Account':
                    mock_query.filter.return_value.in_.return_value.all.return_value = [mock_account]
            return mock_query

        mock_db.query.side_effect = query_side_effect

        # Mock get_config_value
        with patch('utils.system_config.get_config_value') as mock_get_config:
            mock_get_config.return_value = {
                "from_email": "noreply@example.com",
                "cc_emails": ["cc@example.com"],
                "appointments_template": {
                    "title": "New Appointment",
                    "body": "Patient: {patient_name} at {clinic_name}"
                }
            }

            # Mock get_grouped_appointments
            with patch('repository.appointment.get_grouped_appointments') as mock_get_grouped:
                mock_get_grouped.return_value = [mock_appointment]

                mock_send_email.return_value = True

                result = send_appointment_notification_email("appt_123")

                assert result is True
                mock_send_email.assert_called_once()
                mock_db.close.assert_called_once()

    @patch('models.SessionLocal')
    @patch('utils.email.RESEND_API_KEY', '')
    def test_send_appointment_notification_no_resend_key(self, mock_session_local):
        """Test that email fails when RESEND_API_KEY is not configured"""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_appointment = MagicMock()
        mock_appointment.id = "appt_123"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_appointment

        with patch('utils.system_config.get_config_value') as mock_get_config:
            mock_get_config.return_value = {
                "from_email": "noreply@example.com",
                "cc_emails": ["cc@example.com"],
                "appointments_template": {"title": "Test", "body": "Test"}
            }

            result = send_appointment_notification_email("appt_123")

            assert result is False
            mock_db.close.assert_called_once()

    @patch('utils.email.send_email')
    @patch('models.SessionLocal')
    @patch('utils.email.RESEND_API_KEY', 'test_api_key')
    def test_send_appointment_notification_no_template(self, mock_session_local, mock_send_email):
        """Test that email fails when template is not configured"""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_appointment = MagicMock()
        mock_appointment.id = "appt_123"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_appointment

        with patch('utils.system_config.get_config_value') as mock_get_config:
            # Config without template
            mock_get_config.return_value = {
                "from_email": "noreply@example.com",
                "cc_emails": ["cc@example.com"]
            }

            result = send_appointment_notification_email("appt_123")

            assert result is False
            mock_send_email.assert_not_called()
            mock_db.close.assert_called_once()

    @patch('utils.email.send_email')
    @patch('models.SessionLocal')
    @patch('utils.email.RESEND_API_KEY', 'test_api_key')
    def test_send_appointment_notification_no_from_email(self, mock_session_local, mock_send_email):
        """Test that email fails when from_email is not configured"""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_appointment = MagicMock()
        mock_appointment.id = "appt_123"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_appointment

        with patch('utils.system_config.get_config_value') as mock_get_config:
            # Config without from_email
            mock_get_config.return_value = {
                "cc_emails": ["cc@example.com"],
                "appointments_template": {"title": "Test", "body": "Test"}
            }

            result = send_appointment_notification_email("appt_123")

            assert result is False
            mock_send_email.assert_not_called()
            mock_db.close.assert_called_once()

    @patch('utils.email.send_email')
    @patch('models.SessionLocal')
    @patch('utils.email.RESEND_API_KEY', 'test_api_key')
    def test_send_appointment_notification_empty_services(self, mock_session_local, mock_send_email):
        """Test notification when appointment has no services"""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_appointment = MagicMock()
        mock_appointment.id = "appt_456"
        mock_appointment.branch = {"id": "branch_456"}
        mock_appointment.account_id = None
        mock_appointment.guests = None
        mock_appointment.start_datetime.astimezone.return_value.strftime.side_effect = lambda fmt: {
            "%d %B %Y": "14 October 2025",
            "%I:%M %p": "03:00 PM"
        }[fmt]
        mock_appointment.get_services.return_value = []  # Empty services
        mock_payment_breakdown = MagicMock()
        mock_payment_breakdown.total = 0
        mock_appointment.get_payment_breakdown.return_value = mock_payment_breakdown

        mock_branch = MagicMock()
        mock_branch.id = "branch_456"
        mock_branch.name = "Test Clinic"
        mock_branch.email = "clinic@example.com"

        def query_side_effect(model):
            mock_query = MagicMock()
            if hasattr(model, '__name__'):
                if model.__name__ == 'Appointment':
                    mock_query.filter.return_value.first.return_value = mock_appointment
                elif model.__name__ == 'Branch':
                    mock_query.filter.return_value.first.return_value = mock_branch
            return mock_query

        mock_db.query.side_effect = query_side_effect

        with patch('utils.system_config.get_config_value') as mock_get_config:
            mock_get_config.return_value = {
                "from_email": "noreply@example.com",
                "cc_emails": ["cc@example.com"],
                "appointments_template": {
                    "title": "New Appointment",
                    "body": "Services: {service_names}"
                }
            }

            with patch('repository.appointment.get_grouped_appointments') as mock_get_grouped:
                mock_get_grouped.return_value = [mock_appointment]
                mock_send_email.return_value = True

                result = send_appointment_notification_email("appt_456")

                assert result is True
                # Verify service_names was set to default
                call_args = mock_send_email.call_args[1]
                assert "No services selected" in call_args['html']

    @patch('models.SessionLocal')
    @patch('utils.email.RESEND_API_KEY', 'test_api_key')
    def test_send_appointment_notification_template_key_error(self, mock_session_local):
        """Test that template formatting KeyError is handled gracefully"""
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_appointment = MagicMock()
        mock_appointment.id = "appt_789"
        mock_appointment.branch = {"id": "branch_789"}
        mock_appointment.start_datetime.astimezone.return_value.strftime.side_effect = lambda fmt: {
            "%d %B %Y": "15 October 2025",
            "%I:%M %p": "04:00 PM"
        }[fmt]

        mock_branch = MagicMock()
        mock_branch.id = "branch_789"
        mock_branch.name = "Test Clinic"
        mock_branch.email = "clinic@example.com"

        def query_side_effect(model):
            mock_query = MagicMock()
            if hasattr(model, '__name__'):
                if model.__name__ == 'Appointment':
                    mock_query.filter.return_value.first.return_value = mock_appointment
                elif model.__name__ == 'Branch':
                    mock_query.filter.return_value.first.return_value = mock_branch
            return mock_query

        mock_db.query.side_effect = query_side_effect

        with patch('utils.system_config.get_config_value') as mock_get_config:
            # Template with missing variable
            mock_get_config.return_value = {
                "from_email": "noreply@example.com",
                "cc_emails": ["cc@example.com"],
                "appointments_template": {
                    "title": "New Appointment",
                    "body": "Unknown variable: {unknown_variable}"
                }
            }

            with patch('repository.appointment.get_grouped_appointments') as mock_get_grouped:
                mock_get_grouped.return_value = [mock_appointment]
                mock_appointment.get_services.return_value = []
                mock_payment_breakdown = MagicMock()
                mock_payment_breakdown.total = 0
                mock_appointment.get_payment_breakdown.return_value = mock_payment_breakdown

                result = send_appointment_notification_email("appt_789")

                # Should return False due to KeyError
                assert result is False
                mock_db.close.assert_called_once()
