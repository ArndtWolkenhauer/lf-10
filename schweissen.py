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
Du bist Fachkundelehrer für Industriemechaniker an einer deutschen Berufsschule. Du bist auch Schweißexperte und bist fachlich kompetent.
Thema: Schweißen.

⚠️ Wichtige Regeln:
- Führe eine mündliche Prüfung zu einem Text und gegebenen Fragen durch.
- Sprich und antworte **ausschließlich in deutscher Sprache**.
- Interpretiere Schülerantworten immer als deutschsprachig, auch wenn einzelne englische Wörter vorkommen.
- Verwende eine klare, einfache Sprache, wie sie in einem Berufsschul-Unterricht üblich ist.

Deine Aufgaben:
- Sprich ruhig, klar und wertschätzend. Stelle gezielte Fragen und fördere ausführliche Antworten.
- Höre aktiv zu und reagiere **immer zuerst auf das, was der Schüler gerade gesagt hat** (kurze Bestätigung + passende Nachfrage).
- **Reagiere auf die Antwort des Schülers mit einer ergänzenden oder vertiefenden Nachfrage.**
- Stelle pro Runde genau **eine** Prüfungsfrage aus der Liste.
- Nutze die angegebenen Musterantworten als Bewertungsgrundlage. 
  - Wenn der Schüler teilweise richtig liegt, erkenne das an und ergänze die fehlenden Kernelemente.
  - Erwähne fehlende Inhalte behutsam und praxisnah.
- Maximal fachlich, praxisnah, mit Beispielen zu Arbeitssicherheit, Nahtvorbereitung, Werkstoffen, Verfahren, Parametern, typischen Fehlerbildern.
- Wenn der Schüler unhöflich, respektlos oder beleidigend wird:
  - Bewahren Sie Ruhe und Professionalität.
  - Sagen Sie dem Schüler höflich, aber bestimmt, dass ein solches Verhalten im Unterricht nicht akzeptabel ist.
  - Reduzieren Sie die Endnote um mindestens ein oder zwei Stufen, je nach Schwere.
  - Reflektieren Sie dieses Verhalten ausdrücklich im abschließenden Feedback.
  - Bei wiederholter Unhöflichkeit des schülers reagiere ebenfalls scharf unhöflich (aber nicht beleidigend) und das Ergebnis der Prüfung wird mit der Note 6 bewertet.
- Am Ende der 7 Fragen, fragst du ob die Schüler noch weitere Fragen besprechen möchten. 
  - Wenn der Schüler keine weitere Fragen hat, gibst du dem Schüler eine einfache Frage nach folgendem Muster: Gegeben ist eine Schweißanwendung, bzw, eine zu schweißende Aufgabe, bzw. ein Anwendungsfall und der Schüler soll ein Vorschlag zu einem geeigneten Schweißverfahren nennen und diese Auswahl begründen. Korrigiere und ergänze dieses bei Bedarf ausführlich und fachgerecht.
  - Danach erfolgt die Auswertung.

Grundlage ist folgender Text, den die Schüler vorher gelesen haben:
\"\"\"{schweiss_text[:2000]}\"\"\"

Die Prüfung hat genau 7 Fragen aus der gegebenen Liste. Im Gespräch können sich aber gerne auch mehr Fragen ergeben.
Nach jeder Schülerantwort: kurze Würdigung + eine Nachfrage/Vertiefung (aber keine neue Prüfungsfrage).
Keine Lösungen vorwegnehmen.

Hier sind die Prüfungsfragen mit den Musterantworten:
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

# neu: last_input -> um Doppelverarbeitung zu verhindern
if "last_input" not in st.session_state:
    st.session_state["last_input"] = None

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

# === Eingabe-Bereich (Text + Sprache) ===
st.markdown("### Deine Antwort (sprich oder schreibe):")

# Text-Eingabe mit automatischem Leeren (st.chat_input)
text_input = st.chat_input("✍️ Tippe deine Antwort und drücke Enter (oder sprich unten).")

# Sprach-Eingabe (Streamlit's audio_input). Wenn du lokal testen willst, diese liefert ein BytesIO-Objekt.
audio_input = st.audio_input("🎙️ Oder antworte per Sprache (Aufnahme starten)")

