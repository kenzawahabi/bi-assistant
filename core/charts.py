import pandas as pd
import plotly.express as px


def _is_date_like(series: pd.Series) -> bool:
    """Vrai si la colonne ressemble à des dates (2026-10, 2026-10-05...)."""
    name = series.name.lower()
    if any(k in name for k in ("date", "mois", "month", "annee", "année", "year", "jour", "day")):
        return True
    sample = series.astype(str).head(5)
    return sample.str.match(r"^\d{4}-\d{2}(-\d{2})?$").all()


def make_chart(df: pd.DataFrame, question: str = ""):
    """Choisit et construit un graphique Plotly. Renvoie None si inutile."""
    if df is None or df.empty or len(df) < 2:
        return None

    numeric_cols = df.select_dtypes("number").columns.tolist()
    other_cols = [c for c in df.columns if c not in numeric_cols]

    if not numeric_cols or not other_cols:
        return None

    x = other_cols[0]
    y = numeric_cols[0]
    q = question.lower()

    # 1. Série temporelle -> courbe
    if _is_date_like(df[x]):
        data = df.sort_values(x)
        return px.line(data, x=x, y=y, markers=True, title=f"{y} par {x}")

    # 2. Peu de catégories + question de répartition -> camembert
    wants_share = any(k in q for k in ("part ", "parts", "répartition", "repartition", "proportion", "pourcentage"))
    if wants_share and len(df) <= 6 and (df[y] >= 0).all():
        return px.pie(df, names=x, values=y, title=f"{y} par {x}")

    # 3. Beaucoup de catégories -> barres horizontales triées
    if len(df) > 6:
        data = df.sort_values(y, ascending=True).tail(15)
        return px.bar(data, x=y, y=x, orientation="h", title=f"{y} par {x}")

    # 4. Cas général -> barres verticales
    data = df.sort_values(y, ascending=False)
    return px.bar(data, x=x, y=y, title=f"{y} par {x}")


if __name__ == "__main__":
    # Test sans API : données fictives
    ventes_region = pd.DataFrame({
        "region": ["Île-de-France", "Bretagne", "Occitanie"],
        "chiffre_affaires": [53491.98, 24955.69, 25457.21],
    })
    evolution = pd.DataFrame({
        "mois": ["2026-05", "2026-06", "2026-07", "2026-08"],
        "chiffre_affaires": [41000, 45500, 43200, 52000],
    })

    make_chart(ventes_region, "ventes par région").show()
    make_chart(evolution, "évolution par mois").show()