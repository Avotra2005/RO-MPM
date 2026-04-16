import streamlit as st
import networkx as nx
import pandas as pd
import plotly.figure_factory as ff
from datetime import datetime, timedelta

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="RO MPM Expert", layout="wide", page_icon="🏗️")

st.title("🏗️ Ordonnancement de Projet : Méthode MPM")
st.markdown("""
Cette application calcule les dates au plus tôt, au plus tard et les marges de vos tâches.
Elle identifie également le **chemin critique** de votre projet.
""")

# Initialisation des données
if 'tasks' not in st.session_state:
    st.session_state.tasks = []

# --- BARRE LATÉRALE : SAISIE ---
with st.sidebar:
    st.header("➕ Ajouter une Tâche")
    with st.form("task_form", clear_on_submit=True):
        id_t = st.text_input("Nom/ID de la tâche (ex: A, B)").upper().strip()
        dur = st.number_input("Durée (en jours)", min_value=1, value=1)
        pred = st.text_input("Prédécesseurs (séparés par des virgules, ex: A,B)")
        
        submit = st.form_submit_button("Ajouter à la liste")
        
        if submit:
            if id_t:
                # On évite les doublons
                if any(t['Tâche'] == id_t for t in st.session_state.tasks):
                    st.error(f"La tâche {id_t} existe déjà !")
                else:
                    p_list = [p.strip().upper() for p in pred.split(",")] if pred else []
                    st.session_state.tasks.append({
                        "Tâche": id_t, 
                        "Durée": dur, 
                        "Prédécesseurs": p_list
                    })
            else:
                st.warning("Veuillez donner un nom à la tâche.")

    if st.button("🗑️ Tout effacer"):
        st.session_state.tasks = []
        st.rerun()

# --- MOTEUR DE CALCUL (RO MPM) ---
if st.session_state.tasks:
    G = nx.DiGraph()
    
    # 1. Création des nœuds avec attributs de durée
    for t in st.session_state.tasks:
        G.add_node(t["Tâche"], d=t["Durée"])
    
    # 2. Création des arcs (liens de dépendance)
    for t in st.session_state.tasks:
        for p in t["Prédécesseurs"]:
            if G.has_node(p):
                G.add_edge(p, t["Tâche"])
            else:
                st.warning(f"⚠️ La tâche '{t['Tâche']}' dépend de '{p}', mais '{p}' n'est pas encore créée.")

    try:
        # Vérification des cycles (Boucles)
        if not nx.is_directed_acyclic_graph(G):
            cycle = nx.find_cycle(G, orientation="original")
            cycle_path = " -> ".join([u for u, v in cycle]) + f" -> {cycle[0][0]}"
            st.error(f"🛑 **Boucle détectée !** Le projet est impossible car ces tâches tournent en rond : {cycle_path}")
        
        elif len(G.nodes) > 0:
            order = list(nx.topological_sort(G))
            
            # --- CALCUL PASSAGE ALLER (DATES AU PLUS TÔT) ---
            tôt = {n: 0 for n in G.nodes}
            for n in order:
                preds = list(G.predecessors(n))
                if preds:
                    tôt[n] = max(tôt[p] + G.nodes[p].get('d', 0) for p in preds)
            
            # Durée totale = fin de la dernière tâche
            duree_totale = max(tôt[n] + G.nodes[n].get('d', 0) for n in G.nodes)
            
            # --- CALCUL PASSAGE RETOUR (DATES AU PLUS TARD) ---
            tard = {n: 0 for n in G.nodes}
            # Initialisation pour les nœuds terminaux
            for n in G.nodes:
                if G.out_degree(n) == 0:
                    tard[n] = duree_totale - G.nodes[n].get('d', 0)
            
            # Parcours inverse
            for n in reversed(order):
                succs = list(G.successors(n))
                if succs:
                    tard[n] = min(tard[s] for s in succs) - G.nodes[n].get('d', 0)

            # --- RÉSULTATS DANS UN TABLEAU ---
            res_data = []
            gantt_data = []
            
            today = datetime.now().date()

            for n in G.nodes:
                es = tôt[n]
                ls = tard[n]
                d = G.nodes[n].get('d', 0)
                mt = ls - es
                est_critique = "OUI" if mt == 0 else "NON"
                
                res_data.append({
                    "Tâche": n, "Durée": d,
                    "Début Tôt": es, "Fin Tôt": es + d,
                    "Début Tard": ls, "Marge Totale": mt,
                    "Critique": est_critique
                })
                
                # Préparation pour le graphique Gantt
                gantt_data.append(dict(
                    Task=n, 
                    Start=str(today + timedelta(days=es)), 
                    Finish=str(today + timedelta(days=es + d)),
                    Resource="Critique" if est_critique == "OUI" else "Normal"
                ))

            df_res = pd.DataFrame(res_data)

            # --- AFFICHAGE ---
            st.divider()
            c1, c2 = st.columns([1, 1])
            
            with c1:
                st.subheader("📊 Tableau d'ordonnancement")
                st.dataframe(df_res.sort_values(by="Début Tôt"), use_container_width=True)
                st.metric("⏳ Durée Totale", f"{duree_totale} jours")

            with c2:
                st.subheader("🕸️ Chemin Critique")
                critiques = df_res[df_res["Critique"] == "OUI"]["Tâche"].tolist()
                st.success(" → ".join(critiques))
                
            st.divider()
            st.subheader("📅 Planning (Gantt)")
            fig = ff.create_gantt(gantt_data, index_col='Resource', show_colorbar=True, group_tasks=True)
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Une erreur inattendue est survenue : {e}")

else:
    st.info("👋 Bienvenue ! Commencez par ajouter des tâches dans le menu à gauche.")