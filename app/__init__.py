from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()


def create_app(config_name=None):
    import os
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)

    # Login manager settings
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'
    login_manager.session_protection = 'strong'

    # Register blueprints
    from app.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    from app.admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    from app.store import store as store_blueprint
    app.register_blueprint(store_blueprint, url_prefix='/store')

    from app.employee import employee as employee_blueprint
    app.register_blueprint(employee_blueprint, url_prefix='/employee')

    from app.approver import approver as approver_blueprint
    app.register_blueprint(approver_blueprint, url_prefix='/approver')

    from app.reports import reports as reports_blueprint
    app.register_blueprint(reports_blueprint, url_prefix='/reports')

    from app.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # Register template filters
    from app.utils import format_currency, format_datetime, format_date
    app.jinja_env.filters['currency'] = format_currency
    app.jinja_env.filters['datetime'] = format_datetime
    app.jinja_env.filters['date'] = format_date

    # ── Startup: ensure tables exist ──────────────────────────────
    # This runs AFTER all models are imported via the blueprints above,
    # so SQLAlchemy knows every table. It is a no-op if tables already exist.
    with app.app_context():
        try:
            # Import ALL models so SQLAlchemy metadata is complete
            from app import models  # noqa: F401
            db.create_all()
            app.logger.info('db.create_all() completed — all tables verified.')

            # Auto-create admin user if no users exist yet (first deploy)
            from app.models import User
            if User.query.count() == 0:
                admin = User(
                    username='admin',
                    email='admin@engineering.com',
                    full_name='System Administrator',
                    role='admin',
                    is_active=True
                )
                admin.set_password('Admin@123')
                db.session.add(admin)
                db.session.commit()
                app.logger.info('Default admin user created: admin / Admin@123')
        except Exception as e:
            app.logger.error(f'Startup DB init error: {e}')

    return app
