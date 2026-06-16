import unittest
import time
from app import create_app, db
from app.models import User
from itsdangerous import URLSafeTimedSerializer as Serializer

class PasswordResetTokenTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SECRET_KEY'] = 'test-secret-key'
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Create a test user
        self.user = User(
            username='testuser', 
            email='test@example.com', 
            full_name='Test User',
            employee_id='EMP001',
            role='employee'
        )
        self.user.set_password('old_password')
        db.session.add(self.user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_token_works_before_password_change(self):
        token = self.user.get_reset_password_token()
        
        # Verify token is valid
        verified_user = User.verify_reset_password_token(token)
        self.assertIsNotNone(verified_user)
        self.assertEqual(verified_user.id, self.user.id)

    def test_token_fails_after_password_change(self):
        # Generate token with old password
        token = self.user.get_reset_password_token()
        
        # Change password
        self.user.set_password('new_password')
        db.session.commit()
        
        # Verify old token is now INVALID
        verified_user = User.verify_reset_password_token(token)
        self.assertIsNone(verified_user, "Token should be invalid after password change")

    def test_token_expires_after_time_limit(self):
        token = self.user.get_reset_password_token()
        
        # itsdangerous drops sub-second precision, so wait 2 seconds
        # and test with max_age=1
        time.sleep(2) 
        verified_user = User.verify_reset_password_token(token, expires_in=1)
        self.assertIsNone(verified_user, "Token should expire")

if __name__ == '__main__':
    unittest.main()
