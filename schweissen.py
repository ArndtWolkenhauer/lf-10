import streamlit as st
import openai
import tempfile
import time
import requests
from fpdf import FPDF
import random

# OpenAI Client initialisieren
client = openai.OpenAI()

# Dateien von GitHub laden
urls = {
    "text": "https://raw.githubusercontent.com/ArndtWolkenhauer/texts/main/schweissen-text.txt",
    "fragen": "https://raw.githubusercontent.com/ArndtWolkenhauer/texts/main/schweissen-fragen.txt",
    "antworten": "https://raw.githubusercontent.com/ArndtWolkenhauer/texts/main/schweissen-antworten.txt"
}

def load_text(url):
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        return r.text.strip()
    except:
        return "⚠️ Fehler beim Laden der Datei."

schweiss_text = load_text(urls["text"])
fragen_raw = load_text(urls["fragen"]).splitlines()
antworten_raw = load_text(urls["antworten"]).splitlines()

# Fragen/Antworten als Dictionary
qa_pairs = dict(zip(fragen_raw, antworten_raw))

# System Prompt
system_prompt = f"""
Du bist Fachkundelehrer für Industriemechaniker an einer deutschen Berufsschule. 
Thema: Schweißen.

⚠️ Regeln:
- Sprich und antworte ausschließlich auf Deutsch.
- Interpretiere Schülerantworten immer als deutschsprachig.
- Verwende klare und wertschätzende Sprache.

Aufgaben:
- Nach jeder Schülerantwort:
  1. Gib Anerkennung/Lob für korrekt oder teilweise richtige Inhalte.
  2. Ergänze fehlende Punkte behutsam, falls unvollständig.
  3. Korrigiere falsche Aussagen sachlich.
  4. Stelle ggf. eine **Vertiefungsfrage**, die auf die Antwort eingeht.
- Stelle nur **eine neue Prüfungsfrage**, wenn die aktuelle vollständig bearbeitet wurde.
- Grundlage ist der Text:
\"\"\"{schweiss_text[:2000]}\"\"\"

Die Prüfung hat genau 5 Fragen. Nutze die folgenden Musterantworten zur Bewertung:
{qa_pairs}
"""

st.title("🛠️ Fachkundeprüfung Schweißen – Prüfungs-Simulation")

# --- Session Variablen ---
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "system", "content": system_prompt}]
if "fragen_gestellt" not in st.session_state:
    st.session_state["fragen_gestellt"] = []
if "start_time" not in st.session_state:
    st.session_state["start_time"] = time.time()
if "answer_times" not in st.session_state:
    st.session_state["answer_times"] = []  # Zeitpunkte der Antworten speichern
if "finished" not in st.session_state:
    st.session_state["finished"] = False
if "current_question" not in st.session_state:
    st.session_state["current_question"] = None
if "current_status" not in st.session_state:
    st.session_state["current_status"] = "new"  # new, in_progress, done

# Hilfsfunktion PDF
def safe_text(text):
    return text.encode('latin-1', errors='replace').decode('latin-1')

# --- Timer (5 Minuten) ---
if st.session_state.get("start_time"):
    elapsed = time.time() - st.session_state["start_time"]
    remaining = max(0, 300 - int(elapsed))
    minutes = remaining // 60
    seconds = remaining % 60
    st.info(f"⏱ Verbleibende Zeit: {minutes:02d}:{seconds:02d}")

