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
        if not current_user.is_authenticated or not current_user.is_store_manager():
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
        # 1. Read without headers to detect the actual header row
        df_raw = pd.read_excel(filepath, dtype=str, header=None)
        
        # Alias dictionaries
        aliases = {
            'material_code': ['material code', 'material', 'item code'],
            'material_description': ['description', 'material description', 'item description'],
            'available_stock': ['quantity', 'stock quantity', 'unrestricted', 'stock'],
            'uom': ['unit', 'uom', 'bun', 'unit of measure'],
            'unit_rate': ['rate', 'unit rate', 'price'],
            'gl_code': ['gl code', 'gl_code'],
            'cost_center': ['cost center', 'cost_center']
        }

        header_row_idx = -1
        col_map = {}
        detected_columns = []

        # Scan first 20 rows
        for i in range(min(20, len(df_raw))):
            row_values = [str(x).strip().lower() for x in df_raw.iloc[i].fillna('')]
            temp_map = {}
            temp_detected = []
            
            for col_idx, cell_val in enumerate(row_values):
                if not cell_val:
                    continue
                    
                # Check against aliases
                for db_field, alias_list in aliases.items():
                    if any(alias in cell_val for alias in alias_list) and db_field not in temp_map:
                        temp_map[db_field] = col_idx
                        temp_detected.append(f"{cell_val} -> {db_field}")
                        break
            
            # If we found at least Material Code and one other required field, we consider it the header
            if 'material_code' in temp_map and ('material_description' in temp_map or 'available_stock' in temp_map):
                header_row_idx = i
                col_map = temp_map
                detected_columns = temp_detected
                break
                
        if header_row_idx == -1:
            return {
                'success': False, 
                'error': f'Could not detect a valid header row. Ensure your file contains a Material Code column (aliases: {", ".join(aliases["material_code"])}).'
            }

        # Re-read with correct header
        df = pd.read_excel(filepath, dtype=str, header=header_row_idx)
        df.columns = [str(col).strip() for col in df.columns]

        # Build final col_name_map from index to name
        final_col_map = {}
        for db_field, col_idx in col_map.items():
            if col_idx < len(df.columns):
                final_col_map[df.columns[col_idx]] = db_field

        # Rename columns to db fields
        df = df.rename(columns=final_col_map)
        
        # Keep only mapped columns
        df = df[list(final_col_map.values())]

        total_rows = len(df)
        validation_issues = [f"Header detected at row {header_row_idx + 1}"]
        validation_issues.append(f"Mapped: {', '.join(detected_columns)}")

        # Drop empty rows
        df = df.dropna(subset=['material_code'])
        df['material_code'] = df['material_code'].astype(str).str.strip()
        df = df[df['material_code'] != '']
        df = df[df['material_code'] != 'nan']

        skipped_rows = total_rows - len(df)
        if skipped_rows > 0:
            validation_issues.append(f"{skipped_rows} rows skipped (blank material code)")

        # Remove duplicates within the file itself
        before_dedup = len(df)
        df = df.drop_duplicates(subset=['material_code'], keep='first')
        duplicate_count = before_dedup - len(df)
        if duplicate_count > 0:
            validation_issues.append(f"{duplicate_count} duplicate rows ignored in file")

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
            validation_summary='; '.join(validation_issues)
        )
        db.session.add(snapshot)
        db.session.flush()

        # Fetch existing materials to update
        existing_materials = {m.material_code: m for m in Material.query.filter(Material.material_code.in_(df['material_code'].tolist())).all()}
        
        materials_to_insert = []
        updated_count = 0
        new_count = 0

        for _, row in df.iterrows():
            code = str(row.get('material_code', '')).strip()
            desc = str(row.get('material_description', '')).strip() if pd.notna(row.get('material_description')) else ''
            uom = str(row.get('uom', '')).strip() if pd.notna(row.get('uom')) else ''
            rate = safe_numeric(row.get('unit_rate', 0))
            stock = safe_numeric(row.get('available_stock', 0))
            gl = str(row.get('gl_code', '')).strip() if pd.notna(row.get('gl_code')) else ''
            cc = str(row.get('cost_center', '')).strip() if pd.notna(row.get('cost_center')) else ''

            if code in existing_materials:
                # Update existing
                mat = existing_materials[code]
                mat.snapshot_id = snapshot.id
                if desc: mat.material_description = desc
                if uom: mat.uom = uom
                mat.unit_rate = rate
                mat.available_stock = stock
                if gl: mat.gl_code = gl
                if cc: mat.cost_center = cc
                updated_count += 1
            else:
                # Insert new
                mat = Material(
                    snapshot_id=snapshot.id,
                    material_code=code,
                    material_description=desc,
                    uom=uom,
                    unit_rate=rate,
                    available_stock=stock,
                    gl_code=gl,
                    cost_center=cc
                )
                materials_to_insert.append(mat)
                new_count += 1

        if materials_to_insert:
            db.session.bulk_save_objects(materials_to_insert)

        # Audit log
        log = AuditLog(
            user_id=current_user.id,
            action='UPLOAD_INVENTORY',
            entity_type='InventorySnapshot',
            entity_id=snapshot.id,
            details=f'Uploaded inventory: {filename}, {new_count} new items, {updated_count} updated items',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

        return {
            'success': True,
            'valid_items': len(df),
            'duplicate_items': duplicate_count,
            'snapshot_id': snapshot.id,
            'message': f"Imported successfully! {new_count} new items added, {updated_count} existing items updated."
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
