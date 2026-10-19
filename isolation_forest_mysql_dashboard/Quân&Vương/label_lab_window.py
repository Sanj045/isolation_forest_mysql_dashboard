"""Record lab windows and manually apply ground-truth labels to matching DB events.

Labels are based on the operator-recorded time window + account + client host,
never on Isolation Forest predictions. Use only on your authorized lab database.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
import mysql.connector
from config import DB_CONFIG

MANIFEST = Path(__file__).resolve().parent / "lab_ground_truth_manifest.jsonl"


def record_and_label(start, end, account, client_host, is_attack, attack_type, notes=""):
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    if end_dt < start_dt:
        raise ValueError("end phải sau start")
    if int(is_attack) not in (0, 1):
        raise ValueError("is_attack chỉ nhận 0 hoặc 1")
    record = {
        "start": start_dt.isoformat(sep=" "),
        "end": end_dt.isoformat(sep=" "),
        "account": account,
        "client_host": client_host,
        "is_attack": int(is_attack),
        "attack_type": attack_type if int(is_attack) else "normal",
        "notes": notes,
        "label_source": "operator_recorded_lab_window_account_host",
        "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
    }
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE activity_logs
            SET ground_truth_anomaly = %s,
                details = CONCAT(LEFT(details, 350), %s)
            WHERE event_time BETWEEN %s AND %s
              AND db_user = %s
              AND client_host = %s
              AND (details NOT LIKE 'DEMO_DATASET_V1%')
        """, (
            int(is_attack), f"; MANUALLY_LABELED={record['attack_type']}",
            start_dt, end_dt, account, client_host
        ))
        record["matched_rows"] = cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    with MANIFEST.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="ISO local time, e.g. 2026-10-16T10:00:00")
    parser.add_argument("--end", required=True)
    parser.add_argument("--account", required=True, help="Exact DB account name in activity_logs")
    parser.add_argument("--client-host", required=True, help="Exact client_host in activity_logs")
    parser.add_argument("--is-attack", required=True, type=int, choices=[0, 1])
    parser.add_argument("--attack-type", default="normal")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    result = record_and_label(
        args.start, args.end, args.account, args.client_host,
        args.is_attack, args.attack_type, args.notes
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
