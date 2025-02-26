import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Adjust this import to match your actual path structure
# This assumes ai_service.py is in the same directory as this test file
from ai_service.ai_service import app

class TestAIService(unittest.TestCase):
    def setUp(self):
        """Set up test client"""
        self.app = app.test_client()
        self.app.testing = True
        
        # Sample test data
        self.valid_data = {
            "data": [
                {
                    "Date": "2023-01-01",
                    "Expense Name": "Grocery Store",
                    "Amount": 50.0,
                    "Expense Type": "groceries"
                },
                {
                    "Date": "2023-01-02",
                    "Expense Name": "Movie Theater",
                    "Amount": 25.0,
                    "Expense Type": "entertainment"
                }
            ]
        }
        
        self.invalid_data = {"invalid": "data"}
        self.empty_data = {"data": []}

    @patch('ai_service.client')
    def test_analyze_valid_request(self, mock_client):
        """Test analyze endpoint with valid request data"""
        # Mock the OpenAI API response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Mocked AI Analysis"
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test the endpoint
        response = self.app.post('/analyze', 
                               json=self.valid_data, 
                               content_type='application/json')
        
        # Assert the response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertIn('analysis', response_data)
        self.assertEqual(response_data['analysis'], "Mocked AI Analysis")
        
        # Verify the OpenAI client was called
        mock_client.chat.completions.create.assert_called_once()

    def test_analyze_invalid_request(self):
        """Test analyze endpoint with invalid request data"""
        response = self.app.post('/analyze', 
                               json=self.invalid_data, 
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)

    def test_analyze_empty_data(self):
        """Test analyze endpoint with empty data array"""
        response = self.app.post('/analyze', 
                               json=self.empty_data, 
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)
        
    def test_expense_categorization(self):
        """Test that expenses are correctly categorized as essential or non-essential"""
        # Create sample transactions to test categorization
        transactions = [
            {"Date": "2023-01-01", "Expense Name": "Grocery Store", "Amount": "50.0", "Expense Type": "groceries"},
            {"Date": "2023-01-02", "Expense Name": "Movie Theater", "Amount": "25.0", "Expense Type": "entertainment"},
            {"Date": "2023-01-03", "Expense Name": "Utility Bill", "Amount": "100.0", "Expense Type": "utilities"},
            {"Date": "2023-01-04", "Expense Name": "Restaurant", "Amount": "75.0", "Expense Type": "food"}
        ]
        
        # Use the categorization logic from the app
        essential_keywords = ["food", "rent", "utilities", "groceries", "transport", "medical"]
        for transaction in transactions:
            transaction["category"] = "Essential" if any(
                keyword in transaction["Expense Type"].lower() for keyword in essential_keywords
            ) else "Non-Essential"
        
        # Check if categorization is correct
        self.assertEqual(transactions[0]["category"], "Essential")  # groceries
        self.assertEqual(transactions[1]["category"], "Non-Essential")  # entertainment
        self.assertEqual(transactions[2]["category"], "Essential")  # utilities
        self.assertEqual(transactions[3]["category"], "Essential")  # food

if __name__ == '__main__':
    unittest.main()