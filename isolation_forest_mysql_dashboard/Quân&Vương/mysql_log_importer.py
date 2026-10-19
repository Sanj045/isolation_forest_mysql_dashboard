"""Import selected MySQL general-log events into security_demo.activity_logs.

This module intentionally does not enable MySQL general_log automatically.
Enable it manually for a short, controlled lab session, then turn it off.
"""
import hashlib
import re
from datetime import datetime

import mysql.connector


# Only these SQL operations are useful for this dashboard. Avoid importing every
# SET/SHOW/transaction housekeeping statement into the anomaly model.
SUPPORTED_OPERATIONS = {
    "SELECT", "INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER",
    "DROP", "TRUNCATE", "GRANT", "REVOKE", "CALL", "EXECUTE", "WITH",
}


def _extract_user(user_host):
    """Convert MySQL general_log user_host text to a short account name."""
    value = str(user_host or "unknown")
    match = re.match(r"\s*([^\[]+)\[([^\]]*)\]", value)
    if match:
        return (match.group(2) or match.group(1)).strip()[:100]
    return value.split("@", 1)[0].strip()[:100] or "unknown"


def _extract_host(user_host):
    """Extract the client host/IP from general_log user_host, when available."""
    value = str(user_host or "")
    match = re.search(r"\[([^\]]+)\]\s*$", value)
    if match:
        return match.group(1).strip()[:100]
    if "@" in value:
        return value.rsplit("@", 1)[-1].strip()[:100]
    return "unknown"


def _operation_and_table(sql):
    sql = str(sql or "").strip()
    # Skip comments/empty statements and parameter markers with no SQL text.
    cleaned = re.sub(r"(?s)^\s*(?:--[^\n]*\n|/\*.*?\*/\s*)+", "", sql).strip()
    match = re.match(r"(?is)^([a-z]+)\b", cleaned)
    if not match:
        return None, "unknown"

    operation = match.group(1).upper()
    if operation not in SUPPORTED_OPERATIONS:
        return None, "unknown"
    if operation == "WITH":
        inner = re.search(r"(?is)\b(SELECT|INSERT|UPDATE|DELETE|REPLACE)\b", cleaned)
        operation = inner.group(1).upper() if inner else "SELECT"

    table = "unknown"
    patterns = [
        r"(?is)\bFROM\s+([`\w.]+)",
        r"(?is)\bJOIN\s+([`\w.]+)",
        r"(?is)\bINTO\s+([`\w.]+)",
        r"(?is)\bUPDATE\s+([`\w.]+)",
        r"(?is)\bTABLE\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?([`\w.]+)",
    ]
    for pattern in patterns:
        found = re.search(pattern, cleaned)
        if found:
            table = found.group(1).replace("`", "").split(".")[-1][:100]
            break
    return operation, table or "unknown"


def import_general_log(connector):
    """Import up to 10,000 new query events from mysql.general_log.

    Returns the number of newly imported events. The caller supplies a
    connection factory (normally get_connection from app.py).
    """
    conn = connector()
    imported = 0
    try:
        cur = conn.cursor(dictionary=True)
        # Keep deduplication keys in the application's database.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS imported_general_log_keys (
                event_key CHAR(64) PRIMARY KEY,
                imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
        """)
        conn.commit()

        try:
            cur.execute("""
                SELECT event_time, user_host, thread_id, command_type, argument
                FROM mysql.general_log
                WHERE command_type IN ('Query', 'Execute')
                  AND argument IS NOT NULL
                ORDER BY event_time DESC
                LIMIT 10000
            """)
            source_rows = cur.fetchall()
        except mysql.connector.Error as exc:
            raise RuntimeError(
                "Không đọc được mysql.general_log. Hãy bật general_log tạm thời "
                "và dùng tài khoản có quyền SELECT trên mysql.general_log. "
                f"Chi tiết MySQL: {exc}"
            ) from exc

        # Process oldest first so imported rows appear chronologically.
        for row in reversed(source_rows):
            sql = str(row.get("argument") or "").strip()
            sql_lower = sql.lower()
            # Ignore the importer's own reads and dashboard housekeeping queries.
            if any(token in sql_lower for token in (
                "mysql.general_log", "activity_logs", "imported_general_log_keys"
            )):
                continue
            operation, table_name = _operation_and_table(sql)
            if not operation:
                continue

            event_time = row.get("event_time") or datetime.now()
            user = _extract_user(row.get("user_host"))
            client_host = _extract_host(row.get("user_host"))
            thread_id = row.get("thread_id") or 0
            command_type = row.get("command_type") or "Query"
            key_material = f"{event_time}|{thread_id}|{command_type}|{sql}".encode("utf-8", errors="replace")
            event_key = hashlib.sha256(key_material).hexdigest()

            cur.execute("INSERT IGNORE INTO imported_general_log_keys (event_key) VALUES (%s)", (event_key,))
            if cur.rowcount == 0:
                continue

            role = "Admin" if user.lower() in {"root", "admin", "admin01"} else "MySQLUser"
            # Do not persist raw SQL text: it may contain secrets or personal data.
            details = f"Imported from mysql.general_log; command={command_type}; thread={thread_id}"
            cur.execute("""
                INSERT INTO activity_logs
                (event_time, db_user, user_role, client_host, operation, table_name,
                 rows_affected, duration_ms, queries_last_5m, status, details,
                 ground_truth_anomaly)
                VALUES (%s, %s, %s, %s, %s, %s, 0, 0, 1, 'LOGGED', %s, NULL)
            """, (
                event_time, user, role, client_host, operation,
                table_name, details,
            ))
            imported += 1

        conn.commit()
        return imported
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
