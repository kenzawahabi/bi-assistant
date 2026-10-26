import os
import sqlite3

import sqlglot
from sqlglot import exp

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "sales.db")
MAX_ROWS = 1000

# Types d'instructions dangereuses (on refuse si on en trouve une n'importe où)
FORBIDDEN = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
    exp.Alter, exp.Command, exp.Pragma, exp.Attach, exp.Transaction,
)


class UnsafeSQLError(Exception):
    """Levée quand la requête n'est pas autorisée."""


def validate_sql(sql: str) -> str:
    """Vérifie que le SQL est un seul SELECT sûr. Renvoie le SQL nettoyé."""
    try:
        statements = sqlglot.parse(sql, read="sqlite")
    except sqlglot.errors.ParseError as e:
        raise UnsafeSQLError(f"SQL invalide : {e}")

    statements = [s for s in statements if s is not None]

    if len(statements) != 1:
        raise UnsafeSQLError("Une seule requête est autorisée.")

    tree = statements[0]

    if not isinstance(tree, (exp.Select, exp.Union, exp.With)):
        raise UnsafeSQLError("Seules les requêtes SELECT sont autorisées.")

    for node in tree.walk():
        if isinstance(node, FORBIDDEN):
            raise UnsafeSQLError(
                f"Opération interdite : {type(node).__name__}"
            )

    # Ajoute un LIMIT si absent
    if isinstance(tree, exp.Select) and not tree.args.get("limit"):
        tree = tree.limit(MAX_ROWS)

    return tree.sql(dialect="sqlite") + ";"


def run_query(sql: str):
    """Valide puis exécute le SQL en lecture seule. Renvoie (colonnes, lignes)."""
    safe_sql = validate_sql(sql)

    # mode=ro : SQLite refuse toute écriture, même si la validation échouait
    uri = "file:" + os.path.abspath(DB_PATH).replace("\\", "/") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cur = conn.execute(safe_sql)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(MAX_ROWS)
    finally:
        conn.close()
    return columns, rows

def fix_sql(question: str, bad_sql: str, error: str) -> str:
    """Demande au LLM de corriger un SQL qui a échoué."""
    prompt = build_prompt(question) + f"""

Ta requête précédente a échoué.
REQUÊTE : {bad_sql}
ERREUR : {error}

Corrige-la. Réponds avec la requête SQL corrigée seule.
SQL :"""
    for attempt in range(4):
        try:
            response = client.models.generate_content(model=MODEL, contents=prompt)
            return extract_sql(response.text)
        except errors.ServerError:
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))

if __name__ == "__main__":
    tests = [
        "SELECT region_name FROM regions",
        "DROP TABLE sales",
        "DELETE FROM sales WHERE sale_id = 1",
        "SELECT * FROM sales; DROP TABLE sales",
        "UPDATE products SET unit_price = 0",
        "PRAGMA table_info(sales)",
    ]
    for t in tests:
        try:
            cols, rows = run_query(t)
            print(f"AUTORISÉ  : {t}  ->  {len(rows)} lignes")
        except Exception as e:
            print(f"BLOQUÉ    : {t}  ->  {e}")