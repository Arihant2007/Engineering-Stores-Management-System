import os
import uuid
import pandas as pd
from datetime import datetime, date, time
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import func, and_
from app import db
from app.models import (
    InventorySnapshot, Material, Request, IssuedMaterial,
    AuditLog, Notification, User
)
from app.notifications import send_notification, send_email_notification
import threading

store = Blueprint('store', __name__)


def store_manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_store_manager() or current_user.is_admin()):
            flash('Access denied. Store Manager privileges required.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename):
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'xlsx', 'xls'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


@store.route('/dashboard')
@login_required
@store_manager_required
def dashboard():
    today = date.today()
    active_snapshot = InventorySnapshot.query.filter_by(is_active=True).first()

    total_requests = Request.query.count()
    approved_requests = Request.query.filter_by(status='Approved').count()
    pending_requests = Request.query.filter_by(status='Pending Approval').count()
    issued_requests = Request.query.filter_by(status='Issued').count()

    recent_requests = Request.query.filter_by(status='Approved').order_by(Request.created_at.desc()).limit(10).all()

    return render_template('store/dashboard.html',
                           active_snapshot=active_snapshot,
                           today=today,
                           total_requests=total_requests,
                           approved_requests=approved_requests,
                           pending_requests=pending_requests,
                           issued_requests=issued_requests,
                           recent_requests=recent_requests)


@store.route('/inventory/upload', methods=['GET', 'POST'])
@login_required
@store_manager_required
def upload_inventory():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected.', 'danger')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Invalid file type. Only .xlsx and .xls files are allowed.', 'danger')
            return redirect(request.url)

        # Save file
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"inventory_{timestamp}_{uuid.uuid4().hex[:8]}.xlsx"
        filepath = os.path.join(upload_folder, safe_filename)
        file.save(filepath)

        # Process
        result = process_inventory_file(filepath, safe_filename)

        if result['success']:
            flash(f"Inventory uploaded successfully. {result['valid_items']} valid items loaded. "
                  f"{result['duplicate_items']} duplicates removed.", 'success')
            return redirect(url_for('store.inventory_history'))
        else:
            flash(f"Error processing file: {result['error']}", 'danger')
            return redirect(request.url)

    snapshots = InventorySnapshot.query.order_by(InventorySnapshot.created_at.desc()).limit(5).all()
    return render_template('store/upload_inventory.html', snapshots=snapshots)


def process_inventory_file(filepath, filename):
    try:
        # Read Excel
        df = pd.read_excel(filepath, dtype=str)
        df.columns = [str(col).strip() for col in df.columns]

        # Column mapping (flexible)
        col_map = {}
        for col in df.columns:
            col_lower = col.lower().replace(' ', '_')
            if 'material_code' in col_lower or 'material code' in col.lower():
                col_map['material_code'] = col
            elif 'description' in col_lower:
                col_map['material_description'] = col
            elif 'uom' in col_lower or 'unit_of_measure' in col_lower:
                col_map['uom'] = col
            elif 'rate' in col_lower or 'unit_rate' in col_lower:
                col_map['unit_rate'] = col
            elif 'stock' in col_lower or 'available' in col_lower:
                col_map['available_stock'] = col
            elif 'gl_code' in col_lower or 'gl code' in col.lower():
                col_map['gl_code'] = col
            elif 'cost_center' in col_lower or 'cost center' in col.lower():
                col_map['cost_center'] = col

        total_rows = len(df)
        validation_issues = []

        # Validate required columns
        if 'material_code' not in col_map:
            return {'success': False, 'error': 'Material Code column not found in file.'}
        if 'material_description' not in col_map:
            return {'success': False, 'error': 'Material Description column not found in file.'}

        # Rename columns
        df = df.rename(columns={v: k for k, v in col_map.items()})

        # Drop empty rows
        df = df.dropna(subset=['material_code'])
        df['material_code'] = df['material_code'].astype(str).str.strip()
        df = df[df['material_code'] != '']
        df = df[df['material_code'] != 'nan']

        # Check missing descriptions
        missing_desc = df[df.get('material_description', pd.Series(dtype=str)).isna()].shape[0] if 'material_description' in df.columns else 0
        if missing_desc > 0:
            validation_issues.append(f'{missing_desc} rows with missing Material Description')

        # Remove duplicates
        before_dedup = len(df)
        df = df.drop_duplicates(subset=['material_code'], keep='first')
        duplicate_count = before_dedup - len(df)
        if duplicate_count > 0:
            validation_issues.append(f'{duplicate_count} duplicate Material Codes removed')

        # Parse numeric columns
        def safe_numeric(val, default=0):
            try:
                return float(str(val).replace(',', '')) if pd.notna(val) and str(val) not in ('', 'nan') else default
            except (ValueError, TypeError):
                return default

        # Deactivate all previous snapshots
        InventorySnapshot.query.update({'is_active': False})
        db.session.flush()

        # Create new snapshot
        snapshot = InventorySnapshot(
            snapshot_date=date.today(),
            filename=filename,
            uploaded_by=current_user.id,
            is_active=True,
            total_items=total_rows,
            duplicate_items=duplicate_count,
            valid_items=len(df),
            validation_summary='; '.join(validation_issues) if validation_issues else 'No issues found'
        )
        db.session.add(snapshot)
        db.session.flush()

        # Insert materials
        materials_to_insert = []
        for _, row in df.iterrows():
            mat = Material(
                snapshot_id=snapshot.id,
                material_code=str(row.get('material_code', '')).strip(),
                material_description=str(row.get('material_description', '')).strip() if pd.notna(row.get('material_description')) else '',
                uom=str(row.get('uom', '')).strip() if pd.notna(row.get('uom')) else '',
                unit_rate=safe_numeric(row.get('unit_rate', 0)),
                available_stock=safe_numeric(row.get('available_stock', 0)),
                gl_code=str(row.get('gl_code', '')).strip() if pd.notna(row.get('gl_code')) else '',
                cost_center=str(row.get('cost_center', '')).strip() if pd.notna(row.get('cost_center')) else '',
            )
            materials_to_insert.append(mat)

        db.session.bulk_save_objects(materials_to_insert)

        # Audit log
        log = AuditLog(
            user_id=current_user.id,
            action='UPLOAD_INVENTORY',
            entity_type='InventorySnapshot',
            entity_id=snapshot.id,
            details=f'Uploaded inventory: {filename}, {len(df)} valid items, {duplicate_count} duplicates removed',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

        return {
            'success': True,
            'valid_items': len(df),
            'duplicate_items': duplicate_count,
            'snapshot_id': snapshot.id
        }

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}


