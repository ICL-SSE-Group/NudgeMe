import openai
import pandas as pd
import chardet
import os
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Fetch OpenAI API Key
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("❌ OpenAI API Key not found!")

# Initialize OpenAI API client
openai.api_key = openai_api_key

app = Flask(__name__, template_folder="templates")

# Storage for analysis results (temporary for demo purposes)
results_store = {}

def detect_encoding(file_path):
    """Detect file encoding to prevent read errors."""
    with open(file_path, "rb") as f:
        result = chardet.detect(f.read(100000))
    return result["encoding"] or "utf-8"

def analyze_file(file_path):
    """Reads the file, processes expenses, and sends analysis to OpenAI."""
    try:
        detected_encoding = detect_encoding(file_path)
        df = pd.read_csv(file_path, encoding=detected_encoding)
        df.columns = df.columns.str.lower().str.strip()

        # Ensure required columns exist
        required_columns = {"expense name", "expense type", "amount"}
        if not required_columns.issubset(df.columns):
            return "❌ Error: CSV file must include 'Expense Name', 'Expense Type', and 'Amount' columns."

        df["amount"] = df["amount"].replace(r'[\$,]', '', regex=True).astype(float)

        # Categorize expenses
        essential_keywords = ["food", "rent", "utilities", "groceries", "transport", "medical"]
        df["category"] = df["expense type"].apply(
            lambda x: "Essential" if any(keyword in x.lower() for keyword in essential_keywords) else "Non-Essential"
        )

        # Get spending summary
        total_non_essential = df[df["category"] == "Non-Essential"]["amount"].sum()
        essential_expenses = df[df["category"] == "Essential"][["expense name", "amount"]].to_string(index=False)
        non_essential_expenses = df[df["category"] == "Non-Essential"][["expense name", "amount"]].to_string(index=False)

        # Construct the prompt for OpenAI
        prompt = f"""
        The following is a list of expenses, their categories, and amounts:

        **Essential Expenses:**
        {essential_expenses}

        **Non-Essential Expenses:**
        {non_essential_expenses}

        The total amount spent on **Non-Essential** expenses is: **${total_non_essential:.2f}**.

        Provide the output in the following format:

        ```
        Essential:
        - [Expense Name] ($Amount)

        Non-Essential:
        - [Expense Name] ($Amount)

        Total Non-Essential Spending: **$[Total Amount]**
        ```

        Please include insights on how to reduce non-essential expenses.
        """

        # Call OpenAI API for analysis
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"Error processing file: {str(e)}"

@app.route("/analyze", methods=["POST"])
def analyze():
    """Handles AI analysis requests from the upload service."""
    data = request.get_json()
    file_path = data.get("file_path")
    if not file_path:
        return jsonify({"error": "file_path is required"}), 400

    analysis_result = analyze_file(file_path)
    results_store[file_path] = analysis_result
    return jsonify({"analysis": analysis_result}), 200

@app.route("/results")
def results():
    """Displays the latest analysis result."""
    if results_store:
        latest_file = list(results_store.keys())[-1]
        analysis = results_store[latest_file]
    else:
        analysis = "No analysis available yet."
    return render_template("results.html", analysis=analysis)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
