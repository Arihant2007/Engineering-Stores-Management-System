from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from app import db
from app.models import Notification, Request, User, InventorySnapshot
from app.notifications import get_unread_count
from sqlalchemy import func, desc

main = Blueprint('main', __name__)


@main.app_context_processor
def inject_globals():
    """Inject global template variables."""
    def get_pending_count():
        if not current_user.is_authenticated:
            return 0
        if current_user.role == 'approver_l1':
            return Request.query.filter_by(status='Pending Approval', current_approval_level=0).count()
        elif current_user.role == 'approver_l2':
            return Request.query.filter(
                Request.status == 'Pending Approval',
                Request.current_approval_level == 1,
                Request.required_approval_levels == 2
            ).count()
        return 0

    def now():
        return datetime.utcnow()

    return dict(get_pending_count=get_pending_count, now=now)


@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main.route('/dashboard')
@login_required
def dashboard():
    from app.models import Request, Notification, InventorySnapshot

    role = current_user.role
    active_snapshot = InventorySnapshot.query.filter_by(is_active=True).first()

    # Common stats
    unread_notifications = get_unread_count(current_user.id)

    if role == 'admin':
        total_users = User.query.count()
        total_requests = Request.query.count()
        pending = Request.query.filter_by(status='Pending Approval').count()
        approved = Request.query.filter_by(status='Approved').count()
        issued = Request.query.filter_by(status='Issued').count()
        rejected = Request.query.filter_by(status='Rejected').count()

        # Top materials
        top_materials = db.session.query(
            Request.material_description,
            func.count(Request.id).label('count'),
            func.sum(Request.amount).label('total')
        ).group_by(Request.material_description).order_by(desc('count')).limit(5).all()

        # Top departments
        top_depts = db.session.query(
            Request.department,
            func.count(Request.id).label('count')
        ).group_by(Request.department).order_by(desc('count')).limit(5).all()

        # Recent requests for dashboard list
        recent_requests = Request.query.order_by(Request.created_at.desc()).limit(10).all()

        return render_template('main/dashboard.html',
                               total_users=total_users,
                               total_requests=total_requests,
                               pending=pending,
                               approved=approved,
                               issued=issued,
                               rejected=rejected,
                               top_materials=top_materials,
                               top_depts=top_depts,
                               recent_requests=recent_requests,
                               active_snapshot=active_snapshot,
                               unread_notifications=unread_notifications)

    elif role == 'store_manager':
        return redirect(url_for('store.dashboard'))

    elif role in ('approver_l1', 'approver_l2'):
        return redirect(url_for('approver.dashboard'))

    else:
        return redirect(url_for('employee.dashboard'))


@main.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    pagination = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).paginate(page=page, per_page=20, error_out=False)

    # Mark all as read
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()

    return render_template('main/notifications.html', pagination=pagination)


@main.route('/api/notifications/count')
@login_required
def notification_count():
    count = get_unread_count(current_user.id)
    return jsonify({'count': count})


@main.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200



