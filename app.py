import streamlit as st
import os
import subprocess
import sys

DB_FILE = os.path.join(os.path.dirname(__file__), "db", "sales.db")
if not os.path.exists(DB_FILE):
    subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "db", "seed.py")],
        check=True,
    )

from core.pipeline import answer_question
from core.charts import make_chart

st.set_page_config(page_title="Assistant BI", page_icon="📊", layout="wide")
st.title("📊 Assistant BI")
st.caption("Posez une question sur les ventes en français. Je génère le SQL et le graphique.")


@st.cache_data(show_spinner=False)
def cached_answer(question: str) -> dict:
    """Même question = même réponse, sans nouvel appel API."""
    return answer_question(question)


def show_result(result: dict, question: str):
    """Affiche SQL, tableau et graphique pour un résultat."""
    if not result["ok"]:
        st.error(f"Impossible de répondre : {result['error']}")
        with st.expander("Voir le SQL tenté"):
            st.code(result["sql"], language="sql")
        return

    df = result["df"]

    with st.expander("Voir la requête SQL"):
        st.code(result["sql"], language="sql")
        if result["attempts"] > 1:
            st.caption(f"Corrigée automatiquement ({result['attempts']} tentatives)")

    if df.empty:
        st.info("La requête n'a renvoyé aucune ligne.")
        return

    # Un seul chiffre : on l'affiche en grand
    if df.shape == (1, 1):
        st.metric(df.columns[0], f"{df.iloc[0, 0]:,}".replace(",", " "))
        return

    fig = make_chart(df, question)
    if fig is not None:
        st.plotly_chart(
    fig,
    use_container_width=True,
    key=f"plotly_chart_{id(fig)}"
)

    st.dataframe(df, use_container_width=True, hide_index=True)


# --- Barre latérale : exemples ---
EXAMPLES = [
    "Quelles sont les ventes par région ce mois-ci ?",
    "Top 5 des produits par chiffre d'affaires",
    "Évolution du chiffre d'affaires par mois sur l'année en cours",
    "Répartition des ventes par catégorie de produit",
    "Quel segment de clients rapporte le plus ?",
]

with st.sidebar:
    st.header("Exemples")
    for ex in EXAMPLES:
        if st.button(ex, use_container_width=True):
            st.session_state["pending"] = ex
    st.divider()
    if st.button("Effacer la conversation", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()

# --- Historique ---
if "messages" not in st.session_state:
    st.session_state["messages"] = []

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.write(msg["content"])
        else:
            show_result(msg["result"], msg["question"])

# --- Nouvelle question ---
typed = st.chat_input("Ex : Quelles sont les ventes par région ce mois-ci ?")
question = typed or st.session_state.pop("pending", None)

if question:
    st.session_state["messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Je réfléchis..."):
            try:
                result = cached_answer(question)
            except Exception as e:
                result = {"ok": False, "sql": "", "error": f"Erreur de l'API : {e}"}
        show_result(result, question)

    st.session_state["messages"].append(
        {"role": "assistant", "result": result, "question": question}
    )