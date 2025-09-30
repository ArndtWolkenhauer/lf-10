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

# --- Streamlit UI ---
st.title("🛠️ Fachkundeprüfung Schweißen – Simulation")

# --- Session State ---
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

# --- Timer ---
elapsed = time.time() - st.session_state["start_time"]
remaining = max(0, 300 - int(elapsed))
st.info(f"⏱ Verbleibende Zeit: {remaining//60:02d}:{remaining%60:02d}")

# --- Gesprächsverlauf anzeigen ---
for msg in st.session_state["messages"]:
    if msg["role"] == "system":
        continue
    role = "👨‍🎓 Schüler" if msg["role"] == "user" else "👨‍🏫 Lehrer"
    with st.chat_message(role):
        st.markdown(msg["content"])

# --- Eingabe unten ---
col1, col2 = st.columns([2,1])
with col1:
    text_input = st.chat_input("✍️ Tippe deine Antwort und drücke Enter")
with col2:
    audio_input = st.audio_input("🎙️ Sprich deine Antwort")

# --- Eingaben verarbeiten ---
def process_user_input(user_text: str):
    if not user_text or user_text == st.session_state["last_input"]:
        return None
    st.session_state["last_input"] = user_text

    now = time.time()
    if st.session_state["answer_times"]:
        last_q_time = st.session_state["answer_times"][-1][0]
    else:
        last_q_time = st.session_state["start_time"]
    response_time = now - last_q_time
    st.session_state["answer_times"].append((now, response_time))

    st.session_state["messages"].append({"role": "user", "content": user_text})

    if len(st.session_state["fragen_gestellt"]) < 7:
        verbleibend = list(set(fragen_raw) - set(st.session_state["fragen_gestellt"]))
        frage = random.choice(verbleibend)
        st.session_state["fragen_gestellt"].append(frage)
        st.session_state["answer_times"].append((time.time(), 0))

        prompt = st.session_state["messages"] + [{
            "role": "system",
            "content": f"Stelle nun die nächste Prüfungsfrage:\nFrage: {frage}\nMusterantwort: {qa_pairs.get(frage,'')}"
        }]
        response = client.chat.completions.create(model="gpt-4o-mini", messages=prompt)
        teacher_resp = response.choices[0].message.content
    else:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=st.session_state["messages"] + [
                {"role": "system", "content": "Die Prüfung ist vorbei. Gib eine kurze Abschlussbemerkung (ohne Note)."}
            ]
        )
        teacher_resp = response.choices[0].message.content
        st.session_state["finished"] = True

    st.session_state["messages"].append({"role": "assistant", "content": teacher_resp})
    return teacher_resp

# --- Text ---
if text_input:
    teacher_resp = process_user_input(text_input)
    if teacher_resp:
        with st.chat_message("👨‍🏫 Lehrer"):
            st.markdown(teacher_resp)

# --- Audio ---
if audio_input:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(audio_input.getbuffer())
        temp_filename = f.name
    with open(temp_filename, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="de"
        )
    spoken_text = transcript.text
    if spoken_text:
        st.session_state["messages"].append({"role": "user", "content": spoken_text})
        teacher_resp = process_user_input(spoken_text)
        if teacher_resp:
            with st.chat_message("👨‍🏫 Lehrer"):
                st.markdown(teacher_resp)
