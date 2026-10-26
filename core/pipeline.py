import sqlite3

import pandas as pd

from core.llm import question_to_sql, fix_sql
from core.sql_guard import run_query, UnsafeSQLError

MAX_FIXES = 2


def answer_question(question: str) -> dict:
    """Question -> SQL -> exécution (avec auto-correction). Renvoie un dict."""
    sql = question_to_sql(question)
    history = []  # trace des tentatives, utile pour le debug et le README

    for attempt in range(MAX_FIXES + 1):
        try:
            columns, rows = run_query(sql)
            df = pd.DataFrame(rows, columns=columns)
            return {
                "ok": True,
                "sql": sql,
                "df": df,
                "attempts": attempt + 1,
                "history": history,
            }
        except UnsafeSQLError as e:
            # Requête dangereuse : on ne corrige pas, on refuse
            return {"ok": False, "sql": sql, "error": str(e),
                    "attempts": attempt + 1, "history": history}
        except (sqlite3.Error, Exception) as e:
            history.append({"sql": sql, "error": str(e)})
            if attempt == MAX_FIXES:
                return {"ok": False, "sql": sql, "error": str(e),
                        "attempts": attempt + 1, "history": history}
            sql = fix_sql(question, sql, str(e))


if __name__ == "__main__":
    questions = [
        "Quelles sont les ventes par région ce mois-ci ?",
         #"Top 5 des produits les plus vendus en quantité",
         #"Évolution du chiffre d'affaires par mois sur l'année en cours",
    ]
    for q in questions:
        print("\n" + "=" * 60)
        print("Question :", q)
        result = answer_question(q)
        print("SQL :", result["sql"])
        if result["ok"]:
            print(f"Tentatives : {result['attempts']}")
            print(result["df"].head(10).to_string(index=False))
        else:
            print("ÉCHEC :", result["error"])