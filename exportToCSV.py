import sqlite3
import csv
from datetime import datetime

def export_db_to_csv(db_path="matches.db", csv_path="export.csv"):
    """
    Export all rows from matched_messages table into a CSV file,
    converting Gmail timestamps into human-readable format.
    Compatible with the new schema that includes the sender column.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM matched_messages")
    rows = cursor.fetchall()

    # Dynamically get column names (includes new 'sender' column)
    col_names = [desc[0] for desc in cursor.description]

    # Index of timestamp column (still named "timestamp")
    ts_index = col_names.index("timestamp")

    readable_rows = []
    for row in rows:
        row = list(row)
        raw_ts = row[ts_index]

        try:
            # Gmail internalDate is milliseconds
            dt = datetime.fromtimestamp(int(raw_ts) / 1000)
            row[ts_index] = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass  # keep original value

        readable_rows.append(row)

    # Write CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(col_names)   # header row including sender
        writer.writerows(readable_rows)

    conn.close()
    print(f"✔ Export completed: {csv_path}")


if __name__ == "__main__":
    export_db_to_csv()
