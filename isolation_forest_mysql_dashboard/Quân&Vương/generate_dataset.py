"""Generate deterministic synthetic DB access data for the Isolation Forest project."""
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 20261016
OUT = Path(__file__).resolve().parent / "dataset_v1.csv"


def generate_dataset(seed=SEED):
    rng = np.random.default_rng(seed)
    n_normal, n_attack = 500, 42
    start = pd.Timestamp("2026-09-01 00:00:00")
    rows = []
    users = ["staff01", "staff02", "student07", "admin01", "staff03"]
    tables = ["students", "courses", "grades", "attendance", "users"]
    normal_ops = ["SELECT", "SELECT", "SELECT", "INSERT", "UPDATE"]
    # Normal traffic spread across several weeks, including a small amount of after-hours activity.
    offsets = np.sort(rng.integers(0, 35 * 24 * 3600, size=n_normal))
    for i, sec in enumerate(offsets):
        ts = start + pd.Timedelta(seconds=int(sec))
        if rng.random() < 0.09:
            ts = ts.normalize() + pd.Timedelta(hours=int(rng.choice([0, 1, 2, 5, 21, 22, 23])),
                                                minutes=int(rng.integers(0, 60)))
        op = str(rng.choice(normal_ops))
        duration = float(np.clip(rng.lognormal(mean=3.1, sigma=1.0), 1, 2500))
        user = str(rng.choice(users))
        rows.append({
            "event_time": ts, "db_user": user,
            "user_role": "Admin" if user == "admin01" else ("Student" if user.startswith("student") else "Staff"),
            "client_host": str(rng.choice(["10.0.0.12", "10.0.0.18", "192.168.1.20", "localhost"])),
            "operation": op, "table_name": str(rng.choice(tables)),
            "rows_affected": int(rng.integers(0, 10) if op == "SELECT" else rng.integers(1, 16)),
            "duration_ms": round(duration, 3), "status": "SUCCESS",
            "details": "Synthetic normal workload", "is_attack": 0, "attack_type": "normal"
        })

    # Sparse attacks are placed in working hours. Low-and-slow events intentionally
    # overlap normal duration and row-count distributions; burst intensity comes from timestamps.
    attack_specs = (
        [("low_and_slow", "SELECT", "grades", "student07")] * 18
        + [("credential_misuse", "SELECT", "users", "unknown01")] * 8
        + [("destructive_write", "DELETE", "grades", "staff01")] * 8
        + [("privilege_change", "GRANT", "users", "unknown01")] * 8
    )
    base = pd.Timestamp("2026-09-15 09:00:00")
    for i, (kind, op, table, user) in enumerate(attack_specs):
        if kind == "low_and_slow":
            # Each event is slow-ish but often overlaps normal tail; 18 events in a few 5-min windows.
            ts = base + pd.Timedelta(minutes=int(i // 6) * 5 + int(i % 6) * 0.65)
            duration = float(np.clip(rng.lognormal(mean=3.8, sigma=0.65), 12, 900))
            affected = int(rng.integers(0, 5))
        else:
            ts = base + pd.Timedelta(days=int(i % 4), minutes=int(rng.integers(0, 480)))
            duration = float(np.clip(rng.lognormal(mean=4.1, sigma=0.9), 5, 3000))
            affected = int(rng.integers(0, 20) if op == "SELECT" else rng.integers(1, 120))
        rows.append({
            "event_time": ts, "db_user": user,
            "user_role": "Unknown" if user == "unknown01" else "Student",
            "client_host": str(rng.choice(["10.0.0.99", "192.168.1.99"])),
            "operation": op, "table_name": table, "rows_affected": affected,
            "duration_ms": round(duration, 3), "status": "SUCCESS",
            "details": f"Synthetic lab scenario: {kind}", "is_attack": 1, "attack_type": kind
        })

    df = pd.DataFrame(rows).sort_values(["event_time", "db_user"], kind="stable").reset_index(drop=True)
    df["event_time"] = pd.to_datetime(df["event_time"]).dt.strftime("%Y-%m-%d %H:%M:%S.%f")
    # Derive event frequency from timestamps, per account, inclusive 5-minute rolling window.
    times = pd.to_datetime(df["event_time"])
    counts = {}
    from collections import defaultdict, deque
    windows = defaultdict(deque)
    for idx in np.argsort(times.to_numpy()):
        user, ts = str(df.at[idx, "db_user"]), times.iloc[idx]
        q = windows[user]
        while q and (ts - q[0]).total_seconds() > 300:
            q.popleft()
        q.append(ts)
        counts[idx] = len(q)
    df["queries_last_5m"] = pd.Series(counts).reindex(df.index).astype(int)
    cols = ["event_time", "db_user", "user_role", "client_host", "operation", "table_name",
            "rows_affected", "duration_ms", "queries_last_5m", "status", "details",
            "is_attack", "attack_type"]
    return df[cols]


if __name__ == "__main__":
    data = generate_dataset()
    data.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"Created {OUT} ({len(data)} rows, seed={SEED})")
    print(data["attack_type"].value_counts().to_string())
