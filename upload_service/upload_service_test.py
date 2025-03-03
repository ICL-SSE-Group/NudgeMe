import unittest
from unittest.mock import patch, MagicMock
import json
import io
import sys
import os
from flask import session

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Adjust this import to match your actual path structure
# This assumes upload_service.py is in the same directory as this test file
from upload_service import app

class TestUploadService(unittest.TestCase):
    def setUp(self):
        """Set up test client"""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.app = app.test_client()
        
        # Sample CSV content for testing
        self.valid_csv_content = "Date,Expense Name,Amount,Expense Type\n2023-01-01,Grocery Store,50.0,groceries\n2023-01-02,Movie Theater,25.0,entertainment"

    def test_login_page(self):
        """Test that login page loads correctly"""
        response = self.app.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome to NudgeMe', response.data)

    @patch('upload_service.psycopg2.connect')
    def test_login_existing_user(self, mock_connect):
        """Test login with an existing user"""
        # Mock the database connection and cursor
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        # Mock the database response for existing user
        mock_cur.fetchone.return_value = (1,)  # User ID
        
        with self.app as client:
            response = client.post('/login', data={'username': 'testuser'}, follow_redirects=True)
            
            # Check the response
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Upload Your Expense File', response.data)
            
            # Verify database calls
            mock_cur.execute.assert_called_once()

    @patch('upload_service.psycopg2.connect')
    def test_login_new_user(self, mock_connect):
        """Test login with a new user (creates account)"""
        # Mock the database connection and cursor
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        # Mock the database response for non-existent user, then new user creation
        mock_cur.fetchone.side_effect = [None, (2,)]  # No existing user, then new user ID
        
        with self.app as client:
            response = client.post('/login', data={'username': 'newuser'}, follow_redirects=True)
            
            # Check the response
            self.assertEqual(response.status_code, 200)
            
            # Verify database calls
            self.assertEqual(mock_cur.execute.call_count, 2)  # Check for user + insert new user
            mock_conn.commit.assert_called_once()  # Commit for new user creation

    @patch('upload_service.psycopg2.connect')
    @patch('upload_service.os.makedirs')
    @patch('upload_service.open', new_callable=unittest.mock.mock_open, read_data="Date,Expense Name,Amount,Expense Type\n2023-01-01,Grocery Store,50.0,groceries")
    def test_upload_file(self, mock_open, mock_makedirs, mock_connect):
        """Test file upload functionality"""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        # Create a test client with a session
        with self.app as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1
            
            # Create test file data
            data = {'file': (io.BytesIO(self.valid_csv_content.encode('utf-8')), 'test.csv')}
            
            # Post to the upload endpoint
            response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=True)
            
            # Check response
            self.assertEqual(response.status_code, 200)
            
            # Verify os.makedirs was called and that save operations were performed
            mock_makedirs.assert_called_once()
            mock_open.assert_called()
            
            # Verify database operations (at least one execute call)
            self.assertTrue(mock_cur.execute.called)

    @patch('upload_service.requests.post')
    @patch('upload_service.psycopg2.connect')
    def test_get_analysis(self, mock_connect, mock_post):
        """Test getting AI analysis for a file"""
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        
        # Create a mock date object
        mock_date = MagicMock()
        mock_date.isoformat.return_value = "2023-01-01"
        
        # Mock database query results
        mock_cur.fetchall.return_value = [
            (mock_date, "Grocery Store", 50.0, "groceries"),
            (mock_date, "Movie Theater", 25.0, "entertainment")
        ]
        
        # Mock the AI service response
        mock_response = MagicMock()
        mock_response.json.return_value = {"analysis": "AI analysis results"}
        mock_post.return_value = mock_response
        
        # Create a test client with a session
        with self.app as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1
            
            # Test the endpoint
            response = client.get('/get-analysis/test.csv')
            
            # Check response
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('analysis', data)
            self.assertEqual(data['analysis'], "AI analysis results")
            
            # Verify AI service was called
            mock_post.assert_called_once()

    def test_logout(self):
        """Test logout functionality"""
        with self.app as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1
            
            response = client.get('/logout', follow_redirects=True)
            
            # Check that we're redirected to login page
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Welcome to NudgeMe', response.data)

if __name__ == '__main__':
    unittest.main()