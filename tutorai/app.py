"""Streamlit UI for TutorAI. Three account types:

- Students log in, link to teachers (by search or join code), create
  chats for the grade+subject combos a teacher has unlocked for them,
  and chat with the Socratic tutor.
- Teachers log in, declare which grade+subject combos they teach, look
  at their linked students' chats, and draft/save tests by chatting with
  Logos (no RAG -- Logos doesn't search course documents).
- The single Admin account (see create_admin.py) can see every user.

Run this in iTerm with: python3 -m streamlit run tutorai/app.py
"""

import os
import urllib.error

import streamlit as st

from tutorai import (
    chat,
    chat_storage,
    classes,
    config,
    db,
    exams,
    homerooms,
    prompts,
    rag,
    subjects,
    translations,
    users,
)

db.init_db()
classes.sync_with_teaching_assignments()
homerooms.backfill_homerooms()

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


def render_change_password_and_delete(username: str, text: dict) -> None:
    """Shared password-change and delete-with-confirm controls for any
    user, used by both the Teachers and Students admin menus."""
    new_user_password = st.text_input(
        text["new_password_label"], type="password", key=f"newpw_{username}"
    )
    if st.button(text["change_password_button"], key=f"changepw_{username}"):
        if new_user_password:
            users.set_password(username, new_user_password)
            st.success(text["password_changed_message"])
        else:
            st.error(text["signup_missing_fields_error"])

    if username == st.session_state.username:
        st.caption(text["cannot_delete_self_message"])
        return

    pending_delete_key = f"confirm_delete_{username}"
    if st.session_state.get(pending_delete_key):
        st.warning(text["confirm_delete_message"].format(username=username))
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button(text["confirm_delete_button"], key=f"confirm_{username}"):
                users.delete_user(username)
                st.session_state[pending_delete_key] = False
                st.success(text["user_deleted_message"])
                st.rerun()
        with cancel_col:
            if st.button(text["cancel_button"], key=f"cancel_{username}"):
                st.session_state[pending_delete_key] = False
                st.rerun()
    else:
        if st.button(text["delete_user_button"], key=f"delete_{username}"):
            st.session_state[pending_delete_key] = True
            st.rerun()


