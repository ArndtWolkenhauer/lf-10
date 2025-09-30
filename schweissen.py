# --- Funktion: Benutzerantwort verarbeiten ---
def process_user_input(user_text: str):
    if not user_text or user_text == st.session_state["last_input"]:
        return None
    st.session_state["last_input"] = user_text

    # --- Smalltalk erkennen ---
    smalltalk_keywords = ["hallo", "hi", "guten morgen", "servus", "ja gerne", "okay", "klar"]
    if any(g in user_text.lower() for g in smalltalk_keywords):
        teacher_response = "Alles klar, lass uns mit der Prüfung fortfahren."
        st.session_state["messages"].append({"role": "assistant", "content": teacher_response})

        # erste Frage stellen, falls noch nicht geschehen
        if not st.session_state["first_question_given"]:
            verbleibend = [q for q in fragen_raw if q not in st.session_state["fragen_gestellt"]]
            if verbleibend:
                frage = random.choice(verbleibend)
                st.session_state["fragen_gestellt"].append(frage)
                st.session_state["first_question_given"] = True
                st.session_state["messages"].append({"role": "assistant", "content": f"Erste Prüfungsfrage: {frage}"})
        return teacher_response

    # --- Prüfen: gibt es eine offene Frage? ---
    offene_fragen = [f for f in st.session_state["fragen_gestellt"] if
                     f not in [m["content"] for m in st.session_state["messages"] if m["role"]=="user"]]
    if not offene_fragen:
        # Keine Frage gestellt oder alle beantwortet → warten
        return None

    # Schülerantwort speichern
    st.session_state["messages"].append({"role": "user", "content": user_text})

    # --- Prüfen, ob die Antwort fachlich relevant ist ---
    # Beispiel-Stichworte für fachliche Antworten
    fachliche_stichworte = ["schweißen", "punkt", "lichtbogen", "naht", "material", "werkstoff", "verbindung", "verfahren"]
    ist_fachlich = any(word.lower() in user_text.lower() for word in fachliche_stichworte)

    if not ist_fachlich:
        # Nur Bestätigung/Smalltalk → kurze Reaktion
        teacher_response = "Danke für deine Rückmeldung. Lass uns zur Frage zurückkommen."
        st.session_state["messages"].append({"role": "assistant", "content": teacher_response})
        return teacher_response

    # --- Fachliche Rückmeldung generieren ---
    prompt = st.session_state["messages"] + [{
        "role": "system",
        "content": (
            "Du bist der Lehrer. Reagiere **wertschätzend und fachlich korrekt** auf die Schülerantwort. "
            "Stelle keine neue Frage. Musterantwort nur intern zur Bewertung."
        )
    }]
    response = client.chat.completions.create(model="gpt-4o-mini", messages=prompt)
    teacher_response = response.choices[0].message.content
    st.session_state["messages"].append({"role": "assistant", "content": teacher_response})

    # --- Neue Frage stellen, wenn noch nicht alle 7 ---
    if len(st.session_state["fragen_gestellt"]) < 7:
        verbleibend = [q for q in fragen_raw if q not in st.session_state["fragen_gestellt"]]
        if verbleibend:
            neue_frage = random.choice(verbleibend)
            st.session_state["fragen_gestellt"].append(neue_frage)
            st.session_state["messages"].append({"role": "assistant", "content": f"Neue Prüfungsfrage: {neue_frage}"})
    else:
        # Prüfung vorbei
        st.session_state["finished"] = True

    return teacher_response
