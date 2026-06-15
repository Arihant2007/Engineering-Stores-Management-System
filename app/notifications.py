import threading
from flask import current_app
from flask_mail import Message
from app import db, mail
from app.models import Notification


def send_notification(user_id, request_id, title, message, notification_type):
    """Create in-app notification and send email."""
    # In-app notification
    notification = Notification(
        user_id=user_id,
        request_id=request_id,
        title=title,
        message=message,
        notification_type=notification_type
    )
    db.session.add(notification)
    db.session.commit()

    # Send email in background thread
    from app.models import User, Request
    user = User.query.get(user_id)
    req = Request.query.get(request_id) if request_id else None

    if user and user.email:
        app = current_app._get_current_object()
        t = threading.Thread(
            target=send_email_notification,
            args=(app, user.email, user.full_name, title, message, req)
        )
        t.daemon = True
        t.start()


def send_email_notification(app, recipient_email, recipient_name, title, message, req=None):
    """Send email notification via Gmail SMTP."""
    with app.app_context():
        try:
            app.logger.info(f"Email send started to {recipient_email} with subject '{title}'")

            request_details = ''
            if req:
                request_details = f"""
                <tr><td style="padding:8px;background:#f8f9fa;font-weight:bold;">Request Number</td><td style="padding:8px;">{req.request_number}</td></tr>
                <tr><td style="padding:8px;font-weight:bold;">Material</td><td style="padding:8px;">{req.material_description}</td></tr>
                <tr><td style="padding:8px;background:#f8f9fa;font-weight:bold;">Quantity</td><td style="padding:8px;">{float(req.quantity_required) if req.quantity_required else 0} {req.uom}</td></tr>
                <tr><td style="padding:8px;font-weight:bold;">Amount</td><td style="padding:8px;">Rs. {float(req.amount):,.2f}</td></tr>
                <tr><td style="padding:8px;background:#f8f9fa;font-weight:bold;">Status</td><td style="padding:8px;">{req.status}</td></tr>
                """

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head><meta charset="UTF-8"></head>
            <body style="font-family:Arial,sans-serif;background:#f4f6f9;margin:0;padding:20px;">
              <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
                <div style="background:#1B3A5C;padding:20px;text-align:center;">
                  <h2 style="color:#fff;margin:0;font-size:18px;">Engineering Stores Management System</h2>
                </div>
                <div style="padding:30px;">
                  <h3 style="color:#1B3A5C;margin-top:0;">{title}</h3>
                  <p style="color:#555;">Dear {recipient_name},</p>
                  <p style="color:#555;">{message}</p>
                  {f'<table style="width:100%;border-collapse:collapse;margin-top:20px;">{request_details}</table>' if request_details else ''}
                  <p style="color:#888;font-size:12px;margin-top:30px;border-top:1px solid #eee;padding-top:15px;">
                    This is an automated notification from the Engineering Stores Management System.
                  </p>
                </div>
              </div>
            </body>
            </html>
            """

            msg = Message(
                subject=f'[ESMS] {title}',
                recipients=[recipient_email],
                html=html_body,
                sender=app.config.get('MAIL_DEFAULT_SENDER', app.config.get('MAIL_USERNAME'))
            )
            mail.send(msg)
            app.logger.info("Email sent successfully")
        except Exception as e:
            app.logger.error(f'Email send failed with exception details: {str(e)}')


def get_unread_count(user_id):
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()


def mark_notifications_read(user_id):
    Notification.query.filter_by(user_id=user_id, is_read=False).update({'is_read': True})
    db.session.commit()
