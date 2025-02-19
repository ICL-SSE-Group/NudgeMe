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
        conn.commit()
    print("✅ Table 'transactions' is ready.")

def insert_csv_data(file_path, user_id):
    try:
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.lower().str.strip()  # Normalize column names

        required_columns = {"date", "expense name", "amount", "expense type"}
        if not required_columns.issubset(df.columns):
            return "❌ Error: CSV must contain 'Date', 'Expense Name', 'Amount', 'Expense Type'."

        df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y").dt.date
        df["amount"] = df["amount"].replace(r'[\$,]', '', regex=True).astype(float)

        with engine.connect() as conn:
            for _, row in df.iterrows():
                conn.execute(
                    text("""
                        INSERT INTO transactions (date, expense_name, amount, expense_type, user_id)
                        VALUES (:date, :expense_name, :amount, :expense_type, :user_id)
                    """),
                    {
                        "date": row["date"],
                        "expense_name": row["expense name"],
                        "amount": row["amount"],
                        "expense_type": row["expense type"],
                        "user_id": user_id  # ✅ Ensure user_id is passed dynamically
                    }
                )
            conn.commit()
        return "✅ CSV data inserted successfully!"

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
