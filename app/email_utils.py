import os
import logging
import requests
from flask import has_app_context, current_app

logger = logging.getLogger(__name__)

def send_email(to, subject, html_content, text_content=None):
    """
    Sends an email using the Resend API.
    
    :param to: A string or list/iterable of recipient email addresses.
    :param subject: The email subject.
    :param html_content: The HTML body of the email.
    :param text_content: Optional plain text body of the email.
    :return: True if successful, False otherwise.
    """
    # Check suppression and config within or outside app context
    suppress = False
    api_key = None
    sender = None

    if has_app_context():
        suppress = current_app.config.get('MAIL_SUPPRESS_SEND', False)
        api_key = current_app.config.get('RESEND_API_KEY') or os.environ.get('RESEND_API_KEY')
        sender = current_app.config.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_DEFAULT_SENDER', 'onboarding@resend.dev')
    else:
        suppress = os.environ.get('MAIL_SUPPRESS_SEND', 'false').lower() == 'true'
        api_key = os.environ.get('RESEND_API_KEY')
        sender = os.environ.get('MAIL_DEFAULT_SENDER', 'onboarding@resend.dev')

    # Standardize recipient list (Resend API expects an array of strings for "to")
    if isinstance(to, str):
        to_list = [to]
    else:
        to_list = list(to)


    if suppress:
        logger.info(f"[SUPPRESSED] Email to {to_list} with subject '{subject}' was not sent because MAIL_SUPPRESS_SEND is True.")
        return True

    if not api_key:
        logger.error("RESEND_API_KEY is not set. Cannot send email.")
        return False

    payload = {
        "from": sender,
        "to": to_list,
        "subject": subject,
        "html": html_content
    }
    if text_content:
        payload["text"] = text_content

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        logger.info(f"Sending email via Resend to {to_list} with subject: '{subject}'")
        response = requests.post(
            "https://api.resend.com/emails",
            headers=headers,
            json=payload,
            timeout=15
        )
        
        logger.info(f"Resend API response status code: {response.status_code}")
        
        try:
            resp_data = response.json()
            logger.info(f"Resend API response JSON: {resp_data}")
        except Exception:
            logger.info(f"Resend API response raw content: {response.text}")

        if response.status_code in (200, 201):
            logger.info("Email sent successfully via Resend API.")
            return True
        else:
            logger.error(f"Failed to send email via Resend API. Status code: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        logger.exception(f"Exception occurred while sending email via Resend: {str(e)}")
        return False
