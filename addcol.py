import sqlite3

def add_return_flag_column(db_path="matches.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            ALTER TABLE matched_messages
            ADD COLUMN return_flag INTEGER DEFAULT 0;
        """)
        print("✅ Column 'return_flag' added.")

    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️ Column 'return_flag' already exists — skipping.")
        else:
            raise

    conn.commit()
    conn.close()


if __name__ == "__main__":
    add_return_flag_column()
