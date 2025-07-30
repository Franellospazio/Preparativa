from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import os
import time

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
FILE_TXT = os.path.join(DATA_DIR, "c.txt")
FILE_CODICI = os.path.join(DATA_DIR, "codici.xlsx")


compilazioni = []
ultimo_backup = time.time()
hash_ultimo_salvato = ""

def carica_dati():
    usecols = [1, 2, 3, 5, 6]
    df_campioni = pd.read_csv(FILE_TXT, sep="\t", header=0, usecols=usecols, dtype=str)
    df_campioni.columns = ["ID", "Evasione", "Richiedente", "Descrizione campione", "Codice"]
    df_campioni["Evasione"] = pd.to_datetime(df_campioni["Evasione"], errors="coerce", dayfirst=True)
    df_campioni = df_campioni.dropna(subset=["Evasione"])

    df_codici = pd.read_excel(FILE_CODICI)
    df_codici["Codice"] = df_codici["Codice"].astype(str)

    return df_campioni, df_codici

def estrai_opzioni_predefinite_hardcoded(df_codici):
    mappa_valore_colonna = {
        "2": 30,
        "3": 31,
        "4": 32,
    }
    dizionario_opzioni = {}
    for valore, col_idx in mappa_valore_colonna.items():
        if col_idx >= len(df_codici.columns):
            continue
        colonna_nome = df_codici.columns[col_idx]
        opzioni = df_codici[colonna_nome].iloc[1:].dropna().astype(str).tolist()
        dizionario_opzioni[valore] = opzioni
    return dizionario_opzioni

@app.route("/", methods=["GET", "POST"])
def index():
    global compilazioni
    redirect_to = None  # **Importantissimo** per evitare UnboundLocalError

    df_campioni, df_codici = carica_dati()
    opzioni_predefinite = estrai_opzioni_predefinite_hardcoded(df_codici)
    selected_id = request.args.get("selected_id", "")
    campione_info = {}

    if request.method == "POST":
        id_campione = selected_id
        # Rimuovo compilazioni esistenti per questo ID
        compilazioni = [c for c in compilazioni if c["ID"] != id_campione]

        codici_assoc = df_campioni[df_campioni["ID"] == id_campione]["Codice"].astype(str).unique()

        for codice in codici_assoc:
            riga_codice = df_codici[df_codici["Codice"] == codice]
            if riga_codice.empty:
                continue
            tipologia = str(riga_codice.iloc[0]["Tipologia di analisi"])
            record = {"ID": id_campione, "Tipologia": tipologia}
            for col in df_codici.columns[3:33]:
                key = f"campo__{id_campione}__{tipologia}__{col}"
                record[col] = request.form.get(key, "").strip()
            compilazioni.append(record)

        # Recupero redirect_to dal form, se presente
        redirect_to = request.form.get("redirect_to")

        # Se redirect_to è valorizzato, faccio redirect a GET
        if redirect_to:
            return redirect(f"/?selected_id={redirect_to}")

        # Se non c'è redirect_to, torno all’index senza parametri (opzionale)
        return redirect(url_for("index"))

    # --- codice GET ---

    tipologie_info = []
    codici_mancanti = []
    risultati_dict = {}

    if selected_id:
        df_selezionato = df_campioni[df_campioni["ID"] == selected_id]
        if not df_selezionato.empty:
            campione_info = {
                "evasione": (
                    df_selezionato.iloc[0]["Evasione"].strftime("%d/%m/%Y").lower()
                    if pd.notna(df_selezionato.iloc[0]["Evasione"]) else ""
                ),
                "richiedente": str(df_selezionato.iloc[0]["Richiedente"]).lower(),
                "descrizione": str(df_selezionato.iloc[0]["Descrizione campione"]).lower()
            }

        codici_associati = df_selezionato["Codice"].astype(str).unique()
        codici_presenti = df_codici["Codice"].astype(str).unique()
        codici_mancanti = [c for c in codici_associati if c not in codici_presenti]

        tipologie_dict = {}
        for codice in codici_associati:
            riga = df_codici[df_codici["Codice"] == codice]
            if riga.empty:
                continue
            tipologia = str(riga.iloc[0]["Tipologia di analisi"])
            preparativa = str(riga.iloc[0]["Preparativa"])
            if tipologia not in tipologie_dict:
                tipologie_dict[tipologia] = {
                    "tipologia": tipologia,
                    "descrizione": preparativa,
                    "campi": {}
                }

            for col in df_codici.columns[3:33]:
                val = str(riga.iloc[0][col]).strip().lower()
                if val in ("", "nan"):
                    continue
                elif val in ("x", "1"):
                    tipo = "input"
                    opzioni = []
                elif val in ("2", "3", "4"):
                    tipo = "select"
                    opzioni = opzioni_predefinite.get(val, [])
                else:
                    continue

                if col not in tipologie_dict[tipologia]["campi"]:
                    tipologie_dict[tipologia]["campi"][col] = {
                        "nome": col,
                        "tipo": tipo,
                        "opzioni": opzioni
                    }

        for tip in tipologie_dict.values():
            tip["campi"] = list(tip["campi"].values())
            tipologie_info.append(tip)

        for r in compilazioni:
            if r["ID"] == selected_id:
                tip = r["Tipologia"]
                if tip not in risultati_dict:
                    risultati_dict[tip] = {}
                for k, v in r.items():
                    if k not in ("ID", "Tipologia"):
                        risultati_dict[tip][k] = v

    unique_ids = sorted(df_campioni["ID"].astype(str).unique())

    return render_template(
        "index.html",
        unique_ids=unique_ids,
        selected_id=selected_id,
        tipologie_info=tipologie_info,
        risultati=risultati_dict,
        codici_mancanti=codici_mancanti,
        campione_info=campione_info
    )

if __name__ == "__main__":
    app.run(debug=True)
