import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd

DB_PATH = "qarar_enterprise.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_db() -> None:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS companies (
            company_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            plan_status TEXT DEFAULT 'Enterprise',
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS company_data (
            company_id INTEGER PRIMARY KEY,
            resources_json TEXT NOT NULL,
            orders_json TEXT NOT NULL,
            stock_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies (company_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS optimization_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            run_name TEXT NOT NULL,
            objective_mode TEXT NOT NULL,
            status TEXT NOT NULL,
            makespan INTEGER NOT NULL,
            total_cost INTEGER NOT NULL,
            utilization REAL NOT NULL,
            estimated_savings INTEGER NOT NULL,
            schedule_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (company_id) REFERENCES companies (company_id)
        )
        """
    )
    conn.commit()
    conn.close()


def register_company(company_name: str, email: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
    init_db()
    conn = _get_conn()
    cur = conn.cursor()
    try:
        now = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO companies (company_name, email, password_hash, plan_status, created_at) VALUES (?, ?, ?, 'Enterprise', ?)",
            (company_name.strip(), email.strip().lower(), _hash_password(password), now),
        )
        conn.commit()
        cid = cur.lastrowid
        company = {"company_id": cid, "company_name": company_name.strip(), "email": email.strip().lower(), "plan_status": "Enterprise"}
        return True, "تم تسجيل الشركة بنجاح!", company
    except sqlite3.IntegrityError:
        return False, "البريد الإلكتروني مسجل مسبقاً.", None
    finally:
        conn.close()


def login_company(email: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
    init_db()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT company_id, company_name, email, plan_status FROM companies WHERE email = ? AND password_hash = ?",
        (email.strip().lower(), _hash_password(password)),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return True, "تم تسجيل الدخول بنجاح!", dict(row)
    return False, "بيانات الدخول غير صحيحة.", None


def get_or_create_demo_company() -> Dict:
    init_db()
    ok, _, comp = login_company("demo@qarar.ai", "demo123")
    if ok and comp:
        return comp
    _, _, comp = register_company("شركة قرار النموذجية (Demo)", "demo@qarar.ai", "demo123")
    return comp


def save_company_data(company_id: int, resources_df: pd.DataFrame, orders_df: pd.DataFrame, stock_df: pd.DataFrame) -> None:
    init_db()
    conn = _get_conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    res_j = resources_df.to_json(orient="records", force_ascii=False)
    ord_j = orders_df.to_json(orient="records", force_ascii=False)
    stk_j = stock_df.to_json(orient="records", force_ascii=False)
    cur.execute(
        """
        INSERT INTO company_data (company_id, resources_json, orders_json, stock_json, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(company_id) DO UPDATE SET
            resources_json = excluded.resources_json,
            orders_json = excluded.orders_json,
            stock_json = excluded.stock_json,
            updated_at = excluded.updated_at
        """,
        (company_id, res_j, ord_j, stk_j, now),
    )
    conn.commit()
    conn.close()


def load_company_data(company_id: int) -> Optional[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    init_db()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT resources_json, orders_json, stock_json FROM company_data WHERE company_id = ?", (company_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return (
        pd.DataFrame(json.loads(row["resources_json"])),
        pd.DataFrame(json.loads(row["orders_json"])),
        pd.DataFrame(json.loads(row["stock_json"])),
    )


def save_optimization_run(company_id: int, run_name: str, objective_mode: str, result: Dict) -> int:
    init_db()
    conn = _get_conn()
    cur = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    sched_j = result["schedule_df"].to_json(orient="records", force_ascii=False)
    cur.execute(
        """
        INSERT INTO optimization_runs (
            company_id, run_name, objective_mode, status, makespan, total_cost,
            utilization, estimated_savings, schedule_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            run_name,
            objective_mode,
            result["status"],
            int(result["makespan"]),
            int(result["total_cost"]),
            float(result["utilization"]),
            int(result.get("estimated_savings", 0)),
            sched_j,
            now,
        ),
    )
    conn.commit()
    run_id = cur.lastrowid
    conn.close()
    return run_id


def get_optimization_history(company_id: int) -> pd.DataFrame:
    init_db()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT run_id, run_name, objective_mode, status, makespan, total_cost, utilization, estimated_savings, created_at
        FROM optimization_runs
        WHERE company_id = ?
        ORDER BY run_id DESC
        """,
        (company_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return pd.DataFrame(rows)


def load_optimization_run(run_id: int) -> Optional[Dict]:
    init_db()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM optimization_runs WHERE run_id = ?", (run_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["schedule_df"] = pd.DataFrame(json.loads(d["schedule_json"]))
    return d
