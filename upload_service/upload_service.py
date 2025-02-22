from flask import Flask, request, render_template, redirect, flash
import os
import requests
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

app = Flask(__name__, template_folder="templates")

# Use an environment variable for the secret key, or default to a dev key
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key")

# Define the upload folder
UPLOAD_FOLDER = "/tmp"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Use Cloud Run AI Service URL instead of localhost
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "https://ai-service-293093374995.us-central1.run.app/analyze")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("❌ No file uploaded")
            return redirect(request.url)

        # Save the file locally in /tmp (Cloud Run allows this)
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        flash("✅ File uploaded successfully.")

        # Send file path to AI Service for analysis
        try:
            response = requests.post(AI_SERVICE_URL, json={"file_path": file_path})
            if response.status_code == 200:
                flash("✅ AI analysis triggered successfully.")
            else:
                flash("❌ AI analysis failed to trigger.")
        except Exception as e:
            flash(f"❌ Error triggering analysis: {str(e)}")

        # Redirect to AI Service results page on Cloud Run
        return redirect("https://ai-service-293093374995.us-central1.run.app/results")

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
