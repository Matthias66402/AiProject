"""Berechnet für bestehende Jobs/Lebensläufe ohne Matching-Profil (oder ohne
Embedding) beides nach - z.B. für Bestandsdaten von vor Einführung der
Matching-Profile oder nach einem fehlgeschlagenen KI-Aufruf. Mit --all werden
alle Einträge neu berechnet (z.B. nach einer Änderung am Profil-Prompt in
services/match_profile_service.py). Ausführung z.B. via:
    docker compose exec app python backfill_embeddings.py [--all]
"""
import os
import sys

from dotenv import load_dotenv
from langfuse import get_client
from langfuse.openai import OpenAI

import db
from embeddings import strip_html_to_text, to_vector_literal
from services.match_profile_service import job_profile_input, profile_and_embed

load_dotenv()


def _backfill(openai_client, table, kind, columns, to_text, recompute_all):
    conn = db.get_connection()
    try:
        where = "" if recompute_all else " WHERE match_profile IS NULL OR embedding IS NULL"
        with conn.cursor() as cur:
            cur.execute(f"SELECT id, {columns} FROM {table}{where} ORDER BY id")
            rows = cur.fetchall()
        print(f"{table}: {len(rows)} Eintrag/Einträge zu berechnen.")
        for row in rows:
            match_profile, embedding = profile_and_embed(openai_client, kind, to_text(row))
            if embedding is None:
                print(f"  {table} {row['id']}: fehlgeschlagen, übersprungen.")
                continue
            with conn.cursor() as cur:
                cur.execute(f"UPDATE {table} SET match_profile = %s, embedding = %s::vector WHERE id = %s",
                            (match_profile, to_vector_literal(embedding), row["id"]))
            print(f"  {table} {row['id']}: Profil + Embedding gespeichert.")
    finally:
        conn.close()


if __name__ == "__main__":
    recompute_all = "--all" in sys.argv[1:]
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    db.init_db()
    _backfill(openai_client, "jobs", "job", "position, content",
              lambda job: job_profile_input(job["position"], job["content"]), recompute_all)
    _backfill(openai_client, "resumes", "resume", "content",
              lambda resume: strip_html_to_text(resume["content"]), recompute_all)
    # Kurzlebiges Skript: gepufferte Langfuse-Traces vor dem Beenden senden.
    get_client().flush()
