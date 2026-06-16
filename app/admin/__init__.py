from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
import secrets
from app import db
from app.models import User, AuditLog, ApprovalRule, Notification, Request

admin = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@admin.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()
    users_by_role = db.session.query(User.role, db.func.count(User.id)).group_by(User.role).all()
    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           active_users=active_users,
                           recent_logs=recent_logs,
                           users_by_role=users_by_role)


@admin.route('/users')
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    role_filter = request.args.get('role', '')

    query = User.query.filter_by(is_archived=False)
    if search:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{search}%'),
                User.full_name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    if role_filter:
        query = query.filter_by(role=role_filter)

    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/users.html',
                           pagination=pagination,
                           search=search,
                           role_filter=role_filter,
                           roles=User.ROLES)


@admin.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        employee_id = request.form.get('employee_id', '').strip()
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        department = request.form.get('department', '').strip()
        role = request.form.get('role', '')
        password = request.form.get('password', '')

        errors = []
        if not username:
            errors.append('Username is required.')
        if not email:
            errors.append('Email is required.')
        if not full_name:
            errors.append('Full name is required.')
        if role not in User.ROLES:
            errors.append('Invalid role selected.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if User.query.filter_by(username=username).first():
            errors.append('Username already exists.')
        if User.query.filter_by(email=email).first():
            errors.append('Email already exists.')
        if employee_id and User.query.filter_by(employee_id=employee_id).first():
            errors.append('Employee ID already exists.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('admin/create_user.html', roles=User.ROLES)

        user = User(
            username=username,
            employee_id=employee_id if employee_id else None,
            email=email,
            full_name=full_name,
            department=department,
            role=role,
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)

        log = AuditLog(
            user_id=current_user.id,
            action='CREATE_USER',
            entity_type='User',
            details=f'Created user {username} with role {role}',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

        flash(f'User {full_name} created successfully.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/create_user.html', roles=User.ROLES)


@admin.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.full_name = request.form.get('full_name', '').strip()
        user.email = request.form.get('email', '').strip()
        
        employee_id = request.form.get('employee_id', '').strip()
        if employee_id:
            user.employee_id = employee_id
        else:
            user.employee_id = None
            
        user.department = request.form.get('department', '').strip()
        user.role = request.form.get('role', '')
        user.is_active = request.form.get('is_active') == 'on'

        new_password = request.form.get('new_password', '')
        if new_password:
            if len(new_password) < 8:
                flash('Password must be at least 8 characters.', 'danger')
                return render_template('admin/edit_user.html', user=user, roles=User.ROLES)
            user.set_password(new_password)

        db.session.commit()
        flash(f'User {user.full_name} updated successfully.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/edit_user.html', user=user, roles=User.ROLES)


@admin.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
    else:
        user.is_active = not user.is_active
        if not user.is_active:
            user.deactivated_at = datetime.utcnow()
        else:
            user.deactivated_at = None
        db.session.commit()
        status = 'activated' if user.is_active else 'deactivated'
        flash(f'User {user.full_name} {status} successfully.', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.role == 'Administrator' or user.role == 'admin':
        flash('Administrator accounts cannot be deleted.', 'danger')
        return redirect(url_for('admin.users'))

    # Check for historical activity
    has_activity = False
    if user.requests.first() or user.approvals.first() or user.issued_materials.first() or user.notifications.first() or AuditLog.query.filter_by(user_id=user.id).first():
        has_activity = True

    if has_activity:
        flash('User cannot be deleted because historical records exist. Please deactivate the account instead.', 'danger')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully.', 'success')

    return redirect(url_for('admin.users'))


@admin.route('/users/<int:user_id>/reset_password', methods=['POST'])
@login_required
@admin_required
def reset_user_password(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot reset your own password through this action. Please use the Change Password page.', 'danger')
        return redirect(url_for('admin.users'))
        
    if not user.is_active:
        flash(f'Cannot reset password for inactive user {user.full_name}.', 'warning')
        return redirect(url_for('admin.users'))
        
    # Generate temporary password
    temp_pw = f"TEMP-{secrets.token_hex(4).upper()}"
    
    # Update password
    user.set_password(temp_pw)
    
    # Audit log
    log = AuditLog(
        user_id=current_user.id,
        action='ADMIN_PASSWORD_RESET',
        entity_type='User',
        entity_id=user.id,
        details=f'Password reset by admin for user {user.username} ({user.email})',
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    # Display temp password to admin
    flash(f'Password successfully reset for {user.full_name}. The temporary password is: {temp_pw}', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/maintenance/cleanup', methods=['POST'])
@login_required
@admin_required
def run_maintenance():
    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=25)
    
    # Find deactivated users older than 25 days who aren't already archived
    users_to_archive = User.query.filter(
        User.is_active == False,
        User.is_archived == False,
        User.deactivated_at != None,
        User.deactivated_at < cutoff_date
    ).all()

    count = 0
    for u in users_to_archive:
        u.is_archived = True
        count += 1

    if count > 0:
        db.session.commit()
        flash(f'Maintenance complete. Archived {count} inactive user(s).', 'success')
    else:
        flash('Maintenance complete. No users required archiving.', 'info')

    return redirect(url_for('admin.users'))


@admin.route('/audit-logs')
@login_required
@admin_required
def audit_logs():
    page = request.args.get('page', 1, type=int)
    pagination = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template('admin/audit_logs.html', pagination=pagination)


@admin.route('/approval-rules')
@login_required
@admin_required
def approval_rules():
    rules = ApprovalRule.query.order_by(ApprovalRule.min_amount).all()
    return render_template('admin/approval_rules.html', rules=rules)


@admin.route('/approval-rules/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_approval_rule():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        min_amount = float(request.form.get('min_amount', 0))
        max_amount = request.form.get('max_amount', '')
        required_levels = int(request.form.get('required_levels', 1))

        rule = ApprovalRule(
            name=name,
            min_amount=min_amount,
            max_amount=float(max_amount) if max_amount else None,
            required_levels=required_levels
        )
        db.session.add(rule)
        db.session.commit()
        flash('Approval rule created.', 'success')
        return redirect(url_for('admin.approval_rules'))

    return render_template('admin/create_approval_rule.html')


@admin.route('/approval-rules/<int:rule_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_approval_rule(rule_id):
    rule = ApprovalRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    flash('Approval rule deleted.', 'success')
    return redirect(url_for('admin.approval_rules'))
