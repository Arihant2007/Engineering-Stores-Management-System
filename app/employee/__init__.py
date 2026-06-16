from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models import (
    Request, Material, InventorySnapshot, ApprovalRule,
    AuditLog, Notification, User
)
from app.notifications import send_notification, send_email_notification
import threading
import logging
from flask import current_app

logger = logging.getLogger(__name__)

employee = Blueprint('employee', __name__)


def employee_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.is_admin():
            flash('Access denied. Administrator accounts cannot create requisitions.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def generate_request_number():
    today = date.today()
    prefix = f"MR-{today.strftime('%Y%m%d')}-"
    count = Request.query.filter(
        Request.request_number.like(f'{prefix}%')
    ).count()
    return f"{prefix}{str(count + 1).zfill(4)}"


def determine_approval_levels(amount):
    """Determine required approval levels based on amount and configured rules."""
    from flask import current_app
    if not current_app.config.get('ENABLE_LEVEL_2_APPROVAL', False):
        return 1

    rules = ApprovalRule.query.filter_by(is_active=True).order_by(ApprovalRule.min_amount).all()
    if rules:
        for rule in reversed(rules):
            min_amt = float(rule.min_amount) if rule.min_amount else 0
            max_amt = float(rule.max_amount) if rule.max_amount else float('inf')
            if min_amt <= float(amount) <= max_amt:
                return rule.required_levels
    # Default: <=3000 => L1 only, >3000 => L1+L2
    return 1 if float(amount) <= 3000 else 2


@employee.route('/dashboard')
@login_required
@employee_required
def dashboard():
    page = request.args.get('page', 1, type=int)
    my_requests = Request.query.filter_by(user_id=current_user.id).order_by(
        Request.created_at.desc()
    ).paginate(page=page, per_page=10, error_out=False)

    stats = {
        'total': Request.query.filter_by(user_id=current_user.id).count(),
        'pending': Request.query.filter_by(user_id=current_user.id, status='Pending Approval').count(),
        'approved': Request.query.filter_by(user_id=current_user.id, status='Approved').count(),
        'rejected': Request.query.filter_by(user_id=current_user.id, status='Rejected').count(),
        'issued': Request.query.filter_by(user_id=current_user.id, status='Issued').count(),
    }
    return render_template('employee/dashboard.html', my_requests=my_requests, stats=stats)


@employee.route('/request/create', methods=['GET', 'POST'])
@login_required
@employee_required
def create_request():
    active_snapshot = InventorySnapshot.query.filter_by(is_active=True).first()

    if not active_snapshot:
        flash('No active inventory available. Please wait for the Store Manager to upload today\'s inventory.', 'warning')
        return redirect(url_for('employee.dashboard'))

    if request.method == 'POST':
        material_id = request.form.get('material_id', type=int)
        quantity_required = request.form.get('quantity_required', type=float)
        cost_center = request.form.get('cost_center', '').strip()
        gl_code = request.form.get('gl_code', '').strip()
        purpose = request.form.get('purpose', '').strip()

        # Validation
        errors = []
        if not material_id:
            errors.append('Please select a material.')
        if quantity_required is None or quantity_required <= 0:
            flash('Quantity must be greater than zero.', 'danger')
            return redirect(url_for('employee.create_request'))

        material = None
        if material_id:
            material = Material.query.get(material_id)
            if not material:
                errors.append('Invalid material selected.')
            elif quantity_required and float(material.available_stock) > 0 and quantity_required > float(material.available_stock):
                errors.append(f'Quantity exceeds available stock ({float(material.available_stock)} {material.uom}).')
                
            if material and quantity_required:
                COUNT_BASED_UOM = ['NO', 'NOS', 'PCS', 'EA', 'UNIT']
                if material.uom.upper() in COUNT_BASED_UOM:
                    if not float(quantity_required).is_integer():
                        errors.append(f'Decimal quantities are not allowed for {material.uom}. Please enter a whole number.')


        if errors:
            for e in errors:
                flash(e, 'danger')
            materials = Material.query.filter_by(snapshot_id=active_snapshot.id).order_by(Material.material_description).all()
            return render_template('employee/create_request.html',
                                   materials=materials,
                                   active_snapshot=active_snapshot)

        amount = float(quantity_required) * float(material.unit_rate)
        required_levels = determine_approval_levels(amount)

        req = Request(
            request_number=generate_request_number(),
            user_id=current_user.id,
            snapshot_id=active_snapshot.id,
            material_id=material.id,
            requester_name=current_user.full_name,
            requester_email=current_user.email,
            department=current_user.department or request.form.get('department', ''),
            material_code=material.material_code,
            material_description=material.material_description,
            uom=material.uom,
            unit_rate=material.unit_rate,
            available_stock=material.available_stock,
            quantity_required=quantity_required,
            amount=amount,
            cost_center=cost_center,
            gl_code=gl_code,
            purpose=purpose,
            status='Pending Approval',
            required_approval_levels=required_levels,
            current_approval_level=0
        )
        db.session.add(req)

        log = AuditLog(
            user_id=current_user.id,
            action='CREATE_REQUEST',
            entity_type='Request',
            details=f'Created request for {material.material_description}, qty={quantity_required}',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.flush()

        log.entity_id = req.id
        db.session.commit()

        # Notify Level 1 approvers
        l1_approvers = User.query.filter_by(role='approver_l1', is_active=True).all()
        approver_emails = [a.email for a in l1_approvers if a.email and a.email.strip()]
        
        logger.info(f"Requisition {req.request_number} created. Notifying L1 approvers: {', '.join(approver_emails) if approver_emails else 'None'}")
        
        app_obj = current_app._get_current_object()
        
        email_body = f"""
        A new material requisition requires your approval.
        
        Details:
        - Request ID: {req.request_number}
        - Employee Name: {req.requester_name}
        - Material Name: {req.material_description}
        - Quantity: {req.quantity_required} {req.uom}
        - Cost Center: {req.cost_center or 'N/A'}
        - GL Code: {req.gl_code or 'N/A'}
        - Request Amount: Rs. {req.amount:,.2f}
        - Date & Time: {req.created_at.strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        for email_addr in approver_emails:
            t = threading.Thread(
                target=send_email_notification,
                args=(app_obj, email_addr, "Approver", 'New Material Requisition Awaiting Approval', email_body, req)
            )
            t.daemon = True
            t.start()

        # Notify Level 1 approvers in-app
        l1_approvers = User.query.filter_by(role='approver_l1', is_active=True).all()
        for approver in l1_approvers:
            send_notification(
                user_id=approver.id,
                request_id=req.id,
                title='New Requisition Pending Approval',
                message=f'Request {req.request_number} from {current_user.full_name} requires your approval. Amount: Rs. {amount:,.2f}',
                notification_type='request_created'
            )

        flash(f'Requisition {req.request_number} submitted successfully.', 'success')
        return redirect(url_for('employee.view_request', request_id=req.id))

    materials = Material.query.filter_by(snapshot_id=active_snapshot.id).order_by(Material.material_description).all()
    return render_template('employee/create_request.html',
                           materials=materials,
                           active_snapshot=active_snapshot)


@employee.route('/request/<int:request_id>')
@login_required
def view_request(request_id):
    req = Request.query.get_or_404(request_id)

    # Employees can only view their own requests (admins and store managers can view all)
    if current_user.is_employee() and req.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('employee.dashboard'))

    approvals = sorted(req.approvals, key=lambda a: a.actioned_at)
    return render_template('employee/view_request.html', req=req, approvals=approvals)


@employee.route('/requests')
@login_required
@employee_required
def my_requests():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')

    query = Request.query.filter_by(user_id=current_user.id)
    if status_filter:
        query = query.filter_by(status=status_filter)
    if search:
        query = query.filter(
            db.or_(
                Request.request_number.ilike(f'%{search}%'),
                Request.material_description.ilike(f'%{search}%')
            )
        )

    pagination = query.order_by(Request.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('employee/my_requests.html',
                           pagination=pagination,
                           status_filter=status_filter,
                           search=search)
