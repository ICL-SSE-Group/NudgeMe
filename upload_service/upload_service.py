from flask import Flask, request, render_template, redirect, flash
import os
import requests
from dotenv import load_dotenv

load_dotenv()  # Loads variables from .env

app = Flask(__name__, template_folder="templates")
# Use an environment variable for the secret key, or generate one if not set
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key")

# Define the upload folder
UPLOAD_FOLDER = "/tmp"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("❌ No file uploaded")
            return redirect(request.url)
        
        # Save the file locally
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)
        flash("✅ File uploaded successfully.")

        # Trigger the AI service (we assume it runs on port 5001)
        ai_service_url = os.environ.get("AI_SERVICE_URL", "http://localhost:5001/analyze")
        try:
            response = requests.post(ai_service_url, json={"file_path": file_path})
            if response.status_code == 200:
                flash("✅ AI analysis triggered successfully.")
            else:
                flash("❌ AI analysis failed to trigger.")
        except Exception as e:
            flash(f"❌ Error triggering analysis: {str(e)}")
        
        # Redirect to the AI service's results page
        return redirect("http://localhost:5001/results")
    
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