@store.route('/inventory/history')
@login_required
@store_manager_required
def inventory_history():
    page = request.args.get('page', 1, type=int)
    pagination = InventorySnapshot.query.order_by(
        InventorySnapshot.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    return render_template('store/inventory_history.html', pagination=pagination)


@store.route('/inventory/<int:snapshot_id>/view')
@login_required
@store_manager_required
def view_inventory(snapshot_id):
    snapshot = InventorySnapshot.query.get_or_404(snapshot_id)
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')

    query = Material.query.filter_by(snapshot_id=snapshot_id)
    if search:
        query = query.filter(
            db.or_(
                Material.material_code.ilike(f'%{search}%'),
                Material.material_description.ilike(f'%{search}%')
            )
        )

    pagination = query.paginate(page=page, per_page=30, error_out=False)
    return render_template('store/view_inventory.html',
                           snapshot=snapshot,
                           pagination=pagination,
                           search=search)


@store.route('/issuance')
@login_required
@store_manager_required
def issuance_queue():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')

    query = Request.query.filter_by(status='Approved')
    if search:
        query = query.filter(
            db.or_(
                Request.request_number.ilike(f'%{search}%'),
                Request.requester_name.ilike(f'%{search}%'),
                Request.department.ilike(f'%{search}%'),
                Request.material_description.ilike(f'%{search}%')
            )
        )

    pagination = query.order_by(Request.updated_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('store/issuance_queue.html', pagination=pagination, search=search)


@store.route('/issuance/<int:request_id>/issue', methods=['POST'])
@login_required
@store_manager_required
def issue_material(request_id):
    req = Request.query.get_or_404(request_id)

    if req.status != 'Approved':
        flash('Only approved requests can be issued.', 'danger')
        return redirect(url_for('store.issuance_queue'))

    now = datetime.utcnow()
    issued = IssuedMaterial(
        request_id=req.id,
        issued_by=current_user.id,
        issued_date=now.date(),
        issued_time=now.time(),
        remarks=request.form.get('remarks', '')
    )
    req.status = 'Issued'
    db.session.add(issued)

    # Audit log
    log = AuditLog(
        user_id=current_user.id,
        action='ISSUE_MATERIAL',
        entity_type='Request',
        entity_id=req.id,
        details=f'Material issued for request {req.request_number}',
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()

    # Notify employee in-app
    send_notification(
        user_id=req.user_id,
        request_id=req.id,
        title='Material Issued',
        message=f'Your request {req.request_number} for {req.material_description} has been issued.',
        notification_type='issued'
    )
    
    # Send Email to Employee
    if req.requester_email:
        app_obj = current_app._get_current_object()
        emp_email_body = f"""
        Material has been issued for your requisition.
        
        Details:
        - Request ID: {req.request_number}
        - Material Name: {req.material_description}
        - Quantity Issued: {req.quantity_required} {req.uom}
        - Issue Date: {now.strftime('%Y-%m-%d %H:%M:%S')}
        - Issued By: {current_user.full_name}
        """
        t = threading.Thread(
            target=send_email_notification,
            args=(app_obj, req.requester_email, req.requester_name, 'Material Issued Successfully', emp_email_body, req)
        )
        t.daemon = True
        t.start()

    flash(f'Material issued successfully for request {req.request_number}.', 'success')
    return redirect(url_for('store.issuance_queue'))


@store.route('/api/materials')
@login_required
def get_materials():
    """API endpoint for material autocomplete"""
    snapshot = InventorySnapshot.query.filter_by(is_active=True).first()
    if not snapshot:
        return jsonify([])

    search = request.args.get('q', '').strip()
    query = Material.query.filter_by(snapshot_id=snapshot.id)
    if search:
        query = query.filter(
            db.or_(
                Material.material_description.ilike(f'%{search}%'),
                Material.material_code.ilike(f'%{search}%')
            )
        )

    materials = query.limit(50).all()
    return jsonify([{
        'id': m.id,
        'material_code': m.material_code,
        'material_description': m.material_description,
        'uom': m.uom,
        'unit_rate': float(m.unit_rate) if m.unit_rate else 0,
        'available_stock': float(m.available_stock) if m.available_stock else 0,
        'gl_code': m.gl_code,
        'cost_center': m.cost_center,
    } for m in materials])


@store.route('/api/material/<int:material_id>')
@login_required
def get_material(material_id):
    material = Material.query.get_or_404(material_id)
    return jsonify({
        'id': material.id,
        'material_code': material.material_code,
        'material_description': material.material_description,
        'uom': material.uom,
        'unit_rate': float(material.unit_rate) if material.unit_rate else 0,
        'available_stock': float(material.available_stock) if material.available_stock else 0,
        'gl_code': material.gl_code,
        'cost_center': material.cost_center,
    })
