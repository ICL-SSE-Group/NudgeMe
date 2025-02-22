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
    """Handles user login and session management."""
    username = request.form.get("username")
    password = request.form.get("password")

    with psycopg2.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, password FROM users WHERE username = %s", (username,))
            result = cur.fetchone()

    if result:
        session["user_id"] = result[0]  # Store user session
        flash("✅ Login successful!")
        return redirect("/")
    else:
        flash(" Invalid username or password.")
        return redirect("/login")

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
        flash(" No file uploaded")
        return redirect(request.url)

    with psycopg2.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            reader = csv.DictReader(file.read().decode("utf-8").splitlines())

            for row in reader:
                try:
                    amount = float(row["Amount"].replace("$", "").strip())  # Convert amount to float
                except ValueError:
                    flash(f" Invalid amount format: {row['Amount']}")
                    return redirect(request.url)

                cur.execute(
                    """
                    INSERT INTO transactions (user_id, date, expense_name, amount, expense_type)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, row["Date"], row["Expense Name"], amount, row["Expense Type"]),
                )

    flash(" File uploaded and transactions stored in database.")
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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
