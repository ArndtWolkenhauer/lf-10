import streamlit as st
import openai
import tempfile
import time
import requests
import random
from fpdf import FPDF

# OpenAI Client
client = openai.OpenAI()

# GitHub-Rohlinks
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

# Fragen + Musterantworten als Dictionary
qa_pairs = {}
for i, frage in enumerate(fragen):
    if i < len(antworten):
        qa_pairs[frage] = antworten[i]
    else:
        qa_pairs[frage] = ""

# System Prompt
system_prompt = f"""
Du bist Fachkundelehrer für Industriemechaniker an einer deutschen Berufsschule. 
Thema: Schweißen.
- Sprich ruhig, klar und wertschätzend. Stelle gezielte Fragen und fördere ausführliche Antworten.
- Höre aktiv zu und reagiere immer zuerst auf das, was der Schüler gerade gesagt hat (kurze Bestätigung + passende Nachfrage).
- Stelle pro Runde genau **eine** Prüfungsfrage aus der Liste. 
- Nutze die angegebenen Musterantworten als Bewertungsgrundlage. 
  - Wenn der Schüler teilweise richtig liegt, erkenne das an und ergänze die fehlenden Kernelemente.
  - Erwähne fehlende Inhalte behutsam und praxisnah.
- Maximal fachlich, praxisnah, mit Beispielen zu Arbeitssicherheit, Nahtvorbereitung, Werkstoffen, Verfahren, Parametern, typ. Fehlerbildern.
- Grundlage ist folgender Text, den die Schüler vorher gelesen haben:
\"\"\"{schweiss_text[:2000]}\"\"\"
- Die Prüfung hat genau 5 Fragen.
- Nach jeder Schülerantwort: kurze Würdigung + eine Nachfrage/Vertiefung (aber keine neue Prüfungsfrage).
- Keine Lösungen vorwegnehmen.

Hier sind die Prüfungsfragen mit den Musterantworten:
{ {frage: qa_pairs[frage] for frage in list(qa_pairs.keys())[:10]} }
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
if "feedback" not in st.session_state:
    st.session_state["feedback"] = ""

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

        # Lehrerantwort
        if st.session_state["fragen_gestellt"] < 5:
            q = random.choice([fq for fq in fragen if fq not in st.session_state["used_questions"]])
            st.session_state["used_questions"].append(q)
            st.session_state["fragen_gestellt"] += 1
            muster = qa_pairs.get(q, "")

            teacher_prompt = st.session_state["messages"] + [{
                "role": "system",
                "content": f"""
Reagiere zuerst kurz auf die Schülerantwort, 
dann stelle die folgende Prüfungsfrage:
'{q}'

Nutze diese Musterantwort als Referenz für deine Bewertung:
'{muster}'
"""
            }]

            response = client.chat.completions.create(model="gpt-4o-mini", messages=teacher_prompt)
            teacher_text = response.choices[0].message.content
            st.session_state["messages"].append({"role": "assistant", "content": teacher_text})
            st.write(f"**Lehrer:** {teacher_text}")
        else:
            st.session_state["finished"] = True

# Feedback am Ende
if st.session_state["finished"] and not st.session_state["feedback"]:
    st.subheader("📊 Endbewertung")

    feedback = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=st.session_state["messages"] + [{
            "role": "system",
            "content": f"""
Erstelle eine Zusammenfassung des Prüfungsgesprächs.
Bewerte die Schülerantworten anhand der bereitgestellten Musterantworten:
{qa_pairs}

Gib Feedback zu:
- Fachwissen (korrekt, teilweise, fehlend)
- Vollständigkeit
- Praxisbezug
- Ausdruck und Fachsprache

Schließe mit einer Endnote (1–6).
"""
        }]
    )
    st.session_state["feedback"] = feedback.choices[0].message.content
    st.write(st.session_state["feedback"])

# 📄 PDF Export
if st.session_state["finished"] and st.session_state["feedback"]:
    def create_pdf(messages, feedback):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        pdf.multi_cell(0, 10, "📑 Prüfungsprotokoll – Mündliche Prüfung Schweißen\n", align="L")
        pdf.ln(5)

        for msg in messages:
            if msg["role"] == "user":
                pdf.set_text_color(0, 0, 150)
                pdf.multi_cell(0, 8, f"Schüler: {msg['content']}")
            elif msg["role"] == "assistant":
                pdf.set_text_color(0, 100, 0)
                pdf.multi_cell(0, 8, f"Lehrer: {msg['content']}")
            pdf.ln(2)

        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)
        pdf.multi_cell(0, 10, "📊 Endbewertung:\n", align="L")
        pdf.multi_cell(0, 8, feedback)

        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf.output(tmp_file.name)
        return tmp_file.name

    pdf_file = create_pdf(st.session_state["messages"], st.session_state["feedback"])
    with open(pdf_file, "rb") as f:
        st.download_button("⬇️ Prüfungsprotokoll als PDF speichern", f, file_name="pruefung_schweissen.pdf")