if role == "admin":
    st.subheader(text["admin_dashboard_header"])

    st.header(text["add_user_header"])
    new_username = st.text_input(text["username_label"], key="admin_new_username")
    new_password = st.text_input(
        text["password_label"], type="password", key="admin_new_password"
    )
    new_role = st.radio(
        text["role_label"],
        [text["role_student"], text["role_teacher"]],
        key="admin_new_role",
    )
    new_grade = None
    if new_role == text["role_student"]:
        new_grade = st.selectbox(text["grade_label"], options=subjects.GRADES, key="admin_new_grade")

    if st.button(text["add_user_button"]):
        if not new_username or not new_password:
            st.error(text["signup_missing_fields_error"])
        elif users.username_exists(new_username):
            st.error(text["signup_username_taken_error"])
        elif new_role == text["role_student"]:
            users.create_student(new_username, new_password, new_grade)
            st.success(text["add_user_success"])
            st.rerun()
        else:
            join_code = users.create_teacher(new_username, new_password)
            st.success(f"{text['add_user_success']} {text['join_code_label']}: {join_code}")
            st.rerun()

    st.header(text["admin_teachers_menu_header"])
    teacher_grade_filter = st.selectbox(
        text["filter_by_grade_label"],
        options=[text["all_grades_option"]] + subjects.GRADES,
        key="teacher_filter_grade",
    )
    teacher_search_text = st.text_input(text["search_teacher_label"], key="teacher_filter_search")

    matching_teacher_usernames = {
        u["username"] for u in users.list_all_users(teacher_search_text, role="teacher")
    }
    if teacher_grade_filter != text["all_grades_option"]:
        matching_teacher_usernames &= {
            class_record["teacher_username"]
            for class_record in classes.list_classes(grade=teacher_grade_filter)
        }

    if not matching_teacher_usernames:
        st.caption(text["no_matching_users_message"])
    else:
        for teacher_username in sorted(matching_teacher_usernames):
            teacher_record = users.get_user(teacher_username)
            with st.expander(teacher_username):
                teacher_password = users.get_plaintext_password(teacher_username)
                if teacher_password is not None:
                    st.write(f"{text['password_label_admin_view']}: `{teacher_password}`")
                else:
                    st.caption(text["password_not_available_message"])

                st.write(f"{text['join_code_label']}: `{teacher_record['join_code']}`")
                if st.button(text["regenerate_join_code_button"], key=f"regen_{teacher_username}"):
                    new_code = users.regenerate_join_code(teacher_username)
                    st.success(f"{text['join_code_label']}: {new_code}")
                    st.rerun()

                st.write(f"**{text['teaching_list_label']}**")
                if not teacher_record["teaching"]:
                    st.caption(text["no_teaching_message"])
                else:
                    for assignment in teacher_record["teaching"]:
                        class_record = classes.get_or_create_class(
                            teacher_username, assignment["grade"], assignment["subject"]
                        )
                        student_count = len(classes.students_in_class(class_record["id"]))
                        st.write(
                            f"- {assignment['subject']} ({assignment['grade']}) "
                            f"— {student_count} {text['admin_students_menu_header'].lower()}"
                        )

                render_change_password_and_delete(teacher_username, text)

    st.header(text["admin_students_menu_header"])
    student_grade_filter = st.selectbox(
        text["filter_by_grade_label"],
        options=[text["all_grades_option"]] + subjects.GRADES,
        key="student_filter_grade",
    )
    classes_for_filter = classes.list_classes(
        grade=None if student_grade_filter == text["all_grades_option"] else student_grade_filter
    )
    class_filter_choice = st.selectbox(
        text["filter_by_class_label"],
        options=[text["all_classes_option"]] + [c["name"] for c in classes_for_filter],
        key="student_filter_class",
    )
    student_search_text = st.text_input(text["search_teacher_label"], key="student_filter_search")

    matching_student_usernames = {
        u["username"] for u in users.list_all_users(student_search_text, role="student")
    }
    if student_grade_filter != text["all_grades_option"]:
        matching_student_usernames = {
            username
            for username in matching_student_usernames
            if users.get_user(username)["grade"] == student_grade_filter
        }
    if class_filter_choice != text["all_classes_option"]:
        chosen_class = next(c for c in classes_for_filter if c["name"] == class_filter_choice)
        matching_student_usernames &= set(classes.students_in_class(chosen_class["id"]))

    if not matching_student_usernames:
        st.caption(text["no_matching_users_message"])
    else:
        for student_username in sorted(matching_student_usernames):
            student_record = users.get_user(student_username)
            with st.expander(student_username):
                student_password = users.get_plaintext_password(student_username)
                if student_password is not None:
                    st.write(f"{text['password_label_admin_view']}: `{student_password}`")
                else:
                    st.caption(text["password_not_available_message"])

                st.write(f"{text['grade_label']}: {student_record['grade']}")
                st.write(f"{text['homeroom_label']}: {student_record['homeroom_name'] or '—'}")

                st.write(f"**{text['links_list_label']}**")
                if not student_record["subject_links"]:
                    st.caption(text["no_links_message"])
                else:
                    for link in student_record["subject_links"]:
                        link_col, remove_col = st.columns([4, 1])
                        with link_col:
                            st.write(f"- {link['subject']} ({link['grade']}) — {link['teacher']}")
                        with remove_col:
                            remove_key = (
                                f"unlink_{student_username}_{link['teacher']}_"
                                f"{link['grade']}_{link['subject']}"
                            )
                            if st.button(text["remove_link_button"], key=remove_key):
                                users.unlink_student_from_teacher(
                                    student_username,
                                    link["teacher"],
                                    link["grade"],
                                    link["subject"],
                                )
                                st.success(text["link_removed_message"])
                                st.rerun()

                st.write(f"**{text['add_link_header']}**")
                all_teacher_usernames = [u["username"] for u in users.list_all_users(role="teacher")]
                if not all_teacher_usernames:
                    st.caption(text["no_teachers_found"])
                else:
                    chosen_teacher = st.selectbox(
                        text["select_teacher_label"],
                        options=all_teacher_usernames,
                        key=f"admin_link_teacher_{student_username}",
                    )
                    teacher_teaching = users.get_user(chosen_teacher)["teaching"]
                    if not teacher_teaching:
                        st.caption(text["no_teaching_message"])
                    else:
                        teaching_labels = [
                            f"{a['subject']} ({a['grade']})" for a in teacher_teaching
                        ]
                        chosen_label = st.selectbox(
                            text["subject_label"],
                            options=teaching_labels,
                            key=f"admin_link_subject_{student_username}",
                        )
                        chosen_assignment = teacher_teaching[teaching_labels.index(chosen_label)]
                        if st.button(
                            text["link_button"], key=f"admin_link_button_{student_username}"
                        ):
                            try:
                                users.link_student_to_teacher(
                                    student_username,
                                    chosen_teacher,
                                    chosen_assignment["grade"],
                                    chosen_assignment["subject"],
                                )
                                st.success(text["link_success"])
                                st.rerun()
                            except ValueError:
                                st.error(text["link_failed_error"])

                render_change_password_and_delete(student_username, text)

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

    if "test_chats_loaded" not in st.session_state:
        st.session_state.test_chats_loaded = False
    if not st.session_state.test_chats_loaded:
        st.session_state.test_chats = chat_storage.load_chats(st.session_state.username)
        st.session_state.active_test_chat_id = None
        st.session_state.test_chats_loaded = True

    try:
        logos_available_models = chat.get_available_models()
    except urllib.error.URLError:
        if chat.is_ollama_installed():
            st.error(text["ollama_unreachable"])
        else:
            st.error(text["ollama_not_installed"])
        logos_available_models = None

    if logos_available_models:
        logos_default_index = (
            logos_available_models.index(config.CHAT_MODEL_NAME)
            if config.CHAT_MODEL_NAME in logos_available_models
            else 0
        )
        logos_selected_model = st.selectbox(
            text["model_label"], logos_available_models, index=logos_default_index, key="logos_model"
        )

        st.subheader(text["logos_new_test_chat_header"])
        if not current_user["teaching"]:
            st.caption(text["no_teaching_message"])
        else:
            logos_teaching_labels = [
                f"{a['subject']} ({a['grade']})" for a in current_user["teaching"]
            ]
            logos_chosen_label = st.selectbox(
                text["subject_label"], options=logos_teaching_labels, key="logos_new_chat_subject"
            )
            logos_chosen_assignment = current_user["teaching"][
                logos_teaching_labels.index(logos_chosen_label)
            ]

            if st.button(text["create_chat_button"], key="logos_create_chat"):
                logos_system_prompt = prompts.build_logos_system_prompt(
                    logos_chosen_assignment["grade"], logos_chosen_assignment["subject"], language
                )
                new_test_chat = chat_storage.create_chat(
                    st.session_state.username,
                    logos_chosen_assignment["grade"],
                    logos_chosen_assignment["subject"],
                    logos_system_prompt,
                )
                st.session_state.test_chats.append(new_test_chat)
                st.session_state.active_test_chat_id = new_test_chat["id"]

        st.subheader(text["chats_header"])
        if not st.session_state.test_chats:
            st.caption(text["no_chats_message"])
        else:
            logos_chat_labels = [
                f"{c['subject']} ({c['grade']})" for c in st.session_state.test_chats
            ]
            logos_chat_ids = [c["id"] for c in st.session_state.test_chats]
            logos_current_index = (
                logos_chat_ids.index(st.session_state.active_test_chat_id)
                if st.session_state.active_test_chat_id in logos_chat_ids
                else 0
            )
            logos_chosen_chat_label = st.radio(
                text["chats_header"],
                logos_chat_labels,
                index=logos_current_index,
                key="logos_chat_picker",
                label_visibility="collapsed",
            )
            st.session_state.active_test_chat_id = logos_chat_ids[
                logos_chat_labels.index(logos_chosen_chat_label)
            ]

        active_test_chat = next(
            (c for c in st.session_state.test_chats if c["id"] == st.session_state.active_test_chat_id),
            None,
        )

        if active_test_chat is None:
            st.info(text["no_chats_message"])
        else:
            st.write(f"**{active_test_chat['subject']} ({active_test_chat['grade']})**")

            for message in active_test_chat["history"]:
                if message["role"] == "system":
                    continue
                with st.chat_message(message["role"]):
                    st.write(message["content"])

            teacher_message = st.chat_input(text["chat_placeholder"], key="logos_chat_input")

            if teacher_message:
                with st.chat_message("user"):
                    st.write(teacher_message)

                try:
                    with st.spinner(text["thinking_spinner"]):
                        logos_reply = chat.ask_logos(
                            active_test_chat["history"], teacher_message, logos_selected_model
                        )
                except urllib.error.URLError:
                    st.error(text["ollama_disconnected"])
                    st.stop()

                with st.chat_message("assistant"):
                    st.write(logos_reply)

                chat_storage.add_message(active_test_chat["id"], "user", teacher_message)
                chat_storage.add_message(active_test_chat["id"], "assistant", logos_reply)

            last_logos_messages = [
                m for m in active_test_chat["history"] if m["role"] == "assistant"
            ]
            if last_logos_messages:
                st.write(f"**{text['save_test_header']}**")
                test_title = st.text_input(
                    text["test_title_label"], key=f"test_title_{active_test_chat['id']}"
                )
                if st.button(text["save_test_button"], key=f"save_test_{active_test_chat['id']}"):
                    if not test_title:
                        st.error(text["signup_missing_fields_error"])
                    else:
                        exams.save_test(
                            st.session_state.username,
                            active_test_chat["grade"],
                            active_test_chat["subject"],
                            test_title,
                            last_logos_messages[-1]["content"],
                        )
                        st.success(text["test_saved_message"])

    st.subheader(text["your_tests_header"])
    saved_tests = exams.list_tests_for_teacher(st.session_state.username)
    if not saved_tests:
        st.caption(text["no_tests_message"])
    else:
        for saved_test in saved_tests:
            with st.expander(f"{saved_test['title']} — {saved_test['subject']} ({saved_test['grade']})"):
                st.write(saved_test["content"])
                if st.button(text["delete_test_button"], key=f"delete_test_{saved_test['id']}"):
                    exams.delete_test(saved_test["id"], st.session_state.username)
                    st.rerun()

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
            if chat.is_ollama_installed():
                st.error(text["ollama_unreachable"])
            else:
                st.error(text["ollama_not_installed"])
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
