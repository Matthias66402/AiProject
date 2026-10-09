"""Berechnet Matching-Profil + Embedding für bestehende Jobs/Lebensläufe nach,
denen eines davon fehlt (z.B. nach einem fehlgeschlagenen KI-Aufruf) oder
deren Profil mit einem älteren Prompt-Stand erzeugt wurde (match_profile_version
!= PROFILE_VERSION in services/match_profile_service.py). Mit --all werden alle
Einträge neu berechnet. Ausführung z.B. via:
    docker compose exec app python backfill_embeddings.py [--all]
"""
import os
import sys

from dotenv import load_dotenv
from langfuse import get_client
from langfuse.openai import OpenAI

import db
from embeddings import strip_html_to_text, to_vector_literal
from services.match_profile_service import PROFILE_VERSION, job_profile_input, profile_and_embed

load_dotenv()


def _backfill(openai_client, table, kind, columns, to_text, recompute_all):
    conn = db.get_connection()
    try:
        if recompute_all:
            where, params = "", ()
        else:
            where = (" WHERE match_profile IS NULL OR embedding IS NULL"
                     " OR match_profile_version IS DISTINCT FROM %s")
            params = (PROFILE_VERSION,)
        with conn.cursor() as cur:
            cur.execute(f"SELECT id, {columns} FROM {table}{where} ORDER BY id", params)
            rows = cur.fetchall()
        print(f"{table}: {len(rows)} Eintrag/Einträge zu berechnen (Profil-Version {PROFILE_VERSION}).")
        for row in rows:
            fields = profile_and_embed(openai_client, kind, to_text(row))
            if fields["embedding"] is None:
                print(f"  {table} {row['id']}: fehlgeschlagen, übersprungen.")
                continue
            with conn.cursor() as cur:
                cur.execute(f"UPDATE {table} SET match_profile = %s, match_profile_version = %s, "
                            f"embedding = %s::vector WHERE id = %s",
                            (fields["match_profile"], fields["match_profile_version"],
                             to_vector_literal(fields["embedding"]), row["id"]))
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
