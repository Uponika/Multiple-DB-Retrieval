from typing import Dict, Any, List, Optional
import pyodbc
from config.settings import AZURE_SQL_CONN_STR

def _conn():
    return pyodbc.connect(AZURE_SQL_CONN_STR)

def get_candidate_metadata(candidate_id: int) -> Optional[Dict[str, Any]]:
    sql = "SELECT candidate_id, name, location, email, status FROM candidates WHERE candidate_id = ?"
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, (candidate_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [col[0] for col in cur.description]
        return dict(zip(cols, row))


def list_all_candidate_ids() -> List[str]:
    sql = "SELECT candidate_id FROM candidates ORDER BY candidate_id"
    with _conn() as conn:
        cur = conn.cursor()
        return [r[0] for r in cur.execute(sql).fetchall()]
