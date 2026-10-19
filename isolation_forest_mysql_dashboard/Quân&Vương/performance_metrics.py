"""Read measured statement metrics from MariaDB/MySQL performance_schema.

Requires performance_schema=ON and suitable SELECT privileges. This does not
invent timings; it reports server-recorded timer and row-count values.
"""
import argparse
import json
from datetime import datetime
import mysql.connector
from config import DB_CONFIG


def read_statement_metrics(limit=1000):
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SHOW VARIABLES LIKE 'performance_schema'")
        setting = cur.fetchone()
        if not setting or str(setting.get("Value", "")).upper() != "ON":
            raise RuntimeError(
                "performance_schema đang OFF. Dùng slow query log theo README hoặc bật "
                "performance_schema trong cấu hình MariaDB rồi khởi động lại."
            )
        cur.execute("""
            SELECT EVENT_ID, THREAD_ID, EVENT_NAME, SQL_TEXT,
                   ROWS_AFFECTED, ROWS_SENT, ROWS_EXAMINED,
                   TIMER_WAIT, MYSQL_ERRNO, CREATED_TMP_TABLES,
                   CREATED_TMP_DISK_TABLES
            FROM performance_schema.events_statements_history_long
            WHERE SQL_TEXT IS NOT NULL
            ORDER BY THREAD_ID, EVENT_ID
            LIMIT %s
        """, (int(limit),))
        rows = cur.fetchall()
        # TIMER_WAIT is in picoseconds: divide by 1e9 to get milliseconds.
        for row in rows:
            timer = row.get("TIMER_WAIT")
            row["duration_ms"] = round(float(timer) / 1_000_000_000, 3) if timer is not None else None
            row["captured_at_utc"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            row.pop("TIMER_WAIT", None)
        return rows
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--out", default="performance_metrics.jsonl")
    args = parser.parse_args()
    rows = read_statement_metrics(args.limit)
    with open(args.out, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")
    print(f"Đã ghi {len(rows)} bản ghi đo thực tế vào {args.out}")
