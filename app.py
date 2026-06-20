"""Streamlit UI for TutorAI: lets students create chats per grade and
subject, upload PDFs of their course material, and chat with the
Socratic tutor.

Run this in iTerm with: streamlit run app.py
"""

import os
import urllib.error

import streamlit as st

import chat
import config
import prompts
import rag
import subjects
import translations

st.set_page_config(page_title="TutorAI", page_icon="📚")

if "chats" not in st.session_state:
    st.session_state.chats = []
if "active_chat_id" not in st.session_state:
    st.session_state.active_chat_id = None
if "next_chat_id" not in st.session_state:
    st.session_state.next_chat_id = 1

with st.sidebar:
    language = st.selectbox(
        "Idioma / Language",
        options=list(translations.TEXT.keys()),
        format_func=lambda code: "Español" if code == "es" else "English",
    )
    text = translations.TEXT[language]

    st.header(text["new_chat_header"])
    grade = st.selectbox(text["grade_label"], options=subjects.GRADES)
    subject = st.selectbox(text["subject_label"], options=subjects.GRADE_SUBJECTS[grade])

    if st.button(text["create_chat_button"]):
        new_chat = {
            "id": st.session_state.next_chat_id,
            "grade": grade,
            "subject": subject,
            "history": [
                {
                    "role": "system",
                    "content": prompts.build_system_prompt(grade, subject, language),
                }
            ],
        }
        st.session_state.chats.append(new_chat)
        st.session_state.active_chat_id = new_chat["id"]
        st.session_state.next_chat_id += 1

    st.header(text["chats_header"])
    if not st.session_state.chats:
        st.caption(text["no_chats_message"])
    else:
        chat_labels = [f"{c['subject']} ({c['grade']})" for c in st.session_state.chats]
        chat_ids = [c["id"] for c in st.session_state.chats]
        current_index = (
            chat_ids.index(st.session_state.active_chat_id)
            if st.session_state.active_chat_id in chat_ids
            else 0
        )
        chosen_label = st.radio(
            text["chats_header"],
            chat_labels,
            index=current_index,
            label_visibility="collapsed",
        )
        st.session_state.active_chat_id = chat_ids[chat_labels.index(chosen_label)]

    st.header(text["connection_header"])

    try:
        available_models = chat.get_available_models()
    except urllib.error.URLError:
        st.error(text["ollama_unreachable"])
        st.stop()

    default_index = (
        available_models.index(config.CHAT_MODEL_NAME)
        if config.CHAT_MODEL_NAME in available_models
        else 0
    )
    selected_model = st.selectbox(
        text["model_label"], available_models, index=default_index
    )

    st.header(text["material_header"])
    uploaded_pdf = st.file_uploader(text["upload_label"], type="pdf")

    if uploaded_pdf is not None and st.button(text["upload_button"]):
        os.makedirs(config.DOCUMENTS_DIR, exist_ok=True)
        pdf_path = os.path.join(config.DOCUMENTS_DIR, uploaded_pdf.name)

        with open(pdf_path, "wb") as pdf_file:
            pdf_file.write(uploaded_pdf.getbuffer())

        with st.spinner(text["upload_spinner"]):
            num_chunks_added = rag.add_pdf_to_vector_store(pdf_path)

        st.success(text["upload_success"].format(num_chunks=num_chunks_added))

st.title(text["app_title"])

active_chat = next(
    (c for c in st.session_state.chats if c["id"] == st.session_state.active_chat_id),
    None,
)

if active_chat is None:
    st.info(text["no_chats_message"])
else:
    st.subheader(f"{active_chat['subject']} ({active_chat['grade']})")

    for message in active_chat["history"]:
        if message["role"] == "system":
            continue
        with st.chat_message(message["role"]):
            st.write(message["content"])

    student_message = st.chat_input(text["chat_placeholder"])

    if student_message:
        with st.chat_message("user"):
            st.write(student_message)

        try:
            with st.spinner(text["thinking_spinner"]):
                tutor_reply = chat.ask_tutor(
                    active_chat["history"], student_message, selected_model
                )
        except urllib.error.URLError:
            st.error(text["ollama_disconnected"])
            st.stop()

        with st.chat_message("assistant"):
            st.write(tutor_reply)
