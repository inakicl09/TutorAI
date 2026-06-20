"""Streamlit UI for TutorAI. Three account types:

- Students log in, link to teachers (by search or join code), create
  chats for the grade+subject combos a teacher has unlocked for them,
  and chat with the Socratic tutor.
- Teachers log in, declare which grade+subject combos they teach, see
  their join code, and look at their linked students' chats.
- The single Admin account (see create_admin.py) can see every user.

Run this in iTerm with: streamlit run app.py
"""

import os
import urllib.error

import streamlit as st

import chat
import chat_storage
import config
import db
import prompts
import rag
import subjects
import translations
import users

db.init_db()

st.set_page_config(page_title="TutorAI", page_icon="📚")

if "username" not in st.session_state:
    st.session_state.username = None
if "chats_loaded" not in st.session_state:
    st.session_state.chats_loaded = False

with st.sidebar:
    language = st.selectbox(
        "Idioma / Language",
        options=list(translations.TEXT.keys()),
        format_func=lambda code: "Español" if code == "es" else "English",
    )
    text = translations.TEXT[language]

if st.session_state.username is None:
    st.title(text["app_title"])

    auth_mode = st.radio(
        text["app_title"],
        [text["login_tab"], text["signup_tab"]],
        horizontal=True,
        label_visibility="collapsed",
    )
    username_input = st.text_input(text["username_label"])
    password_input = st.text_input(text["password_label"], type="password")

    if auth_mode == text["login_tab"]:
        if st.button(text["login_button"]):
            if users.verify_login(username_input, password_input):
                st.session_state.username = username_input
                st.rerun()
            else:
                st.error(text["login_failed_error"])
    else:
        role_choice = st.radio(
            text["role_label"], [text["role_student"], text["role_teacher"]]
        )
        signup_grade = None
        if role_choice == text["role_student"]:
            signup_grade = st.selectbox(text["grade_label"], options=subjects.GRADES)

        if st.button(text["signup_button"]):
            if not username_input or not password_input:
                st.error(text["signup_missing_fields_error"])
            elif users.username_exists(username_input):
                st.error(text["signup_username_taken_error"])
            elif role_choice == text["role_student"]:
                users.create_student(username_input, password_input, signup_grade)
                st.session_state.username = username_input
                st.rerun()
            else:
                users.create_teacher(username_input, password_input)
                st.session_state.username = username_input
                st.rerun()

    st.stop()

current_user = users.get_user(st.session_state.username)
role = current_user["role"]

with st.sidebar:
    st.write(f"{text['logged_in_as']} **{st.session_state.username}** ({text[f'role_{role}']})")
    if st.button(text["logout_button"]):
        st.session_state.username = None
        st.session_state.chats_loaded = False
        st.rerun()

st.title(config.ASSISTANT_NAMES[role])

if role == "admin":
    st.subheader(text["admin_dashboard_header"])
    st.header(text["all_users_header"])
    for user in users.list_all_users():
        role_label = text[f"role_{user['role']}"]
        st.write(f"- **{user['username']}** — {role_label}")

elif role == "teacher":
    st.subheader(text["teacher_dashboard_header"])
    st.write(f"{text['join_code_label']}: `{current_user['join_code']}`")

    st.header(text["add_teaching_header"])
    add_grade = st.selectbox(text["grade_label"], options=subjects.GRADES, key="add_teaching_grade")
    add_subject = st.selectbox(
        text["subject_label"],
        options=subjects.GRADE_SUBJECTS[add_grade],
        key="add_teaching_subject",
    )
    if st.button(text["add_teaching_button"]):
        users.add_teaching_assignment(st.session_state.username, add_grade, add_subject)
        st.rerun()

    st.header(text["your_subjects_header"])
    if not current_user["teaching"]:
        st.caption(text["no_teaching_message"])
    else:
        for assignment in current_user["teaching"]:
            st.write(f"- {assignment['subject']} ({assignment['grade']})")

    st.header(text["your_students_header"])
    linked_students = users.students_linked_to_teacher(st.session_state.username)
    if not linked_students:
        st.caption(text["no_students_message"])
    else:
        for student_username in linked_students:
            student_record = users.get_user(student_username)
            relevant_links = [
                link
                for link in student_record["subject_links"]
                if link["teacher"] == st.session_state.username
            ]
            student_chats = chat_storage.load_chats(student_username)
            relevant_chats = [
                c
                for c in student_chats
                if any(
                    c["grade"] == link["grade"] and c["subject"] == link["subject"]
                    for link in relevant_links
                )
            ]
            non_system_messages = [
                m for c in relevant_chats for m in c["history"] if m["role"] != "system"
            ]
            message_count = len(non_system_messages)
            timestamps = [m["created_at"] for m in non_system_messages if m.get("created_at")]
            last_active = max(timestamps) if timestamps else text["no_activity_yet"]

            expander_label = (
                f"{student_username} — {text['messages_count_label']}: {message_count} · "
                f"{text['last_active_label']}: {last_active}"
            )
            with st.expander(expander_label):
                for link in relevant_links:
                    st.write(f"**{link['subject']} ({link['grade']})**")
                    matching_chats = [
                        c
                        for c in relevant_chats
                        if c["grade"] == link["grade"] and c["subject"] == link["subject"]
                    ]
                    if not matching_chats:
                        st.caption(text["no_chats_message"])
                    for student_chat in matching_chats:
                        st.caption(f"Chat #{student_chat['id']}")
                        for message in student_chat["history"]:
                            if message["role"] == "system":
                                continue
                            with st.chat_message(message["role"]):
                                st.write(message["content"])
                                if message.get("created_at"):
                                    st.caption(message["created_at"])

    st.header(text["tests_header"])
    st.info(text["tests_coming_soon"])

