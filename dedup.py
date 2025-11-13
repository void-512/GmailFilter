import sqlite3

def deduplicate_by_order_id(db_path="matches.db"):
    """
    Remove duplicate messages that share the same order_id,
    keeping only the one with the longest text_length.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Delete all messages whose text_length is not the maximum within their order_id group
    cursor.execute("""
        DELETE FROM matched_messages
        WHERE id NOT IN (
            SELECT id FROM (
                SELECT id, order_id
                FROM matched_messages
                WHERE text_length IS NOT NULL
                GROUP BY order_id
                HAVING text_length = MAX(text_length)
            )
        )
        AND order_id IS NOT NULL;
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    deduplicate_by_order_id()