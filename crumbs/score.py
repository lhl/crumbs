"""Scoring (DAT-06 v1): labels vs model output.

Reads the append-only `labels` table (human, source='user') and the latest
classification per photo, and reports: category confusion, accuracy with
abstention treated explicitly (model 'unknown' is scored as abstention, not
silently as an error class), and dish-label recall against extraction
output. Emits JSON so numbers can flow into reports without hand-typing.
"""

import json
from collections import Counter


def score_all(conn) -> dict:
    labels = conn.execute(
        "SELECT media_id, field, value FROM labels WHERE source = 'user'"
    ).fetchall()
    by_media: dict[int, dict] = {}
    for media_id, field, value in labels:
        by_media.setdefault(media_id, {}).setdefault(field, []).append(value)

    cat_labels = {m: v["category"][0] for m, v in by_media.items() if "category" in v}
    report: dict = {"labeled_media": len(by_media), "category_labels": len(cat_labels)}
    if not cat_labels:
        report["note"] = (
            "No user category labels yet. Label the food + unknown slice in `crumbs label` "
            "(~50-100 items) and this command produces the confusion table."
        )
        return report

    confusion: Counter = Counter()
    correct = abstained = 0
    for media_id, truth in cat_labels.items():
        row = conn.execute(
            "SELECT json_extract(labels_json, '$.category') FROM classifications "
            "WHERE media_id = ? ORDER BY id DESC LIMIT 1", (media_id,),
        ).fetchone()
        pred = row[0] if row else None
        confusion[(truth, pred)] += 1
        if pred == "unknown" and truth != "unknown":
            abstained += 1
        elif pred == truth:
            correct += 1
    decided = sum(n for (t, p), n in confusion.items() if p != "unknown")
    report["category"] = {
        "accuracy_all": round(correct / len(cat_labels), 3),
        "accuracy_when_decided": round(correct / decided, 3) if decided else None,
        "abstentions_on_labeled": abstained,
        "confusion": {f"{t}->{p}": n for (t, p), n in sorted(confusion.items())},
    }

    dish_truth = {m: [x.lower() for x in v["dish"]] for m, v in by_media.items() if "dish" in v}
    if dish_truth:
        hits = checked = 0
        for media_id, truths in dish_truth.items():
            row = conn.execute(
                "SELECT data_json FROM extractions WHERE media_id = ? ORDER BY id DESC LIMIT 1", (media_id,)
            ).fetchone()
            got = []
            if row:
                got = [d["name"].lower() for d in json.loads(row[0]).get("dish_candidates", [])]
            for t in truths:
                checked += 1
                if any(t in g or g in t for g in got):
                    hits += 1
        report["dishes"] = {"labeled_dishes": checked, "found_in_extraction": hits,
                            "recall": round(hits / checked, 3) if checked else None}
    return report
