"""Review queue answers (REC-02 corrections): the owner confirms, rejects,
or names the place behind a visit.

Provenance rule: an answer is stored as its own `visit_resolutions` row
with created_by='user'; the reconciler's scored row is never modified, and
re-running `reconcile` leaves user rows and answered questions alone. A
later answer to the same visit replaces only the user's own earlier one.
"""

import json

from .ask import visit_card

ANSWERS = ("confirm", "reject", "name", "skip")


def open_questions(conn, limit=20):
    rows = conn.execute(
        """SELECT q.id, q.visit_id, q.question FROM review_questions q
           JOIN visits v ON v.id = q.visit_id
           WHERE q.status = 'open' ORDER BY v.started_at DESC LIMIT ?""", (limit,)).fetchall()
    return [{"question_id": r["id"], "question": r["question"], "visit": visit_card(conn, r["visit_id"])} for r in rows]


def answer_question(conn, question_id: int, answer: str, name: str | None = None) -> dict:
    if answer not in ANSWERS:
        raise ValueError(f"answer must be one of {', '.join(ANSWERS)}")
    q = conn.execute("SELECT id, visit_id FROM review_questions WHERE id = ?", (question_id,)).fetchone()
    if q is None:
        raise ValueError("no such question")
    algo = conn.execute(
        "SELECT top_place_id FROM visit_resolutions WHERE visit_id = ? AND created_by != 'user' "
        "ORDER BY id DESC LIMIT 1", (q["visit_id"],)).fetchone()
    top = algo["top_place_id"] if algo else None
    record = {"question_id": question_id, "answer": answer}

    if answer in ("confirm", "reject"):
        if top is None:
            raise ValueError("this question has no candidate place to confirm or reject; answer 'name' instead")
        status = "confirmed" if answer == "confirm" else "rejected"
    elif answer == "name":
        name = (name or "").strip()
        if not name:
            raise ValueError("answer 'name' needs a non-empty name")
        status, top = "named", None
        record["name"] = name[:200]
    else:
        status = None

    if status:
        conn.execute(
            "INSERT OR REPLACE INTO visit_resolutions (visit_id, top_place_id, status, tier, reasons_json, created_by) "
            "VALUES (?, ?, ?, 'user', ?, 'user')",
            (q["visit_id"], top, status, json.dumps(record, ensure_ascii=False)))
    conn.execute("UPDATE review_questions SET status = ?, answer = ? WHERE id = ?",
                 ("skipped" if answer == "skip" else "answered", json.dumps(record, ensure_ascii=False), question_id))
    conn.commit()
    return {"ok": True, "question_id": question_id, "answer": answer, "visit": visit_card(conn, q["visit_id"])}
