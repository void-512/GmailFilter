import sqlite3

def deduplicate_by_order_id(db_path="matches.db"):
    """
    Remove duplicate messages that share the same order_id (case-insensitive),
    keeping only the one with the longest text_length.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM matched_messages
        WHERE id NOT IN (
            SELECT id FROM (
                SELECT id
                FROM matched_messages AS mm
                WHERE mm.text_length IS NOT NULL
                GROUP BY LOWER(mm.order_id)
                HAVING mm.text_length = MAX(mm.text_length)
            )
        )
        AND order_id IS NOT NULL;
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    deduplicate_by_order_id()
