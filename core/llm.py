import os
import re
import sqlite3
import time
from datetime import date

from dotenv import load_dotenv
from groq import Groq, APIStatusError, RateLimitError, APIConnectionError

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "sales.db")
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def get_schema() -> str:
    """Lit automatiquement le schéma de la base (tables + colonnes)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    tables = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()

    lines = []
    for (table,) in tables:
        cols = cur.execute(f"PRAGMA table_info({table})").fetchall()
        col_desc = ", ".join(f"{c[1]} {c[2]}" for c in cols)
        lines.append(f"{table}({col_desc})")
    conn.close()
    return "\n".join(lines)


def build_prompt(question: str) -> str:
    schema = get_schema()
    today = date.today().isoformat()
    return f"""Tu es un expert SQL. Tu traduis des questions en français en requêtes SQLite.

SCHÉMA DE LA BASE :
{schema}

RELATIONS :
- sales.customer_id -> customers.customer_id
- sales.product_id -> products.product_id
- customers.region_id -> regions.region_id

RÈGLES :
- Écris UNIQUEMENT du SQL compatible SQLite.
- Uniquement des requêtes SELECT. Jamais INSERT, UPDATE, DELETE, DROP.
- Les dates sont au format texte YYYY-MM-DD. Utilise strftime() pour filtrer par mois ou année.
- La date d'aujourd'hui est {today}.
- Pour "les ventes" ou "le chiffre d'affaires", utilise SUM(sales.total_amount).
- Donne des alias clairs aux colonnes (ex: chiffre_affaires, region).
- Réponds avec la requête SQL seule, sans explication.
- Les valeurs de customers.segment sont exactement 'Particulier' ou 'Entreprise' (au singulier).
- "Quantité vendue" ou "produits les plus vendus" = SUM(sales.quantity), pas le montant.
- "Chiffre d'affaires" ou "ventes" en euros = SUM(sales.total_amount).
- Ne renvoie que les colonnes demandées par la question : pas d'identifiants (product_id, customer_id...) dans le SELECT, sauf si on les demande.
- Pour regrouper par produit ou client, fais le GROUP BY sur l'identifiant mais ne l'affiche pas dans le SELECT.
- Si la question demande "quel(le) X a le plus...", renvoie le nom ET la valeur.
- Si la question demande "quels clients...", renvoie uniquement le nom du client.
- "Les 6 derniers mois" = sale_date >= date('now', '-6 months').

QUESTION : {question}
SQL :"""


def extract_sql(text: str) -> str:
    """Nettoie la réponse : retire les ```sql ... ``` si présents."""
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1)
    return text.strip().rstrip(";") + ";"


def _call_llm(prompt: str, max_retries: int = 4) -> str:
    """Appelle Groq avec retry (backoff exponentiel) sur les erreurs temporaires."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            return extract_sql(response.choices[0].message.content)
        except (RateLimitError, APIConnectionError):
            if attempt == max_retries - 1:
                raise
            wait = 2 ** (attempt + 1)
            print(f"Limite atteinte ou réseau, nouvel essai dans {wait}s...")
            time.sleep(wait)
        except APIStatusError as e:
            if e.status_code >= 500 and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"Serveur indisponible, nouvel essai dans {wait}s...")
                time.sleep(wait)
            else:
                raise


def question_to_sql(question: str) -> str:
    return _call_llm(build_prompt(question))


def fix_sql(question: str, bad_sql: str, error: str) -> str:
    """Demande au LLM de corriger un SQL qui a échoué."""
    prompt = build_prompt(question) + f"""

Ta requête précédente a échoué.
REQUÊTE : {bad_sql}
ERREUR : {error}

Corrige-la. Réponds avec la requête SQL corrigée seule.
SQL :"""
    return _call_llm(prompt)


if __name__ == "__main__":
    q = "Quelles sont les ventes par région ce mois-ci ?"
    print("Question :", q)
    print("SQL généré :")
    print(question_to_sql(q))