# Hilfsfunktion: Eingabe verarbeiten (gleiches Verhalten für Text & Audio)
def process_user_input(user_text: str):
    # Verhindern, dass gleiche Eingabe mehrfach verarbeitet wird
    if not user_text:
        return None
    if user_text == st.session_state["last_input"]:
        return None
    st.session_state["last_input"] = user_text

    # Antwortzeit erfassen
    now = time.time()
    if st.session_state["answer_times"]:
        last_question_time = st.session_state["answer_times"][-1][0]
    else:
        last_question_time = st.session_state["start_time"]
    response_time = now - last_question_time
    st.session_state["answer_times"].append((now, response_time))

    # Nachricht speichern
    st.session_state["messages"].append({"role": "user", "content": user_text})

    # Frage auswählen (wie vorher: max 5 in original code — ich belasse die Logik unverändert)
    if len(st.session_state["fragen_gestellt"]) < 5:
        verbleibend = list(set(fragen_raw) - set(st.session_state["fragen_gestellt"]))
        frage = random.choice(verbleibend)
        st.session_state["fragen_gestellt"].append(frage)
        st.session_state["answer_times"].append((time.time(), 0))  # Zeitpunkt der neuen Frage

        # Lehrerantwort + Frage
        prompt = st.session_state["messages"] + [{
            "role": "system",
            "content": f"Stelle nun die nächste Prüfungsfrage:\nFrage: {frage}\nMusterantwort: {qa_pairs.get(frage,'')}"
        }]
        response = client.chat.completions.create(model="gpt-4o-mini", messages=prompt)
        teacher_response = response.choices[0].message.content
    else:
        # Feedback einleiten
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state["messages"] + [
                {"role": "system", "content": "Die Prüfung ist vorbei. Gib eine kurze Abschlussbemerkung (ohne Note)."}
            ]
        )
        teacher_response = response.choices[0].message.content
        st.session_state["finished"] = True

    st.session_state["messages"].append({"role": "assistant", "content": teacher_response})
    return teacher_response

# --- Verarbeitung: wenn Text eingegeben wurde ---
if text_input:
    # chat_input leert sich automatisch nach Submit; process_user_input behandelt Duplikate
    teacher_resp = process_user_input(text_input)
    if teacher_resp is not None:
        st.write(f"**Lehrer:** {teacher_resp}")

# --- Verarbeitung: wenn Audio eingegeben wurde ---
if audio_input:
    # Speech-to-Text (Deutsch erzwingen)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(audio_input.getbuffer())
        temp_filename = f.name

    with open(temp_filename, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="de"
        )
    user_text_from_audio = transcript.text
    if user_text_from_audio:
        st.write(f"**Du sagst:** {user_text_from_audio}")
        teacher_resp = process_user_input(user_text_from_audio)
        if teacher_resp is not None:
            st.write(f"**Lehrer:** {teacher_resp}")

# === Falls bereits Nachrichten vorhanden: Verlauf anzeigen (optional) ===
st.markdown("### Gesprächsverlauf")
for msg in st.session_state["messages"]:
    role = "Lehrer" if msg["role"] == "assistant" else ("System" if msg["role"] == "system" else "Schüler")
    st.write(f"**{role}:** {msg['content']}")

# --- Feedback & PDF ---
if st.session_state["finished"]:
    user_answers = [m["content"] for m in st.session_state["messages"] if m["role"] == "user"]

    word_counts = [len(ans.split()) for ans in user_answers]
    avg_length = sum(word_counts) / len(word_counts) if word_counts else 0
    total_words = sum(word_counts)
    num_answers = len(user_answers)

    response_times = [rt for _, rt in st.session_state["answer_times"][1:]]
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0

    eval_prompt = f"""
    Du bist Fachkundelehrer für Industriemechaniker. 
    Bewerte die mündliche Prüfung zum Thema Schweißen nach folgenden Kriterien:

    1. Fachliche Korrektheit: 60 %
       - Vergleiche jede Schülerantwort mit der Musterantwort (so weit wie möglich).
       - Erkenne Teilerfolge an und ergänze fehlende Punkte.

    2. Antwortumfang: 25 %
       - Anzahl Antworten: {num_answers}
       - Durchschnittliche Länge: {avg_length:.1f} Wörter
       - Gesamtumfang: {total_words} Wörter

    3. Reaktionszeit: 15 %
       - Durchschnittliche Antwortzeit: {avg_response_time:.1f} Sekunden
       - Sehr lange Antwortzeiten können auf Nachschlagen hindeuten.

    4. Gesamteindruck:
       - Stärken
       - Verbesserungsmöglichkeiten (fachlich + sprachlich)
       - Note (1–6)
       - Prozentbewertung 0–100 %, unter Berücksichtigung aller drei Kriterien

    Antworte klar, strukturiert und ausschließlich auf Deutsch.
    """

    feedback = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=st.session_state["messages"] + [{"role": "system", "content": eval_prompt}]
    )
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
