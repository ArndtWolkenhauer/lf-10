import streamlit as st
import openai
import tempfile
import time
import requests
import random
from fpdf import FPDF

# OpenAI Client
client = openai.OpenAI()

# GitHub-Rohlinks für Text, Fragen und Antworten
text_url = "https://raw.githubusercontent.com/ArndtWolkenhauer/texts/main/schweissen-text.txt"
fragen_url = "https://raw.githubusercontent.com/ArndtWolkenhauer/texts/main/schweissen-fragen.txt"
antworten_url = "https://raw.githubusercontent.com/ArndtWolkenhauer/texts/main/schweissen-antworten.txt"

def load_file(url):
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        return r.text.strip().splitlines()
    except Exception as e:
        st.error(f"Fehler beim Laden von {url}: {e}")
        return []

# Dateien laden
schweiss_text = "\n".join(load_file(text_url))
fragen = load_file(fragen_url)
antworten = load_file(antworten_url)

# System Prompt
system_prompt = f"""
Du bist Fachkundelehrer für Industriemechaniker an einer deutschen Berufsschule in Niedersachsen. Gesprochen wird ausschließlich deutsch.
Thema: Schweißen.
- DU führst eine mündliche Prüfung zu dem Thema Schweissen durch. Die Schüler hatten einen Text und Fragen ( vorgegebenen Liste) dazu.
- Sprich ruhig, klar und wertschätzend. Stelle gezielte Fragen und fördere ausführliche Antworten.
- Höre aktiv zu und reagiere immer zuerst auf das, was der Schüler gerade gesagt hat (kurze Bestätigung + passende Nachfrage).
- Stelle pro Runde genau **eine** Prüfungsfrage (aus der vorgegebenen Liste). 
- Wenn Antwort sehr kurz/unklar: bitte um Konkretisierung.
- Falls der Schüler fachlich teilweise richtig liegt, erkenne das an und ergänze schonend fehlende Kernelemente.
- Maximal fachlich, praxisnah, mit Beispielen zu Arbeitssicherheit, Nahtvorbereitung, Werkstoffen, Verfahren, Parametern, typ. Fehlerbildern.
- Grundlage ist folgender Text, den die Schüler vorher gelesen haben:
\"\"\"{schweiss_text[:2000]}\"\"\"
- Die Prüfung hat genau 5 Fragen aus der gegeben Liste, es können sich im Gespräch aber auch zusätzliche Fragen ergeben.
- Nach jeder Schülerantwort: kurze Würdigung + eine Nachfrage/Vertiefung (aber keine neue Prüfungsfrage).
- Keine Lösungen vorwegnehmen.
"""

st.title("🛠️ Mündliche Prüfung Schweißen – Berufsschule")

# Session-State
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "system", "content": system_prompt}]
if "fragen_gestellt" not in st.session_state:
    st.session_state["fragen_gestellt"] = 0
if "used_questions" not in st.session_state:
    st.session_state["used_questions"] = []
if "finished" not in st.session_state:
    st.session_state["finished"] = False

# Prüfungsgespräch
if not st.session_state["finished"]:
    audio_input = st.audio_input("🎙️ Deine Antwort aufnehmen")
    if audio_input:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            f.write(audio_input.getbuffer())
            temp_filename = f.name

        # Speech-to-Text
        with open(temp_filename, "rb") as f:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=f)
        user_text = transcript.text
        st.write(f"**Du sagst:** {user_text}")
        st.session_state["messages"].append({"role": "user", "content": user_text})

        # Lehrer reagiert
        if st.session_state["fragen_gestellt"] < 5:
            # Neue Prüfungsfrage auswählen
            if st.session_state["fragen_gestellt"] >= len(st.session_state["used_questions"]):
                q = random.choice([fq for fq in fragen if fq not in st.session_state["used_questions"]])
                st.session_state["used_questions"].append(q)
                st.session_state["fragen_gestellt"] += 1
                teacher_prompt = st.session_state["messages"] + [{"role": "system", "content": f"Reagiere zuerst kurz auf die Schülerantwort, dann stelle folgende Prüfungsfrage: {q}"}]
            else:
                teacher_prompt = st.session_state["messages"]

            response = client.chat.completions.create(model="gpt-4o-mini", messages=teacher_prompt)
            teacher_text = response.choices[0].message.content
            st.session_state["messages"].append({"role": "assistant", "content": teacher_text})
            st.write(f"**Lehrer:** {teacher_text}")
        else:
            st.session_state["finished"] = True

# Feedback am Ende
if st.session_state["finished"]:
    st.subheader("📊 Endbewertung")

    feedback = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=st.session_state["messages"] + [{"role": "system", "content": "Erstelle eine Zusammenfassung des Prüfungsgesprächs. Bewerte den Schüler (1–6), gehe dabei auf Fachwissen, Vollständigkeit, Praxisbezug und Ausdruck ein."}]
    )
    feedback_text = feedback.choices[0].message.content
    st.write(feedback_text)


