"""Bewertet das Lebenslauf<->Stellen-Matching gegen die fachliche Einordnung in
eval/matching_labels.json: Ähnlichkeit aller Paare aus Stelle und allgemeiner
Lebenslauf-Version (nicht gelöscht, mit Embedding), Trefferquote je Schwelle,
beste Schwelle im Vergleich zu MIN_MATCH_SIMILARITY und Ausreißer. Liest nur,
ändert nichts. Nach Änderungen am Profil-Prompt (PROFILE_VERSION in
services/match_profile_service.py) und dem Backfill ausführen, z.B. via:
    docker compose exec app python eval_matching.py
"""
import json
import os
import statistics

from dotenv import load_dotenv

import db

load_dotenv()

LABELS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval", "matching_labels.json")
THRESHOLDS = [0.60, 0.65, 0.70, 0.71, 0.72, 0.75, 0.78, 0.80, 0.85]


def load_pairs():
    """Ähnlichkeit aller Paare - dieselbe Auswahl wie das Matching (allgemeine
    Lebenslauf-Versionen, keine gelöschten Einträge), ohne Schwelle und Filter."""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT j.id AS job_id, j.position, r.id AS resume_id,
                       split_part(r.match_profile, E'\\n', 1) AS resume_role,
                       1 - (j.embedding <=> r.embedding) AS similarity
                FROM jobs j
                JOIN resumes r ON NOT r.deleted AND r.target_job_id IS NULL AND r.embedding IS NOT NULL
                WHERE NOT j.deleted AND j.embedding IS NOT NULL
            """)
            return cur.fetchall()
    finally:
        conn.close()


def classify(pairs, labels):
    """Teilt die Paare in passend/teilweise/unpassend; nicht eingeordnete IDs
    werden gesammelt statt geraten."""
    partial = {tuple(p) for p in labels["partial"]}
    groups = {"passend": [], "teilweise": [], "unpassend": []}
    unknown_jobs, unknown_resumes = set(), set()
    for pair in pairs:
        job_field = labels["jobs"].get(str(pair["job_id"]))
        resume_field = labels["resumes"].get(str(pair["resume_id"]))
        if job_field is None:
            unknown_jobs.add(pair["job_id"])
        if resume_field is None:
            unknown_resumes.add(pair["resume_id"])
        if job_field is None or resume_field is None:
            continue
        if job_field == resume_field:
            groups["passend"].append(pair)
        elif (job_field, resume_field) in partial:
            groups["teilweise"].append(pair)
        else:
            groups["unpassend"].append(pair)
    return groups, unknown_jobs, unknown_resumes


def _fmt(pair):
    return (f"{pair['similarity']:.3f}  Stelle {pair['job_id']} ({pair['position'][:40]})"
            f" <-> Lebenslauf {pair['resume_id']} ({pair['resume_role'][:50]})")


def main():
    with open(LABELS_FILE, encoding="utf-8") as f:
        labels = json.load(f)
    groups, unknown_jobs, unknown_resumes = classify(load_pairs(), labels)
    good = sorted(p["similarity"] for p in groups["passend"])
    bad = sorted(p["similarity"] for p in groups["unpassend"])
    if not good or not bad:
        print("Zu wenig eingeordnete Paare für eine Auswertung - eval/matching_labels.json ergänzen.")
        return

    print("Verteilung der Ähnlichkeit:")
    for name, values in (("passend", good), ("teilweise", sorted(p["similarity"] for p in groups["teilweise"])),
                         ("unpassend", bad)):
        if values:
            print(f"  {name:10} n={len(values):3}  min={values[0]:.3f}  median={statistics.median(values):.3f}"
                  f"  max={values[-1]:.3f}")

    print(f"\nSchwelle   passend erkannt   unpassend durchgerutscht   (aktuell: {db.MIN_MATCH_SIMILARITY:.2f})")
    for t in THRESHOLDS:
        marker = "  <- aktuell" if abs(t - db.MIN_MATCH_SIMILARITY) < 1e-9 else ""
        print(f"  {t:.2f}     {sum(s >= t for s in good):3}/{len(good):<3}           "
              f"{sum(s >= t for s in bad):3}/{len(bad):<3}{marker}")

    # Beste Schwelle: knapp über dem höchsten unpassenden Paar - die niedrigste
    # Schwelle ohne unpassende Treffer und damit mit den meisten erkannten passenden.
    best = round(bad[-1] + 0.005, 2)
    print(f"\nEmpfohlene Schwelle (kein unpassendes Paar darüber): {best:.2f} -> "
          f"{sum(s >= best for s in good)}/{len(good)} passende erkannt")

    threshold = db.MIN_MATCH_SIMILARITY
    missed = [p for p in groups["passend"] if p["similarity"] < threshold]
    false_hits = [p for p in groups["unpassend"] if p["similarity"] >= threshold]
    print(f"\nPassend, aber unter {threshold:.2f} ({len(missed)}):")
    for pair in sorted(missed, key=lambda p: p["similarity"]):
        print("  " + _fmt(pair))
    print(f"Unpassend, aber ab {threshold:.2f} ({len(false_hits)}):")
    for pair in sorted(false_hits, key=lambda p: -p["similarity"]):
        print("  " + _fmt(pair))

    if unknown_jobs or unknown_resumes:
        print(f"\nHinweis: nicht eingeordnet (in der Auswertung ignoriert) - Stellen {sorted(unknown_jobs)}, "
              f"Lebensläufe {sorted(unknown_resumes)}")


if __name__ == "__main__":
    main()