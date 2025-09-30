import streamlit as st
import openai
import tempfile
import time
import requests
from fpdf import FPDF
import random

# --- OpenAI Client ---
client = openai.OpenAI()

# --- Dateien von GitHub laden ---
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
qa_pairs = dict(zip(fragen_raw, antworten_raw))

# --- System Prompt ---
system_prompt = f"""
Du bist Fachkundelehrer für Industriemechaniker an einer deutschen Berufsschule. Du bist auch Schweißexperte und bist fachlich kompetent.
Thema: Schweißen.

⚠️ Wichtige Regeln:
- Führe eine mündliche Prüfung zu einem Text und gegebenen Fragen durch.
- Sprich und antworte ausschließlich in deutscher Sprache.
- Interpretiere Schülerantworten immer als deutschsprachig, auch wenn einzelne englische Wörter vorkommen.
- Verwende eine klare, einfache Sprache.

Deine Aufgaben:
- Sprich ruhig, klar und wertschätzend. Stelle gezielte Fragen und fördere ausführliche Antworten.
- Höre aktiv zu und reagiere immer zuerst auf das, was der Schüler gerade gesagt hat.
- Reagiere auf die Antwort des Schülers mit einer ergänzenden oder vertiefenden Nachfrage.
- Stelle pro Runde genau eine Prüfungsfrage aus der Liste.
- Nutze die Musterantworten als Bewertungsgrundlage.
- Maximal praxisnah mit Beispielen zu Arbeitssicherheit, Nahtvorbereitung, Werkstoffen, Verfahren, Parametern, typischen Fehlerbildern.
- Am Ende der 7 Fragen, frage ob weitere Fragen besprochen werden möchten.

Grundlage ist folgender Text:
\"\"\"{schweiss_text[:2000]}\"\"\"

Hier sind die Prüfungsfragen mit den Musterantworten:
{qa_pairs}
"""

# --- Streamlit Titel ---
st.title("🛠️ Fachkundeprüfung Schweißen – Prüfungs-Simulation")

# --- Session Variablen ---
if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "system", "content": system_prompt}]
if "fragen_gestellt" not in st.session_state:
    st.session_state["fragen_gestellt"] = []
if "start_time" not in st.session_state:
    st.session_state["start_time"] = time.time()
if "answer_times" not in st.session_state:
    st.session_state["answer_times"] = []
if "finished" not in st.session_state:
    st.session_state["finished"] = False
if "last_input" not in st.session_state:
    st.session_state["last_input"] = None
if "current_question" not in st.session_state:
    st.session_state["current_question"] = None
if "awaiting_answer" not in st.session_state:
    st.session_state["awaiting_answer"] = False

# --- Hilfsfunktion PDF ---
def safe_text(text):
    return text.encode('latin-1', errors='replace').decode('latin-1')

# --- Timer ---
if st.session_state.get("start_time"):
    elapsed = time.time() - st.session_state["start_time"]
    remaining = max(0, 300 - int(elapsed))
    st.info(f"⏱ Verbleibende Zeit: {remaining//60:02d}:{remaining%60:02d}")

# --- Chat-Verlauf anzeigen ---
st.markdown("### Gesprächsverlauf")
for msg in st.session_state["messages"]:
    if msg["role"] == "assistant":
        st.chat_message("assistant").write(msg["content"])
    elif msg["role"] == "user":
        st.chat_message("user").write(msg["content"])

# --- Eingabe ---
st.markdown("### Deine Antwort (sprich oder schreibe):")
text_input = st.chat_input("✍️ Tippe deine Antwort und drücke Enter")
audio_input = st.audio_input("🎙️ Oder antworte per Sprache (Aufnahme starten)")

