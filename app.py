"""Streamlit UI for TutorAI: lets students upload PDFs of their course
material and chat with the Socratic tutor.

Run this in iTerm with: streamlit run app.py
"""

import os
import urllib.error

import streamlit as st

import chat
import config
import prompts
import rag

st.set_page_config(page_title="TutorAI", page_icon="📚")
st.title("TutorAI: tu tutor socrático")

if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = [
        {"role": "system", "content": prompts.SYSTEM_PROMPT}
    ]

with st.sidebar:
    st.header("Conexión con Ollama")

    try:
        available_models = chat.get_available_models()
    except urllib.error.URLError:
        st.error(
            "No se pudo conectar con Ollama. Ejecuta 'ollama serve' en una "
            "terminal y vuelve a cargar esta página."
        )
        st.stop()

    default_index = (
        available_models.index(config.CHAT_MODEL_NAME)
        if config.CHAT_MODEL_NAME in available_models
        else 0
    )
    selected_model = st.selectbox(
        "Elige el modelo de chat", available_models, index=default_index
    )

    st.header("Material de la asignatura")
    uploaded_pdf = st.file_uploader("Sube un PDF", type="pdf")

    if uploaded_pdf is not None and st.button("Añadir material"):
        os.makedirs(config.DOCUMENTS_DIR, exist_ok=True)
        pdf_path = os.path.join(config.DOCUMENTS_DIR, uploaded_pdf.name)

        with open(pdf_path, "wb") as pdf_file:
            pdf_file.write(uploaded_pdf.getbuffer())

        with st.spinner("Procesando PDF..."):
            num_chunks_added = rag.add_pdf_to_vector_store(pdf_path)

        st.success(f"Se añadieron {num_chunks_added} fragmentos a la base de conocimiento.")

for message in st.session_state.conversation_history:
    if message["role"] == "system":
        continue
    with st.chat_message(message["role"]):
        st.write(message["content"])

student_message = st.chat_input("Escribe tu pregunta...")

if student_message:
    with st.chat_message("user"):
        st.write(student_message)

    try:
        with st.spinner("Pensando..."):
            tutor_reply = chat.ask_tutor(
                st.session_state.conversation_history, student_message, selected_model
            )
    except urllib.error.URLError:
        st.error("Se perdió la conexión con Ollama. Comprueba que sigue en marcha.")
        st.stop()

    with st.chat_message("assistant"):
        st.write(tutor_reply)
