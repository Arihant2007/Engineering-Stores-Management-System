from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models import Request, Approval, AuditLog, User, Notification
from app.notifications import send_notification, send_email_notification
import threading
import logging
from flask import current_app

logger = logging.getLogger(__name__)

approver = Blueprint('approver', __name__)


def approver_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_approver():
            flash('Access denied. Approver privileges required.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def get_pending_requests_for_approver(user):
    """Get requests that this approver can act on."""
    if user.role == 'approver_l1':
        # L1 approver sees requests needing L1 approval (current_level = 0)
        return Request.query.filter_by(
            status='Pending Approval',
            current_approval_level=0
        ).order_by(Request.created_at.asc())
    elif user.role == 'approver_l2':
        # L2 approver sees requests needing L2 approval (current_level = 1, required = 2)
        return Request.query.filter(
            Request.status == 'Pending Approval',
            Request.current_approval_level == 1,
            Request.required_approval_levels == 2
        ).order_by(Request.created_at.asc())
    return Request.query.filter_by(id=None)


@approver.route('/dashboard')
@login_required
@approver_required
def dashboard():
    pending_query = get_pending_requests_for_approver(current_user)
    pending_count = pending_query.count()
    pending_requests = pending_query.limit(10).all()

    # Stats for requests this approver has acted on
    my_approvals = Approval.query.filter_by(approver_id=current_user.id)
    approved_count = my_approvals.filter_by(action='Approved').count()
    rejected_count = my_approvals.filter_by(action='Rejected').count()

    return render_template('approver/dashboard.html',
                           pending_count=pending_count,
                           pending_requests=pending_requests,
                           approved_count=approved_count,
                           rejected_count=rejected_count)


@approver.route('/pending')
@login_required
@approver_required
def pending_requests():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')

    query = get_pending_requests_for_approver(current_user)
    if search:
        query = query.filter(
            db.or_(
                Request.request_number.ilike(f'%{search}%'),
                Request.requester_name.ilike(f'%{search}%'),
                Request.department.ilike(f'%{search}%'),
                Request.material_description.ilike(f'%{search}%')
            )
        )

    pagination = query.paginate(page=page, per_page=20, error_out=False)
    return render_template('approver/pending_requests.html',
                           pagination=pagination,
                           search=search)


@approver.route('/request/<int:request_id>')
@login_required
@approver_required
def view_request(request_id):
    req = Request.query.get_or_404(request_id)
    approvals = req.approvals.order_by('actioned_at').all()
    return render_template('approver/view_request.html', req=req, approvals=approvals)


@approver.route('/request/<int:request_id>/action', methods=['POST'])
@login_required
@approver_required
def action_request(request_id):
    req = Request.query.get_or_404(request_id)
    action = request.form.get('action', '')
    remarks = request.form.get('remarks', '').strip()

    if action not in ('Approved', 'Rejected'):
        flash('Invalid action.', 'danger')
        return redirect(url_for('approver.view_request', request_id=request_id))

    if req.status != 'Pending Approval':
        flash('This request is no longer pending approval.', 'warning')
        return redirect(url_for('approver.pending_requests'))

    # Verify approver can act
    if current_user.role == 'approver_l1' and req.current_approval_level != 0:
        flash('This request is not at Level 1 approval stage.', 'warning')
        return redirect(url_for('approver.pending_requests'))

    if current_user.role == 'approver_l2' and req.current_approval_level != 1:
        flash('This request is not at Level 2 approval stage.', 'warning')
        return redirect(url_for('approver.pending_requests'))

    # Determine approval level
    approval_level = 1 if current_user.role == 'approver_l1' else 2

    # Record approval
    approval = Approval(
        request_id=req.id,
        approver_id=current_user.id,
        approval_level=approval_level,
        action=action,
        remarks=remarks
    )
    db.session.add(approval)

    if action == 'Rejected':
        req.status = 'Rejected'
        # Notify employee
        send_notification(
            user_id=req.user_id,
            request_id=req.id,
            title='Requisition Rejected',
            message=f'Your request {req.request_number} for {req.material_description} has been rejected by {current_user.full_name}. Remarks: {remarks or "None"}',
            notification_type='rejected'
        )
    elif action == 'Approved':
        if req.required_approval_levels == 1 or (req.required_approval_levels == 2 and approval_level == 2):
            # Final approval
            req.status = 'Approved'
            req.current_approval_level = approval_level
            # Notify employee in-app
            send_notification(
                user_id=req.user_id,
                request_id=req.id,
                title='Requisition Approved',
                message=f'Your request {req.request_number} for {req.material_description} has been approved and is ready for issuance.',
                notification_type='approved'
            )
            
            # Notify Store Managers via Email
            store_managers = User.query.filter_by(role='store_manager', is_active=True).all()
            sm_emails = [sm.email for sm in store_managers if sm.email and sm.email.strip()]
            
            logger.info(f"Requisition {req.request_number} approved. Notifying Store Managers: {', '.join(sm_emails) if sm_emails else 'None'}")
            
            app_obj = current_app._get_current_object()
            sm_email_body = f"""
            An approved requisition is awaiting material issue.
            
            Details:
            - Request ID: {req.request_number}
            - Employee Name: {req.requester_name}
            - Material Name: {req.material_description}
            - Quantity: {req.quantity_required} {req.uom}
            - Approval Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}
            """
            for email_addr in sm_emails:
                t1 = threading.Thread(
                    target=send_email_notification,
                    args=(app_obj, email_addr, "Store Manager", 'Approved Requisition Awaiting Material Issue', sm_email_body, req)
                )
                t1.daemon = True
                t1.start()

            # Send Email to Employee
            if req.requester_email:
                emp_email_body = f"Your request {req.request_number} for {req.material_description} has been approved."
                t2 = threading.Thread(
                    target=send_email_notification,
                    args=(app_obj, req.requester_email, req.requester_name, 'Requisition Approved', emp_email_body, req)
                )
                t2.daemon = True
                t2.start()

            # Notify Store Managers in-app
            store_managers = User.query.filter_by(role='store_manager', is_active=True).all()
            for sm in store_managers:
                send_notification(
                    user_id=sm.id,
                    request_id=req.id,
                    title='New Approved Requisition in Queue',
                    message=f'Request {req.request_number} for {req.material_description} has been approved and is pending issuance.',
                    notification_type='approved'
                )
        elif req.required_approval_levels == 2 and approval_level == 1:
            # Move to L2
            req.current_approval_level = 1
            # Notify L2 approvers
            l2_approvers = User.query.filter_by(role='approver_l2', is_active=True).all()
            for l2 in l2_approvers:
                send_notification(
                    user_id=l2.id,
                    request_id=req.id,
                    title='Requisition Pending Level 2 Approval',
                    message=f'Request {req.request_number} from {req.requester_name} requires your approval. Amount: Rs. {float(req.amount):,.2f}',
                    notification_type='request_created'
                )

    # Audit log
    log = AuditLog(
        user_id=current_user.id,
        action=f'REQUEST_{action.upper()}',
        entity_type='Request',
        entity_id=req.id,
        details=f'Request {req.request_number} {action} by {current_user.full_name} (Level {approval_level}). Remarks: {remarks}',
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()

    flash(f'Request {req.request_number} has been {action.lower()}.', 'success')
    return redirect(url_for('approver.pending_requests'))


@approver.route('/history')
@login_required
@approver_required
def approval_history():
    page = request.args.get('page', 1, type=int)
    pagination = Approval.query.filter_by(
        approver_id=current_user.id
    ).order_by(Approval.actioned_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('approver/history.html', pagination=pagination)