# --- Eingabe verarbeiten ---
def process_user_input(user_text: str):
    if not user_text or user_text == st.session_state["last_input"]:
        return None
    st.session_state["last_input"] = user_text

    now = time.time()
    last_q_time = st.session_state["answer_times"][-1][0] if st.session_state["answer_times"] else st.session_state["start_time"]
    response_time = now - last_q_time
    st.session_state["answer_times"].append((now, response_time))

    st.session_state["messages"].append({"role": "user", "content": user_text})

    # --- Wenn keine aktuelle Frage, neue auswählen ---
    if st.session_state["current_question"] is None and len(st.session_state["fragen_gestellt"]) < 7:
        verbleibend = list(set(fragen_raw) - set(st.session_state["fragen_gestellt"]))
        frage = random.choice(verbleibend)
        st.session_state["current_question"] = frage
        st.session_state["fragen_gestellt"].append(frage)
        st.session_state["awaiting_answer"] = True
        st.session_state["answer_times"].append((time.time(), 0))
        prompt_msg = [{
            "role": "system",
            "content": f"Stelle die Prüfungsfrage:\nFrage: {frage}\nMusterantwort: {qa_pairs.get(frage,'')}"
        }]
        response = client.chat.completions.create(model="gpt-4o-mini", messages=st.session_state["messages"] + prompt_msg)
        teacher_response = response.choices[0].message.content
    # --- Wenn auf aktuelle Antwort reagieren ---
    elif st.session_state["awaiting_answer"]:
        prompt_msg = [{
            "role": "system",
            "content": f"Reagiere auf die Antwort des Schülers und stelle bei Bedarf eine vertiefende Rückfrage zur Frage: {st.session_state['current_question']}\nMusterantwort: {qa_pairs.get(st.session_state['current_question'],'')}"
        }]
        response = client.chat.completions.create(model="gpt-4o-mini", messages=st.session_state["messages"] + prompt_msg)
        teacher_response = response.choices[0].message.content

        # --- Prüfen, ob Vertiefung beendet ist ---
        # Hier nehmen wir an: nach jeder Reaktion des Bots wird eine Frage als abgeschlossen markiert
        st.session_state["awaiting_answer"] = False
        st.session_state["current_question"] = None
    else:
        # Prüfung abgeschlossen
        teacher_response = "Die Prüfung ist abgeschlossen."
        st.session_state["finished"] = True

    st.session_state["messages"].append({"role": "assistant", "content": teacher_response})
    return teacher_response

# --- Text-Eingabe ---
if text_input:
    teacher_resp = process_user_input(text_input)
    if teacher_resp is not None:
        st.chat_message("assistant").write(teacher_resp)

# --- Audio-Eingabe ---
if audio_input:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(audio_input.getbuffer())
        temp_filename = f.name
    with open(temp_filename, "rb") as f:
        transcript = client.audio.transcriptions.create(model="whisper-1", file=f, language="de")
    user_text_from_audio = transcript.text
    if user_text_from_audio:
        st.chat_message("user").write(user_text_from_audio)
        teacher_resp = process_user_input(user_text_from_audio)
        if teacher_resp is not None:
            st.chat_message("assistant").write(teacher_resp)

# --- Feedback & PDF ---
if st.session_state["finished"]:
    user_answers = [m["content"] for m in st.session_state["messages"] if m["role"] == "user"]
    word_counts = [len(ans.split()) for ans in user_answers]
    avg_length = sum(word_counts)/len(word_counts) if word_counts else 0
    total_words = sum(word_counts)
    num_answers = len(user_answers)
    response_times = [rt for _, rt in st.session_state["answer_times"][1:]]
    avg_response_time = sum(response_times)/len(response_times) if response_times else 0

    eval_prompt = f"""
    Du bist Fachkundelehrer für Industriemechaniker. 
    Bewerte die mündliche Prüfung zum Thema Schweißen nach folgenden Kriterien:

    1. Fachliche Korrektheit: 60 %
    2. Antwortumfang: 25 % – Antworten: {num_answers}, ∅ Länge: {avg_length:.1f} Wörter, Gesamt: {total_words}
    3. Reaktionszeit: 15 % – ∅ {avg_response_time:.1f} Sekunden
    4. Gesamteindruck:
       - Stärken
       - Verbesserungsmöglichkeiten
       - Note (1–6)
       - Prozentbewertung 0–100 %

    Antworte klar, strukturiert und ausschließlich auf Deutsch.
    """

    feedback = client.chat.completions.create(model="gpt-4o-mini", messages=st.session_state["messages"] + [{"role":"system","content":eval_prompt}])
    feedback_text = feedback.choices[0].message.content
    st.subheader("📊 Endbewertung")
    st.write(feedback_text)

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
