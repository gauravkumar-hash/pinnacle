"""
Email utility for sending notifications via Resend API
"""
import html
import logging
import re
from typing import Optional
import resend
from config import RESEND_API_KEY, MOCK_EMAIL


# Email validation regex (basic RFC 5322 compliant)
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# Set Resend API key
resend.api_key = RESEND_API_KEY


def sanitize_email_input(value: str) -> str:
    """
    Sanitize email input to prevent header injection
    Removes newlines and control characters

    Args:
        value: Input string to sanitize

    Returns:
        Sanitized string
    """
    return value.replace('\n', ' ').replace('\r', ' ').strip()


def validate_email(email: str) -> bool:
    """
    Validate email address format

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    if not email or not isinstance(email, str):
        return False

    return bool(EMAIL_REGEX.match(email.strip()))


def send_email(
    from_email: str,
    to_email: Optional[str],
    subject: str,
    html: str,
    cc_emails: Optional[list[str]] = None
) -> bool:
    """
    Send an email via Resend API

    Args:
        from_email: Sender email address (must be verified domain)
        to_email: Recipient email address (can be None if only CC recipients)
        subject: Email subject
        html: Email body in HTML format
        cc_emails: Optional list of CC email addresses

    Returns:
        True if email was sent successfully, False otherwise
    """
    # Build recipient lists - filter valid emails only
    to_recipients = [email for email in [to_email] if email and validate_email(email)]
    cc_recipients = [email for email in (cc_emails or []) if email and validate_email(email)]

    # Must have at least one recipient
    if not to_recipients and not cc_recipients:
        logging.error(f"No valid recipient email addresses provided. To: {to_email}, CC: {cc_emails}")
        return False

    # Sanitize subject to prevent injection
    subject = sanitize_email_input(subject)

    if MOCK_EMAIL:
        logging.debug(f"MOCK EMAIL: From: {from_email}, To: {to_email or 'None'}, CC: {cc_emails}, Subject: {subject}")
        logging.debug(f"HTML Body:\n{html}")
        return True

    try:
        # Build params for Resend API
        params: resend.Emails.SendParams = {
            "from": from_email,
            "to": to_recipients if to_recipients else cc_recipients[:1], # Resend requires at least one 'to'
            "subject": subject,
            "html": html,
        }

        # Only add CC if there are CC recipients and we have a primary 'to' recipient
        # OR if we have multiple CC recipients and used the first one as 'to'
        cc_to_add = cc_recipients if to_recipients else cc_recipients[1:]
        if cc_to_add:
            params["cc"] = cc_to_add

        # Send email via Resend
        email: resend.Email = resend.Emails.send(params)

        logging.info(f"Email sent successfully to {to_email or cc_recipients[0]}, ID: {email.get('id', 'unknown')}")
        return True

    except Exception as e:
        logging.error(f"Failed to send email to {to_email}: {str(e)}", exc_info=True)
        return False


def send_appointment_notification_email(
    appointment_id: str
) -> bool:
    """
    Send appointment notification email to clinic

    This function handles all the logic for gathering appointment data,
    patient names, branch email, and CC emails from the database.
    Creates its own database session for thread safety.

    Args:
        appointment_id: ID of the appointment to send notification for

    Returns:
        True if email was sent successfully, False otherwise
    """
    from models import SessionLocal, Account, Appointment
    from models.pinnacle import Branch
    from models.appointment import AppointmentCorporateCode
    from repository.appointment import get_grouped_appointments
    from utils.system_config import get_config_value
    from utils.sg_datetime import sgtz

    # Create new database session for thread safety
    db = SessionLocal()
    try:
        # Query the appointment
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            logging.error(f"Appointment {appointment_id} not found when sending notification email")
            return False

        # Get email configuration from backend config
        email_config: dict = get_config_value(db, "EMAIL_NOTIFICATIONS_CC") or {}
        if not isinstance(email_config, dict):
            logging.error(f"Invalid email configuration format for appointment {appointment.id}")
            return False

        from_email: Optional[str] = email_config.get("from_email")
        cc_emails: Optional[list[str]] = email_config.get("cc_emails")
        email_template: Optional[dict] = email_config.get("appointments_template")

        # Check if RESEND_API_KEY is configured
        if not RESEND_API_KEY and not MOCK_EMAIL:
            logging.error(
                f"RESEND_API_KEY not configured. Cannot send email notification for appointment {appointment.id}"
            )
            return False

        # Check if from_email is configured
        if not from_email:
            logging.error(f"from_email not configured in EMAIL_NOTIFICATIONS_CC. Cannot send email notification for appointment {appointment.id}")
            return False

        # Check if email template is configured
        if not email_template:
            logging.error(f"Email template not configured in EMAIL_NOTIFICATIONS_CC. Cannot send email notification for appointment {appointment.id}")
            return False

        # Get branch information
        branch = db.query(Branch).filter(Branch.id == appointment.branch['id']).first()
        if not branch:
            logging.error(f"Branch not found for appointment {appointment.id}")
            return False

        # Log warning if branch email is missing (recoverable - can still send to CC)
        if not branch.email:
            logging.warning(
                f"Branch {branch.id} ({branch.name}) has no email configured for appointment {appointment.id}. "
                f"Email will be sent to CC recipients only: {cc_emails or 'None'}"
            )

        # Must have at least one recipient (branch email or CC)
        if not branch.email and not cc_emails:
            logging.warning(
                f"No email recipients configured for appointment {appointment.id}. "
                f"Branch email: {branch.email}, CC emails: {cc_emails}"
            )
            return False

        # Get all grouped appointments
        appts = get_grouped_appointments(db, appointment)

        # Batch query accounts to avoid N+1 problem
        account_ids = [a.account_id for a in appts if a.account_id]
        accounts_map = {}
        if account_ids:
            accounts = db.query(Account).filter(Account.id.in_(account_ids)).all()
            accounts_map = {acc.id: acc for acc in accounts}

        # Collect patient names
        patient_names = []
        for _appt in appts:
            if _appt.account_id and _appt.account_id in accounts_map:
                patient_names.append(accounts_map[_appt.account_id].name)
            if _appt.guests:
                for guest in _appt.guests:
                    guest_name = guest.get('name', 'Guest')
                    patient_names.append(guest_name)

        # Format patient names as comma-separated list
        patient_name = ", ".join(patient_names) if patient_names else "Guest"

        # Format date and time
        appointment_datetime = appointment.start_datetime.astimezone(sgtz)
        appointment_date = appointment_datetime.strftime("%d %B %Y")  # e.g., "13 October 2025"
        appointment_time = appointment_datetime.strftime("%I:%M %p")  # e.g., "02:30 PM"

        # Get service names
        service_groups = appointment.get_services()
        service_names = ", ".join([
            f"{service_group.name} ({', '.join(service_item.name for service_item in service_group.items)})"
            for service_group in service_groups
        ]) or "No services selected"

        # Get prepayment amount
        payment_breakdown = appointment.get_payment_breakdown()
        prepayment_amount = payment_breakdown.total if payment_breakdown.total > 0 else None

        # Get corporate code information
        corporate_info = "NA"
        if appointment.corporate_code:
            corporate_code_obj = db.query(AppointmentCorporateCode).filter(
                AppointmentCorporateCode.code == appointment.corporate_code
            ).first()
            if corporate_code_obj:
                corporate_info = f"{appointment.corporate_code} - {corporate_code_obj.organization}"
            else:
                corporate_info = appointment.corporate_code

        # Use template from backend_configs
        subject = email_template.get("title", "New Appointment Booking - PinnacleSG+ App")
        body_template = email_template.get("body", "")

        # Format prepayment line
        prepayment_line = f"S${prepayment_amount:.2f}" if prepayment_amount and prepayment_amount > 0 else "S$0.00"

        # Template variables: {clinic_name}, {patient_name}, {appointment_date}, {appointment_time}, {service_names}, {prepayment}, {corporate}
        try:
            body = body_template.format(
                clinic_name=branch.name,
                patient_name=patient_name,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                service_names=service_names,
                prepayment=prepayment_line,
                corporate=corporate_info
            )
        except KeyError as e:
            logging.error(f"Template formatting error for appointment {appointment.id}: missing variable {e}")
            return False

        # Convert plain text to HTML (preserve line breaks and escape HTML entities)
        html_content = html.escape(body).replace('\n', '<br>\n')

        return send_email(
            from_email=from_email,
            to_email=branch.email,
            subject=subject,
            html=html_content,
            cc_emails=cc_emails
        )
    finally:
        db.close()
