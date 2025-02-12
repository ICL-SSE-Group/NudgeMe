from flask import Flask, request, render_template
from dotenv import load_dotenv
import pandas as pd
import openai
import os
import chardet
from google.cloud import secretmanager
import json

# ✅ Load environment variables
load_dotenv()


# ✅ Function to set up Google Cloud authentication from GitHub Secrets
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

# ✅ Function to retrieve secrets from Google Cloud Secret Manager
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

# ✅ Fetch OpenAI API Key securely
openai_api_key = get_secret("OPENAI_API_KEY")

if not openai_api_key:
    raise ValueError("❌ OPENAI API Key not found in Secret Manager!")

# ✅ Initialize OpenAI client
client = openai.Client(api_key=openai_api_key)

# ✅ Initialize Flask app
app = Flask(__name__, template_folder="templates")

# ✅ Define and create upload folder
UPLOAD_FOLDER = "/tmp"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ✅ Function to detect file encoding
def detect_encoding(file_path):
    with open(file_path, "rb") as f:
        result = chardet.detect(f.read(100000))
    return result["encoding"] or "utf-8"

# ✅ Function to analyze expenses
def analyze_expenses(file_path):
    try:
        detected_encoding = detect_encoding(file_path)
        df = pd.read_csv(file_path, encoding=detected_encoding)

        df.columns = df.columns.str.lower().str.strip()

        required_columns = {"expense name", "expense type", "amount"}
        if not required_columns.issubset(df.columns):
            return "❌ Error: The CSV file must include 'Expense Name', 'Expense Type', and 'Amount' columns."

        df["amount"] = df["amount"].replace(r'[\$,]', '', regex=True).astype(float)

        essential_keywords = ["food", "rent", "utilities", "groceries", "transport", "medical"]
        df["category"] = df["expense type"].apply(
            lambda x: "Essential" if any(keyword in x.lower() for keyword in essential_keywords) else "Non-Essential"
        )

        total_non_essential = df[df["category"] == "Non-Essential"]["amount"].sum()

        essential_expenses = df[df["category"] == "Essential"][["expense name", "amount"]].to_string(index=False)
        non_essential_expenses = df[df["category"] == "Non-Essential"][["expense name", "amount"]].to_string(index=False)

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

        Please include insights on how to reduce the non-essential expenses.
        """

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"Error processing file: {str(e)}"

# ✅ Flask routes
@app.route("/", methods=["GET", "POST"])
def index():
    analysis = "Upload your CSV file to analyse your expenses."

    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            return "No file uploaded"
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        analysis = analyze_expenses(file_path)
    
    return render_template("index.html", analysis=analysis)

# ✅ Run Flask app
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))  # Default to 8080 for Cloud Run
    app.run(debug=True, host="0.0.0.0", port=port)
