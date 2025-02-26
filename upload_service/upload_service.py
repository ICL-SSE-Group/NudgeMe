from flask import Flask, render_template, request, redirect, session, flash, jsonify, send_file
import os
import psycopg2
from dotenv import load_dotenv
import requests
import pandas as pd
import csv
from decimal import Decimal

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_key")

# Database connection
DB_CONN = os.getenv("DATABASE_URL", "postgresql://transaction_user:postgres@127.0.0.1:5432/expense_transactions")

# AI Service URL
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:5001/analyze") 

# ---------------- AUTHENTICATION ROUTES ------------------

@app.route("/login", methods=["GET"])
def login_page():
    """Displays the login page."""
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    """Handles user login and session management, creating a new user if needed."""
    username = request.form.get("username")

    with psycopg2.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            # Check if the username already exists
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            result = cur.fetchone()

            if result:
                # Existing user found, log them in
                user_id = result[0]
            else:
                # New user - insert into the database
                cur.execute("INSERT INTO users (username) VALUES (%s) RETURNING id", (username,))
                user_id = cur.fetchone()[0]
                conn.commit()  # Commit new user creation

    session["user_id"] = user_id  # Store unique user ID in session
    flash("✅ Login successful!")
    return redirect("/")


@app.route("/logout")
def logout():
    """Logs out the user and clears session."""
    session.clear()
    flash("✅ You have been logged out.")
    return redirect("/login")

# ------------------  FILE UPLOAD & DASHBOARD ------------------

@app.route("/", methods=["GET"])
def index():
    """Displays file upload page."""
    if "user_id" not in session:
        return redirect("/login")
    return render_template("index.html")


@app.route("/", methods=["POST"])
def upload_file():
    if "user_id" not in session:
        return redirect("/login")

    file = request.files.get("file")
    user_id = session["user_id"]

    if not file:
        flash("❌ No file uploaded")
        return redirect(request.url)

    # Ensure the uploaded file has a proper CSV extension
    if not file.filename.endswith(".csv"):
        flash("❌ Invalid file format. Please upload a CSV file.")
        return redirect(request.url)

    # Save the file temporarily
    upload_folder = "uploads"
    os.makedirs(upload_folder, exist_ok=True)  # Ensure upload folder exists
    file_path = os.path.join(upload_folder, file.filename)
    file.save(file_path)

    # Process CSV file
    with open(file_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        with psycopg2.connect(DB_CONN) as conn:
            with conn.cursor() as cur:
                for row in reader:
                    try:
                        amount = float(row["Amount"].replace("$", "").strip())  # Convert amount to float
                    except ValueError:
                        flash(f"❌ Invalid amount format: {row['Amount']}")
                        return redirect(request.url)

                    cur.execute(
                        """
                        INSERT INTO transactions (user_id, date, expense_name, amount, expense_type)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (user_id, row["Date"], row["Expense Name"], amount, row["Expense Type"]),
                    )

    # Store file in uploads table
    with psycopg2.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO uploads (user_id, file_name, storage_path) VALUES (%s, %s, %s)",
                (user_id, file.filename, file_path),
            )

    flash("✅ File uploaded and transactions stored in database.")
    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    """Displays the dashboard with uploaded files."""
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    with psycopg2.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT file_name, storage_path, uploaded_at FROM uploads WHERE user_id = %s ORDER BY uploaded_at DESC", (user_id,))
            files = cur.fetchall()

    return render_template("dashboard.html", files=files)

# ------------------  AI ANALYSIS ROUTES ------------------
@app.route("/get-analysis/<filename>", methods=["GET"])
def get_analysis(filename):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    #  Retrieve transactions from database
    with psycopg2.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT date, expense_name, amount, expense_type
                FROM transactions
                WHERE user_id = %s
                ORDER BY date ASC
                """,
                (user_id,),
            )
            transactions = cur.fetchall()

    if not transactions:
        return jsonify({"error": " No transactions found for this user"}), 404

    # Convert query results to JSON format
    transactions_json = [
        {
            "Date": row[0].isoformat(),
            "Expense Name": row[1],
            "Amount": float(row[2]),
            "Expense Type": row[3]
        }
        for row in transactions
    ]

    try:
        # Send JSON data to AI Service
        response = requests.post(
            AI_SERVICE_URL,
            json={"data": transactions_json},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()  # Raise an exception for bad status codes
        
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        print(f" AI Service request failed: {str(e)}")
        return jsonify({"error": " Failed to get AI analysis"}), 500


@app.route("/view-file/<filename>")
def view_file(filename):
    """Allows users to view their uploaded file from the database."""
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    # Retrieve the file path from the database
    with psycopg2.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT storage_path FROM uploads WHERE user_id = %s AND file_name = %s", 
                (user_id, filename)
            )
            result = cur.fetchone()

    if result:
        file_path = result[0]
        print(f" Serving file from: {file_path}")  # Debugging line

        # Ensure file exists before sending
        if os.path.exists(file_path):
            return send_file(file_path, mimetype="text/csv")
        else:
            print(f" File not found: {file_path}")
            return " File not found", 404
    else:
        print(f" No database record found for file: {filename}")
        return " File record not found", 404

@app.route('/delete-file/<filename>', methods=['DELETE'])
def delete_file(filename):
    try:
        # Get user ID from session or request
        user_id = request.headers.get('X-User-Id') or 'default_user'
        
        # Create user-specific upload folder path
        user_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
        file_path = os.path.join(user_upload_folder, filename)

        # Check if file exists and delete it
        if os.path.exists(file_path):
            os.remove(file_path)
            return '', 204  # Success with no content
        return 'File not found', 404
    except Exception as e:
        print(f"Error deleting file: {str(e)}")  # Log the error
        return str(e), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)