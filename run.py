import os
from app import create_app, db
from app.models import User, ApprovalRule

app = create_app(os.environ.get('FLASK_ENV', 'default'))


@app.shell_context_processor
def make_shell_context():
    from app import models
    return {'db': db, 'User': models.User, 'Request': models.Request}


@app.cli.command('seed-db')
def seed_db():
    """Seed the database with initial data."""
    import seed
    seed.seed()
    print('Database seeded successfully.')


@app.cli.command('create-admin')
def create_admin():
    """Create the default admin user."""
    from app.models import User
    if not User.query.filter_by(username='admin').first():
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
        print('Admin user created: admin / Admin@123')
    else:
        print('Admin user already exists.')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
