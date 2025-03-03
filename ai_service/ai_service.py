from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import openai
import pandas as pd
import json

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))


# Fetch OpenAI API Key
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI API Key not found! Ensure it's set in .env or Google Secret Manager.")

# Initialize OpenAI Client
client = openai.OpenAI(api_key=openai_api_key)

app = Flask(__name__)

@app.route("/analyze", methods=["POST"])
def analyze():
    """Receives JSON transaction data from Upload Service and processes it."""
    data = request.get_json()
    
    if not data or "data" not in data:
        print("No data received in AI Service")
        return jsonify({"error": "No data received"}), 400
    
    try:
        transactions = data["data"]
        if not transactions:
            return jsonify({"error": "No transactions provided"}), 400

        print("AI Service received JSON data and converted it to structured format")
        
        # Categorize expenses
        essential_keywords = ["food", "rent", "utilities", "groceries", "transport", "medical"]
        for transaction in transactions:
            transaction["category"] = "Essential" if any(
                keyword in transaction["Expense Type"].lower() for keyword in essential_keywords
            ) else "Non-Essential"
        
        # Summarize spending
        total_non_essential = sum(float(tx["Amount"]) for tx in transactions if tx["category"] == "Non-Essential")
        
        essential_expenses = "\n".join(
            f"- {tx['Expense Name']} (${tx['Amount']})" for tx in transactions if tx["category"] == "Essential"
        )
        non_essential_expenses = "\n".join(
            f"- {tx['Expense Name']} (${tx['Amount']})" for tx in transactions if tx["category"] == "Non-Essential"
        )
        
        print("AI Service prepared expense summary")
        
        # OpenAI Prompt
        prompt = f"""
        Here is a list of transactions categorized as essential and non-essential:

        **Essential Expenses:**
        {essential_expenses}

        **Non-Essential Expenses:**
        {non_essential_expenses}

        The total amount spent on **Non-Essential** expenses is: **${total_non_essential:.2f}**.

        Provide financial insights, including:
        - Areas where spending can be reduced.
        - How to prioritize essential expenses.
        - Budgeting tips for the user.

        Return the response in this format:

        ```
        Essential:
        - [Expense Name] ($Amount)

        Non-Essential:
        - [Expense Name] ($Amount)

        Total Non-Essential Spending: **$[Total Amount]**
        ```

        Also, include a brief personalized suggestion for the user.
        """
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        
        print("AI Service successfully generated response")
        
        return jsonify({"analysis": response.choices[0].message.content})
    
    except Exception as e:
        print(f"Error in AI Service: {str(e)}")
        return jsonify({"error": f"Error processing data: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)