else:  # role == "student"
    if not st.session_state.chats_loaded:
        st.session_state.chats = chat_storage.load_chats(st.session_state.username)
        st.session_state.active_chat_id = None
        st.session_state.chats_loaded = True

    with st.sidebar:
        st.header(text["link_teacher_header"])
        link_method = st.radio(
            text["link_method_label"],
            [text["link_method_search"], text["link_method_code"]],
            horizontal=True,
        )

        if link_method == text["link_method_search"]:
            search_text = st.text_input(text["search_teacher_label"], key="search_text")

            # find_teachers already returns alphabetical order, and since
            # Streamlit reruns the script on every text_input change, this
            # list re-filters itself as the student types.
            matching_teachers = users.find_teachers(search_text)

            if not matching_teachers:
                st.caption(text["no_teachers_found"])
            else:
                for teacher_username in matching_teachers:
                    teacher_record = users.get_user(teacher_username)
                    with st.expander(teacher_username):
                        if not teacher_record["teaching"]:
                            st.caption(text["no_teaching_message"])
                            continue

                        teaching_labels = [
                            f"{a['subject']} ({a['grade']})"
                            for a in teacher_record["teaching"]
                        ]
                        chosen_label = st.selectbox(
                            text["select_teacher_label"],
                            options=teaching_labels,
                            key=f"search_pick_{teacher_username}",
                        )
                        chosen_assignment = teacher_record["teaching"][
                            teaching_labels.index(chosen_label)
                        ]
                        if st.button(text["link_button"], key=f"link_search_{teacher_username}"):
                            users.link_student_to_teacher(
                                st.session_state.username,
                                teacher_username,
                                chosen_assignment["grade"],
                                chosen_assignment["subject"],
                            )
                            st.success(text["link_success"])
                            st.rerun()
        else:
            join_code_input = st.text_input(text["join_code_input_label"], key="join_code_input")
            if join_code_input:
                found_teacher = users.find_teacher_by_join_code(join_code_input.strip().upper())
                if found_teacher is None:
                    st.error(text["join_code_invalid_error"])
                else:
                    teacher_record = users.get_user(found_teacher)
                    teaching_options = [
                        f"{t['subject']} ({t['grade']})" for t in teacher_record["teaching"]
                    ]
                    if not teaching_options:
                        st.caption(text["no_teachers_found"])
                    else:
                        chosen_label = st.selectbox(
                            text["select_teacher_label"], options=teaching_options, key="code_pick"
                        )
                        chosen_assignment = teacher_record["teaching"][
                            teaching_options.index(chosen_label)
                        ]
                        if st.button(text["link_button"], key="link_code_button"):
                            users.link_student_to_teacher(
                                st.session_state.username,
                                found_teacher,
                                chosen_assignment["grade"],
                                chosen_assignment["subject"],
                            )
                            st.success(text["link_success"])
                            st.rerun()

        st.header(text["new_chat_header"])
        subject_links = current_user["subject_links"]
        if not subject_links:
            st.caption(text["no_links_message"])
        else:
            link_labels = [f"{link['subject']} ({link['grade']})" for link in subject_links]
            unique_labels = list(dict.fromkeys(link_labels))
            chosen_link_label = st.selectbox(
                text["subject_label"], options=unique_labels, key="new_chat_link"
            )
            chosen_link = subject_links[link_labels.index(chosen_link_label)]

            if st.button(text["create_chat_button"]):
                system_prompt = prompts.build_system_prompt(
                    chosen_link["grade"], chosen_link["subject"], language
                )
                new_chat = chat_storage.create_chat(
                    st.session_state.username,
                    chosen_link["grade"],
                    chosen_link["subject"],
                    system_prompt,
                )
                st.session_state.chats.append(new_chat)
                st.session_state.active_chat_id = new_chat["id"]

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
            chosen_chat_label = st.radio(
                text["chats_header"],
                chat_labels,
                index=current_index,
                label_visibility="collapsed",
            )
            st.session_state.active_chat_id = chat_ids[chat_labels.index(chosen_chat_label)]

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

            chat_storage.add_message(active_chat["id"], "user", student_message)
            chat_storage.add_message(active_chat["id"], "assistant", tutor_reply)
