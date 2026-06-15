from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from flask import current_app
from flask_mail import Message
from app import db, mail
from app.models import User, AuditLog
import logging

logger = logging.getLogger(__name__)

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        employee_id = request.form.get('employee_id', '').strip()
        full_name = request.form.get('full_name', '').strip()
        department = request.form.get('department', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not employee_id or not full_name or not email or not password:
            flash('Please fill out all required fields.', 'danger')
            return render_template('auth/register.html')
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter((db.func.lower(User.email) == email.lower())).first():
            flash('A user with that email already exists.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(employee_id=employee_id).first():
            flash('A user with that Employee ID already exists.', 'danger')
            return render_template('auth/register.html')
            
        if User.query.filter_by(username=employee_id).first():
            flash('That Employee ID is already in use as a username.', 'danger')
            return render_template('auth/register.html')

        user = User(
            username=employee_id,
            employee_id=employee_id,
            full_name=full_name,
            department=department,
            email=email,
            role='employee',
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        log = AuditLog(
            user_id=user.id,
            action='REGISTER',
            entity_type='User',
            entity_id=user.id,
            details=f'New employee self-registered: {user.employee_id}',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')



@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('auth/login.html')

        user = User.query.filter(
            (db.func.lower(User.username) == username.lower()) |
            (db.func.lower(User.email) == username.lower())
        ).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Contact administrator.', 'danger')
                return render_template('auth/login.html')

            login_user(user, remember=False)
            user.last_login = datetime.utcnow()
            db.session.commit()

            # Audit log
            log = AuditLog(
                user_id=user.id,
                action='LOGIN',
                entity_type='User',
                entity_id=user.id,
                details=f'User {user.username} logged in',
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('auth/login.html')


@auth.route('/logout')
@login_required
def logout():
    log = AuditLog(
        user_id=current_user.id,
        action='LOGOUT',
        entity_type='User',
        entity_id=current_user.id,
        details=f'User {current_user.username} logged out',
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()

    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'danger')
            return render_template('auth/change_password.html')

        if len(new_password) < 8:
            flash('New password must be at least 8 characters long.', 'danger')
            return render_template('auth/change_password.html')

        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return render_template('auth/change_password.html')

        current_user.set_password(new_password)
        db.session.commit()

        flash('Password changed successfully.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('auth/change_password.html')

def send_password_reset_email(user):
    logger.info(f"Sending password reset email to {user.email}...")
    token = user.get_reset_password_token()
    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or 'noreply@esms.com'
    msg = Message('[ESMS] Reset Your Password',
                  sender=sender,
                  recipients=[user.email])
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    msg.body = f'''To reset your password, visit the following link:
{reset_url}

If you did not make this request then simply ignore this email and no changes will be made.
'''
    msg.html = f'''<p>To reset your password, visit the following link:</p>
<p><a href="{reset_url}">Reset Password</a></p>
<p>If you did not make this request then simply ignore this email and no changes will be made.</p>
'''
    logger.info(f"Preparing to send mail.send()...")
    logger.info(f"msg.sender: {msg.sender}")
    logger.info(f"msg.recipients: {msg.recipients}")
    logger.info(f"msg.subject: {msg.subject}")
    logger.info(f"MAIL_SERVER: {current_app.config.get('MAIL_SERVER')}")
    logger.info(f"MAIL_PORT: {current_app.config.get('MAIL_PORT')}")
    logger.info(f"MAIL_USE_TLS: {current_app.config.get('MAIL_USE_TLS')}")
    logger.info(f"MAIL_USERNAME: {current_app.config.get('MAIL_USERNAME')}")
    
    try:
        mail.send(msg)
        logger.info("Password reset email sent successfully")
    except Exception as e:
        logger.exception("Password reset email failed")

@auth.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        logger.info(f"Received password reset request for email: {email}")
        user = User.query.filter_by(email=email).first()
        if user:
            logger.info(f"User found for email {email}, proceeding to send email")
            send_password_reset_email(user)
        else:
            logger.info(f"No user found for email {email}, skipping email send")
        flash('Check your email for the instructions to reset your password', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password_request.html')

@auth.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    user = User.verify_reset_password_token(token)
    if not user:
        flash('Invalid or expired reset token', 'danger')
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if not password or len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
        elif password != confirm_password:
            flash('Passwords do not match.', 'danger')
        else:
            user.set_password(password)
            db.session.commit()
            flash('Your password has been reset.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', token=token)

@auth.route('/test_email')
def test_email():
    if not current_user.is_authenticated or not current_user.is_admin():
        return "Unauthorized", 401
    
    to_email = request.args.get('to', current_user.email)
    sender = current_app.config.get('MAIL_DEFAULT_SENDER') or 'noreply@esms.com'
    subject = f"SMTP Test {datetime.utcnow().isoformat()}"
    
    msg = Message(subject,
                  sender=sender,
                  recipients=[to_email])
    msg.body = 'This is a test email.'
    
    logger.info(f"TEST EMAIL - Preparing to send mail.send()...")
    logger.info(f"TEST EMAIL - msg.sender: {msg.sender}")
    logger.info(f"TEST EMAIL - msg.recipients: {msg.recipients}")
    logger.info(f"TEST EMAIL - msg.subject: {msg.subject}")
    logger.info(f"TEST EMAIL - MAIL_SERVER: {current_app.config.get('MAIL_SERVER')}")
    logger.info(f"TEST EMAIL - MAIL_PORT: {current_app.config.get('MAIL_PORT')}")
    logger.info(f"TEST EMAIL - MAIL_USE_TLS: {current_app.config.get('MAIL_USE_TLS')}")
    logger.info(f"TEST EMAIL - MAIL_USERNAME: {current_app.config.get('MAIL_USERNAME')}")
    logger.info(f"TEST EMAIL - MAIL_SUPPRESS_SEND: {current_app.config.get('MAIL_SUPPRESS_SEND')}")
    
    try:
        logger.info("TEST EMAIL - Executing mail.send(msg) synchronously now...")
        mail.send(msg)
        logger.info("TEST EMAIL - mail.send(msg) completed successfully without exceptions.")
        return f"Email supposedly sent to {to_email}. Check logs for details."
    except Exception as e:
        logger.exception("TEST EMAIL - SMTP Exception caught during mail.send(msg)")
        return f"Failed to send email: {str(e)}", 500
