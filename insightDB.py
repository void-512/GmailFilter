#!/usr/bin/env python3
"""
view_matches.py
----------------
Reads the SQLite database (matches.db) and displays all matched Gmail messages
with colorful, formatted output using the 'rich' library.
"""

import sqlite3
from rich.console import Console
from rich.table import Table
from rich import box
from datetime import datetime
from config import DB_PATH

def read_matches(db_path=DB_PATH):
    """Fetch all records from the matched_messages table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, subject, order_id, timestamp, has_attachment FROM matched_messages ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def format_timestamp(ts_str):
    """Convert Gmail internalDate (ms since epoch) to readable format."""
    try:
        ts_int = int(ts_str)
        dt = datetime.fromtimestamp(ts_int / 1000)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "N/A"

def display_matches(matches):
    """Pretty-print the messages in a colorful table."""
    console = Console()
    table = Table(title="📬 Matched Gmail Messages", box=box.SIMPLE_HEAVY)

    table.add_column("Msg ID", style="cyan", no_wrap=True)
    table.add_column("Subject", style="bold yellow")
    table.add_column("Order ID", style="green")
    table.add_column("Timestamp", style="magenta")
    table.add_column("Attachment", style="bright_blue", justify="center")

    if not matches:
        console.print("[red]No matched messages found in the database.[/red]")
        return

    for msg_id, subject, order_id, timestamp, has_attachment in matches:
        attach_icon = "📎" if has_attachment else "—"
        table.add_row(
            msg_id[:10] + "…",  # shorten ID
            subject or "[dim]No Subject[/dim]",
            order_id or "[dim]N/A[/dim]",
            format_timestamp(timestamp),
            attach_icon
        )

    console.print(table)
    console.print(f"\n[bold green]Total messages:[/bold green] {len(matches)}\n")

if __name__ == "__main__":
    matches = read_matches()
    display_matches(matches)