# --- Gespräch ---
if not st.session_state["finished"]:
    audio_input = st.audio_input("🎙️ Deine Antwort aufnehmen")
    if audio_input:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            f.write(audio_input.getbuffer())
            temp_filename = f.name

        # Speech-to-Text (Deutsch erzwingen)
        with open(temp_filename, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="de"
            )
        user_text = transcript.text
        st.write(f"**Du sagst:** {user_text}")

        # Antwortzeit erfassen
        now = time.time()
        if st.session_state["current_question"] is not None and st.session_state["current_status"]=="in_progress":
            last_question_time = st.session_state["answer_times"][-1][0]
        else:
            last_question_time = st.session_state["start_time"]
        response_time = now - last_question_time
        st.session_state["answer_times"].append((now, response_time))

        st.session_state["messages"].append({"role": "user", "content": user_text})

        # --- Lehrer reagiert auf Antwort ---
        if st.session_state["current_question"] is None:
            # Neue Frage auswählen
            verbleibend = list(set(fragen_raw) - set(st.session_state["fragen_gestellt"]))
            if verbleibend:
                frage = random.choice(verbleibend)
                st.session_state["current_question"] = frage
                st.session_state["fragen_gestellt"].append(frage)
                st.session_state["current_status"] = "in_progress"
                st.session_state["answer_times"].append((time.time(), 0))  # Fragezeit
            else:
                st.session_state["finished"] = True

        if st.session_state["current_question"] is not None:
            frage = st.session_state["current_question"]
            muster = qa_pairs.get(frage, "")

            prompt = st.session_state["messages"] + [{
                "role": "system",
                "content": f"""
                Die Schülerantwort war: "{user_text}"
                Prüfe sie auf:
                  - Vollständigkeit
                  - Richtigkeit
                  - Teilkorrektheiten
                Ergänze fehlende Punkte sachlich und praxisnah.
                Stelle danach eine **Vertiefungsfrage**, die auf die Antwort eingeht.
                Verwende Musterantwort als Referenz:
                {muster}
                Antworte freundlich und wertschätzend.
                """
            }]

            response = client.chat.completions.create(model="gpt-4o-mini", messages=prompt)
            teacher_response = response.choices[0].message.content

            st.session_state["messages"].append({"role": "assistant", "content": teacher_response})
            st.write(f"**Lehrer:** {teacher_response}")

            # Status nach Bearbeitung der Antwort aktualisieren
            st.session_state["current_status"] = "done"  # nach Vertiefung

            # Nach Bearbeitung der Antwort nächste Frage vorbereiten
            st.session_state["current_question"] = None

# --- Feedback & PDF ---
if st.session_state["finished"]:
    user_answers = [m["content"] for m in st.session_state["messages"] if m["role"] == "user"]
    word_counts = [len(ans.split()) for ans in user_answers]
    avg_length = sum(word_counts) / len(word_counts) if word_counts else 0
    total_words = sum(word_counts)
    num_answers = len(user_answers)

    response_times = [rt for _, rt in st.session_state["answer_times"][1:]]  # erste Zeit ignorieren
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0

    eval_prompt = f"""
    Du bist Fachkundelehrer für Industriemechaniker. 
    Bewerte die mündliche Prüfung zum Thema Schweißen nach Kriterien:

    1. Fachliche Korrektheit (60%) - Musterantworten {qa_pairs}
    2. Antwortumfang (25%) - {num_answers} Antworten, Durchschnittslänge {avg_length:.1f} Wörter
    3. Reaktionszeit (15%) - Durchschnittliche Antwortzeit {avg_response_time:.1f} Sekunden

    Erstelle:
    - Note (1-6)
    - Prozentwert 0-100 %
    - Stärken
    - Verbesserungsmöglichkeiten
    """

    feedback = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=st.session_state["messages"] + [{"role": "system", "content": eval_prompt}]
    )
    feedback_text = feedback.choices[0].message.content
    st.subheader("📊 Endbewertung")
    st.write(feedback_text)

    # PDF generieren
    def generate_pdf(messages, feedback_text, filename="schweissen_pruefung.pdf"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, "Fachkundeprüfung Schweißen", ln=True, align="C")
        pdf.ln(10)
        for msg in messages:
            role = msg["role"].capitalize()
            content = safe_text(msg["content"])
            pdf.multi_cell(0, 10, f"{role}: {content}")
            pdf.ln(2)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Endbewertung:", ln=True)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, safe_text(feedback_text))
        pdf.output(filename)
        return filename

    pdf_file = generate_pdf(st.session_state["messages"], feedback_text)
    with open(pdf_file, "rb") as f:
        st.download_button("📥 PDF herunterladen", f, "schweissen_pruefung.pdf")
