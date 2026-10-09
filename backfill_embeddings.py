"""Einmalig ausführbares Skript, um für bestehende Jobs/Lebensläufe ohne
Embedding eines nachzuberechnen. Ausführung z.B. via:
    docker compose exec app python backfill_embeddings.py
"""
import os

from dotenv import load_dotenv
from langfuse import get_client
from langfuse.openai import OpenAI

import db
from embeddings import embed_texts, strip_html_to_text, to_vector_literal

load_dotenv()


def backfill_jobs(openai_client):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, position, content FROM jobs WHERE embedding IS NULL")
            jobs = cur.fetchall()
        print(f"{len(jobs)} Job(s) ohne Embedding gefunden.")
        if not jobs:
            return
        texts = [f"{job['position']}\n\n{strip_html_to_text(job['content'])}" for job in jobs]
        embeddings = embed_texts(openai_client, texts)
        for job, embedding in zip(jobs, embeddings):
            if embedding is None:
                print(f"  Job {job['id']}: Embedding fehlgeschlagen, übersprungen.")
                continue
            with conn.cursor() as cur:
                cur.execute("UPDATE jobs SET embedding = %s::vector WHERE id = %s",
                            (to_vector_literal(embedding), job["id"]))
            print(f"  Job {job['id']}: Embedding gespeichert.")
    finally:
        conn.close()


def backfill_resumes(openai_client):
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, content FROM resumes WHERE embedding IS NULL")
            resumes = cur.fetchall()
        print(f"{len(resumes)} Lebenslauf/Lebensläufe ohne Embedding gefunden.")
        if not resumes:
            return
        texts = [strip_html_to_text(resume["content"]) for resume in resumes]
        embeddings = embed_texts(openai_client, texts)
        for resume, embedding in zip(resumes, embeddings):
            if embedding is None:
                print(f"  Resume {resume['id']}: Embedding fehlgeschlagen, übersprungen.")
                continue
            with conn.cursor() as cur:
                cur.execute("UPDATE resumes SET embedding = %s::vector WHERE id = %s",
                            (to_vector_literal(embedding), resume["id"]))
            print(f"  Resume {resume['id']}: Embedding gespeichert.")
    finally:
        conn.close()


if __name__ == "__main__":
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    db.init_db()
    backfill_jobs(openai_client)
    backfill_resumes(openai_client)
    # Kurzlebiges Skript: gepufferte Langfuse-Traces vor dem Beenden senden.
    get_client().flush()
