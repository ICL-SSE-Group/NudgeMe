import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://transaction_user:postgres@127.0.0.1:5432/expense_transactions"
engine = create_engine(DATABASE_URL)

def create_table():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                expense_name TEXT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                expense_type TEXT NOT NULL,
                user_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
    print("✅ Table 'transactions' is ready.")

def insert_csv_data(file_path, user_id):
    try:
        # ✅ Load CSV file and normalize column names
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.lower().str.strip()

        # ✅ Ensure the required columns are present
        required_columns = {"date", "expense name", "amount", "expense type"}
        if not required_columns.issubset(df.columns):
            return "❌ Error: CSV must contain 'Date', 'Expense Name', 'Amount', 'Expense Type'."

        # ✅ Format the data
        df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y").dt.date
        df["amount"] = df["amount"].replace(r'[\$,]', '', regex=True).astype(float)

        # ✅ Insert transactions into the database (avoid duplicates)
        with engine.begin() as conn:
            inserted_count = 0

            for _, row in df.iterrows():
                date = row["date"]
                expense_name = row["expense name"]
                amount = row["amount"]
                expense_type = row["expense type"]

                # ✅ Check if transaction already exists
                existing_transaction = conn.execute(
                    text("""
                        SELECT id FROM transactions
                        WHERE date = :date AND expense_name = :expense_name
                        AND amount = :amount AND user_id = :user_id
                    """),
                    {
                        "date": date,
                        "expense_name": expense_name,
                        "amount": amount,
                        "user_id": user_id
                    }
                ).fetchone()

                # ✅ Insert only if transaction does not exist
                if not existing_transaction:
                    conn.execute(
                        text("""
                            INSERT INTO transactions (date, expense_name, amount, expense_type, user_id, created_at)
                            VALUES (:date, :expense_name, :amount, :expense_type, :user_id, NOW())
                        """),
                        {
                            "date": date,
                            "expense_name": expense_name,
                            "amount": amount,
                            "expense_type": expense_type,
                            "user_id": user_id
                        }
                    )
                    inserted_count += 1
                    
        return f"✅ {inserted_count} new transactions added." if inserted_count else "No new transactions were inserted."

    except Exception as e:
        return f"❌ Error inserting data: {str(e)}"

# ✅ Function to retrieve transactions
def fetch_transactions():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM transactions ORDER BY date DESC"))
        return result.fetchall()

# ✅ Run database checks
if __name__ == "__main__":
    create_table()  # Ensure table exists before using it
    print("✅ Database is ready!")
