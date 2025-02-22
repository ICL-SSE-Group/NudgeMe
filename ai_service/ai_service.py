from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
import os
import openai
import pandas as pd
from google.cloud import secretmanager
import json
import chardet 

app = Flask(__name__, template_folder="templates")

load_dotenv()

# Function to set up Google Cloud authentication from GitHub Secrets
def setup_google_auth():
    """Sets up Google authentication using GitHub Secrets."""
    if os.getenv("GCP_SA_KEY"):
        key_data = json.loads(os.getenv("GCP_SA_KEY"))
        credential_path = "/tmp/gcp-key.json"
        
        # ✅ Write the service account key JSON to a temporary file
        with open(credential_path, "w") as f:
            json.dump(key_data, f)
        
        # ✅ Set the environment variable for Google authentication
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credential_path

# Function to retrieve secrets from Google Cloud Secret Manager
def get_secret(secret_name):
    """Fetches a secret from Google Cloud Secret Manager or .env (fallback)."""
    if os.getenv("LOCAL_ENV") == "True":
        return os.getenv(secret_name)

    setup_google_auth()  # Ensure Google authentication is set up

    client = secretmanager.SecretManagerServiceClient()
    project_id = "nudgeme-450123"
    secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"

    try:
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"❌ Error retrieving secret '{secret_name}': {e}")
        return None

# Fetch OpenAI API Key securely
openai_api_key = get_secret("OPENAI_API_KEY")

if not openai_api_key:
    raise ValueError("❌ OPENAI API Key not found in Secret Manager!")

# Initialize OpenAI client
client = openai.Client(api_key=openai_api_key)

# For simplicity, we use an in-memory store to keep analysis results
results_store = {} 

def detect_encoding(file_path):
    """Detect the encoding of a CSV file to prevent read errors."""
    with open(file_path, "rb") as f:
        result = chardet.detect(f.read(100000))
    return result["encoding"] or "utf-8"

def analyse_file(file_path):
    """Reads the CSV file, categorizes transactions, and generates AI insights."""
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

        # Summarize spending
        total_non_essential = df[df["category"] == "Non-Essential"]["amount"].sum()
        essential_expenses = df[df["category"] == "Essential"][["expense name", "amount"]].to_string(index=False)
        non_essential_expenses = df[df["category"] == "Non-Essential"][["expense name", "amount"]].to_string(index=False)

        # OpenAI Prompt
        prompt = f"""
        Here is a list of transactions with categories:

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

        # Call OpenAI for analysis
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content  # Return AI insights

    except Exception as e:
        return f"❌ Error processing file: {str(e)}"


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    file_path = data.get("file_path")
    if not file_path:
        return jsonify({"error": "file_path is required"}), 400

    # Run the analysis (this is a dummy function)
    analysis_result = analyse_file(file_path)
    # Store the result using the file path as a key
    results_store[file_path] = analysis_result
    return jsonify({"analysis": analysis_result}), 200

@app.route("/results")
def results():
    # For simplicity, display the most recent analysis result
    if results_store:
        latest_file = list(results_store.keys())[-1]
        analysis = results_store[latest_file]
    else:
        analysis = "No analysis available yet."
    return render_template("results.html", analysis=analysis)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
