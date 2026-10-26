import json
import os
import sqlite3
import sys

# permet d'importer "core" depuis le dossier eval
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.llm import question_to_sql, fix_sql
from core.sql_guard import run_query

HERE = os.path.dirname(__file__)
QUESTIONS_PATH = os.path.join(HERE, "questions.json")
RESULTS_PATH = os.path.join(HERE, "results.json")
DB_PATH = os.path.join(HERE, "..", "db", "sales.db")


def normalize(rows):
    """Rend les résultats comparables : arrondi des nombres, tri des lignes."""
    out = []
    for row in rows:
        out.append(tuple(
            round(v, 2) if isinstance(v, float) else v for v in row
        ))
    return sorted(out, key=lambda r: tuple(str(x) for x in r))


def run_reference(sql):
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def generate_and_run(question, max_fixes=2):
    """Même logique que le pipeline, mais renvoie aussi le nombre de corrections."""
    sql = question_to_sql(question)
    for attempt in range(max_fixes + 1):
        try:
            cols, rows = run_query(sql)
            return sql, rows, attempt, None
        except Exception as e:
            if attempt == max_fixes:
                return sql, None, attempt, str(e)
            sql = fix_sql(question, sql, str(e))


def is_correct(expected, got):
    """Compare les résultats, en ignorant l'ordre des lignes et les noms de colonnes."""
    if got is None:
        return False
    return normalize(expected) == normalize(got)


def main():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = json.load(f)

    # On reprend les résultats déjà obtenus (utile avec le quota quotidien)
    results = {}
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH, encoding="utf-8") as f:
            results = json.load(f)

    for item in questions:
        q = item["question"]
        if q in results:
            continue  # déjà évaluée

        print(f"\n> {q}")
        try:
            sql, rows, fixes, error = generate_and_run(q)
        except Exception as e:
            print(f"  Arrêt (API) : {str(e)[:150]}")
            print("  Relancez plus tard, le script reprendra ici.")
            break

        expected = run_reference(item["reference_sql"])
        ok = is_correct(expected, rows)
        results[q] = {
            "correct": ok,
            "fixes": fixes,
            "generated_sql": sql,
            "error": error,
        }
        print(f"  {'OK' if ok else 'ÉCHEC'} (corrections : {fixes})")

        # Sauvegarde après chaque question
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    # Bilan
    done = len(results)
    good = sum(1 for r in results.values() if r["correct"])
    if done:
        print("\n" + "=" * 50)
        print(f"Évaluées : {done}/{len(questions)}")
        print(f"Correctes : {good}/{done} ({100 * good / done:.0f} %)")
        needed_fix = sum(1 for r in results.values() if r["fixes"] > 0)
        print(f"Ayant nécessité une correction : {needed_fix}")


if __name__ == "__main__":
    main()