"""Streamlit UI for TutorAI. Three account types, each with their own
sidebar-navigable screens (the LLM persona name is the page title, the
screen picker lives right below the login/logout controls):

- Students (Socrates): a main menu, the chat itself, linking a teacher,
  and uploading course material for RAG.
- Teachers (Logos): a main menu, supervising linked students' activity,
  managing their own classes, and drafting/saving tests with Logos (no
  RAG -- Logos doesn't search course documents).
- The single Admin account (Artemis, see create_admin.py): a main menu,
  adding users, and two filterable menus for browsing teachers/students.

Run this in iTerm with: python3 -m streamlit run tutorai/app.py
"""

import os
import time
from typing import Optional

import pandas as pd
import streamlit as st

from tutorai import (
    announcements,
    artemis_actions,
    chat,
    chat_storage,
    classes,
    config,
    db,
    exams,
    exercises,
    goals,
    homerooms,
    notes,
    prompts,
    questions,
    rag,
    sessions,
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
if "test_chats_loaded" not in st.session_state:
    st.session_state.test_chats_loaded = False
if "artemis_chat_loaded" not in st.session_state:
    st.session_state.artemis_chat_loaded = False

# Restoring a login from the URL's session token (if any) is what lets a
# restart of the Streamlit server -- which wipes st.session_state -- log
# the user back in automatically, since the token survives in the
# browser's URL and in the sessions table.
if st.session_state.username is None:
    token_from_url = st.query_params.get("session")
    if token_from_url:
        restored_username = sessions.get_username_for_token(token_from_url)
        if restored_username:
            st.session_state.username = restored_username


def log_in_as(username: str) -> None:
    """Set the logged-in user and start a persistent session for them."""
    st.session_state.username = username
    st.query_params["session"] = sessions.create_session(username)


def log_out() -> None:
    """Clear the logged-in user and end their persistent session."""
    token = st.query_params.get("session")
    if token:
        sessions.delete_session(token)
        del st.query_params["session"]
    st.session_state.username = None
    st.session_state.chats_loaded = False
    st.session_state.test_chats_loaded = False
    st.session_state.artemis_chat_loaded = False


# Sentinel grade/subject for Artemis's single chat -- admin isn't tied to
# a real grade or subject, but the chats table requires both.
ARTEMIS_GRADE = "Admin"
ARTEMIS_SUBJECT = "Artemis"

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
                log_in_as(username_input)
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
                log_in_as(username_input)
                st.rerun()
            else:
                users.create_teacher(username_input, password_input)
                log_in_as(username_input)
                st.rerun()

    # --- TEMPORARY: remove this block once the project is finished ---
    # Lets you log in as any existing user without a password, purely
    # for testing different roles quickly.
    st.divider()
    st.warning(text["dev_login_warning"])
    all_usernames = [u["username"] for u in users.list_all_users()]
    if all_usernames:
        dev_login_username = st.selectbox(
            text["dev_login_label"], options=all_usernames, key="dev_login_username"
        )
        if st.button(text["dev_login_button"], key="dev_login_button"):
            log_in_as(dev_login_username)
            st.rerun()
    # --- END TEMPORARY ---

    st.stop()

else:
    # Everything below is the logged-in app. It lives in an `else`
    # (rather than relying on st.stop() above alone) so it can never
    # run without a logged-in user -- st.stop() is a no-op when the
    # module is imported outside `streamlit run` (tests, import checks).
    current_user = users.get_user(st.session_state.username)
    role = current_user["role"]

    if "session_start_time" not in st.session_state:
        st.session_state.session_start_time = time.time()

    # Each role's sidebar screens, in nav order. The label keys are looked up
    # in translations.py so the tab names follow the chosen UI language.
    # Artemis is deliberately NOT in the admin list below -- it gets its own
    # button past a divider in the sidebar (see the nav code), separate from
    # the day-to-day management screens, since it's a different kind of
    # feature (an assistant with its own ability to act, not a CRUD screen).
    SCREENS_BY_ROLE = {
        "admin": [
            ("main_menu", "screen_main_menu"),
            ("add_user", "add_user_header"),
            ("teachers", "admin_teachers_menu_header"),
            ("students", "admin_students_menu_header"),
            ("bug_reports", "screen_bug_reports"),
        ],
        "teacher": [
            ("main_menu", "screen_main_menu"),
            ("supervise", "screen_supervise"),
            ("my_classes", "screen_my_classes"),
            ("tests", "screen_logos"),
            ("question_bank", "screen_question_bank"),
            ("announcements", "screen_announcements"),
            ("exercises", "screen_exercises"),
        ],
        "student": [
            ("main_menu", "screen_main_menu"),
            ("chat", "screen_chat"),
            ("exercises", "screen_exercises"),
            ("notes", "screen_notes"),
            ("progress", "screen_progress"),
            ("link_teacher", "screen_link_teacher"),
            ("material", "screen_material"),
            ("tests", "screen_student_tests"),
            ("flashcards", "screen_flashcards"),
        ],
    }

    with st.sidebar:
        user_col, logout_col = st.columns([3, 1])
        with user_col:
            st.write(f"**{st.session_state.username}** ({text[f'role_{role}']})")
        with logout_col:
            if st.button("↩", help=text["logout_button"], key="logout_btn"):
                log_out()
                st.rerun()

        st.divider()

        screen_ids = [screen_id for screen_id, _ in SCREENS_BY_ROLE[role]]
        screen_labels = [text[label_key] for _, label_key in SCREENS_BY_ROLE[role]]

        if role == "admin":
            # Artemis lives behind its own button, past a divider, instead of
            # being one more option in the management radio above -- it's a
            # different kind of feature (an assistant that can act on the
            # admin's behalf), not another CRUD screen. A radio widget always
            # reports its last-remembered value on every rerun, even reruns
            # the user triggered some other way (e.g. sending an Artemis chat
            # message) -- so switching away from "artemis" must only happen
            # through this radio's own on_change, never by comparing its
            # return value against the current screen on every rerun.
            if "admin_screen" not in st.session_state:
                st.session_state.admin_screen = screen_ids[0]

            def _switch_to_management_screen() -> None:
                chosen_label = st.session_state["admin_management_nav"]
                st.session_state.admin_screen = screen_ids[screen_labels.index(chosen_label)]

            default_label = (
                screen_labels[screen_ids.index(st.session_state.admin_screen)]
                if st.session_state.admin_screen in screen_ids
                else screen_labels[0]
            )
            st.radio(
                text["screen_nav_label"],
                screen_labels,
                index=screen_labels.index(default_label),
                key="admin_management_nav",
                on_change=_switch_to_management_screen,
            )

            st.divider()
            if st.button(
                f"🤖 {text['screen_artemis']}", key="artemis_nav_button", use_container_width=True
            ):
                st.session_state.admin_screen = "artemis"

            screen = st.session_state.admin_screen
        else:
            # pending_screen_id is set by quick-nav buttons BEFORE this widget is drawn,
            # so we can safely pre-select the right radio option without touching the
            # widget's key after instantiation (which Streamlit forbids).
            pending_sid = st.session_state.pop("pending_screen_id", None)
            default_screen_idx = (
                screen_ids.index(pending_sid)
                if pending_sid and pending_sid in screen_ids
                else 0
            )

            chosen_screen_label = st.radio(
                text["screen_nav_label"],
                screen_labels,
                index=default_screen_idx,
                key="screen_nav",
            )
            screen = screen_ids[screen_labels.index(chosen_screen_label)]

            if role == "student":
                elapsed_secs = int(time.time() - st.session_state.session_start_time)
                elapsed_mins = elapsed_secs // 60
                session_str = "< 1 min" if elapsed_mins == 0 else f"{elapsed_mins} min"
                st.caption(f"⏱ {text['stat_session_time']}: {session_str}")

        st.divider()
        with st.expander(text["report_bug_header"]):
            bug_desc = st.text_area(
                text["report_bug_label"], key="bug_report_input", label_visibility="collapsed"
            )
            if st.button(text["report_bug_button"], key="bug_report_submit"):
                if bug_desc.strip():
                    from datetime import datetime as _dt, timezone as _tz
                    conn = db.get_connection()
                    try:
                        conn.execute(
                            "INSERT INTO bug_reports (username, role, description, created_at) "
                            "VALUES (?, ?, ?, ?)",
                            (
                                st.session_state.username,
                                role,
                                bug_desc.strip(),
                                _dt.now(_tz.utc).isoformat(),
                            ),
                        )
                        conn.commit()
                    finally:
                        conn.close()
                    st.success(text["report_bug_success"])
                    st.rerun()
                else:
                    st.error(text["report_bug_empty_error"])

    st.title(config.ASSISTANT_NAMES[role])

    def run_proposed_artemis_action(reply: str, text: dict) -> Optional[str]:
        """If Artemis's reply proposes an action, run it immediately and
        return a result message to show/save as a follow-up chat message, or
        None if the reply didn't propose anything. Artemis's ability list is
        a strict subset of what the admin dashboard can already do (no
        admin-account creation, and execute_action separately refuses to let
        it delete the currently-logged-in admin's own account), so this never
        gives Artemis more power than a human admin already has."""
        action = artemis_actions.parse_proposed_action(reply)
        if not action:
            return None

        try:
            extra = artemis_actions.execute_action(action, st.session_state.username)
            summary = artemis_actions.describe_action(action)
            message = text["action_completed_message"].format(summary=summary)
            if extra:
                message += f" ({extra})"
            return message
        except ValueError as error:
            return text["action_failed_error"].format(error=error)


    def render_change_password_and_delete(username: str, text: dict) -> None:
        """Shared password-change and delete-with-confirm controls for any
        user, used by both the Teachers and Students admin screens."""
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


    MAX_ACTIVITY_SUMMARY_LENGTH = 6000


    def build_class_activity_summary(teacher_username: str, grade: str, subject: str) -> str:
        """Gather the linked students' chat activity for one of a teacher's
        classes, formatted as plain text for Logos's analysis-mode prompt.
        Truncated to a fixed length as a simple guard against overflowing
        the model's context window."""
        lines = []
        for student_username in users.students_linked_to_teacher(teacher_username):
            student_record = users.get_user(student_username)
            is_linked_to_this_class = any(
                link["teacher"] == teacher_username and link["grade"] == grade and link["subject"] == subject
                for link in student_record["subject_links"]
            )
            if not is_linked_to_this_class:
                continue

            matching_chats = [
                c
                for c in chat_storage.load_chats(student_username)
                if c["grade"] == grade and c["subject"] == subject
            ]
            for student_chat in matching_chats:
                for message in student_chat["history"]:
                    if message["role"] == "system":
                        continue
                    lines.append(f"{student_username} ({message['role']}): {message['content']}")

        summary = "\n".join(lines)
        return summary[:MAX_ACTIVITY_SUMMARY_LENGTH]


    if role == "admin":
        if screen == "main_menu":
            st.write(text["welcome_message"].format(username=st.session_state.username))

            all_users = users.list_all_users()
            stat_columns = st.columns(4)
            with stat_columns[0]:
                st.metric(text["stat_total_students"], sum(1 for u in all_users if u["role"] == "student"))
            with stat_columns[1]:
                st.metric(text["stat_total_teachers"], sum(1 for u in all_users if u["role"] == "teacher"))
            with stat_columns[2]:
                st.metric(text["stat_total_classes"], len(classes.list_classes()))
            with stat_columns[3]:
                st.metric(text["stat_total_homerooms"], len(homerooms.list_homerooms()))

        elif screen == "add_user":
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
                new_grade = st.selectbox(
                    text["grade_label"], options=subjects.GRADES, key="admin_new_grade"
                )

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

        elif screen == "teachers":
            st.header(text["admin_teachers_menu_header"])
            teacher_grade_filter = st.selectbox(
                text["filter_by_grade_label"],
                options=[text["all_grades_option"]] + subjects.GRADES,
                key="teacher_filter_grade",
            )
            teacher_search_text = st.text_input(
                text["search_teacher_label"], key="teacher_filter_search"
            )

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
                        if st.button(
                            text["regenerate_join_code_button"], key=f"regen_{teacher_username}"
                        ):
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

                        st.write(f"**{text['add_teaching_header']}**")
                        admin_add_class_grade = st.selectbox(
                            text["grade_label"],
                            options=subjects.GRADES,
                            key=f"admin_add_class_grade_{teacher_username}",
                        )
                        admin_add_class_subject = st.selectbox(
                            text["subject_label"],
                            options=subjects.GRADE_SUBJECTS[admin_add_class_grade],
                            key=f"admin_add_class_subject_{teacher_username}",
                        )
                        if st.button(
                            text["add_teaching_button"], key=f"admin_add_class_button_{teacher_username}"
                        ):
                            users.add_teaching_assignment(
                                teacher_username, admin_add_class_grade, admin_add_class_subject
                            )
                            st.rerun()

                        render_change_password_and_delete(teacher_username, text)

        elif screen == "students":
            st.header(text["admin_students_menu_header"])
            student_grade_filter = st.selectbox(
                text["filter_by_grade_label"],
                options=[text["all_grades_option"]] + subjects.GRADES,
                key="student_filter_grade",
            )
            classes_for_filter = classes.list_classes(
                grade=None
                if student_grade_filter == text["all_grades_option"]
                else student_grade_filter
            )
            class_filter_choice = st.selectbox(
                text["filter_by_class_label"],
                options=[text["all_classes_option"]] + [c["name"] for c in classes_for_filter],
                key="student_filter_class",
            )
            student_search_text = st.text_input(
                text["search_teacher_label"], key="student_filter_search"
            )

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
                        st.write(
                            f"{text['homeroom_label']}: {student_record['homeroom_name'] or '—'}"
                        )

                        st.write(f"**{text['links_list_label']}**")
                        if not student_record["subject_links"]:
                            st.caption(text["no_links_message"])
                        else:
                            for link in student_record["subject_links"]:
                                link_base_key = (
                                    f"{student_username}_{link['teacher']}_"
                                    f"{link['grade']}_{link['subject']}"
                                )
                                moving_key = f"moving_link_{link_base_key}"
                                link_col, move_col, remove_col = st.columns([3, 1, 1])
                                with link_col:
                                    st.write(
                                        f"- {link['subject']} ({link['grade']}) — {link['teacher']}"
                                    )
                                with move_col:
                                    if st.button(
                                        text["move_link_button"], key=f"move_{link_base_key}"
                                    ):
                                        st.session_state[moving_key] = True
                                with remove_col:
                                    if st.button(
                                        text["remove_link_button"], key=f"unlink_{link_base_key}"
                                    ):
                                        users.unlink_student_from_teacher(
                                            student_username,
                                            link["teacher"],
                                            link["grade"],
                                            link["subject"],
                                        )
                                        st.success(text["link_removed_message"])
                                        st.rerun()

                                if st.session_state.get(moving_key):
                                    move_target_teachers = [
                                        u["username"] for u in users.list_all_users(role="teacher")
                                    ]
                                    move_chosen_teacher = st.selectbox(
                                        text["move_to_label"],
                                        options=move_target_teachers,
                                        key=f"move_teacher_{link_base_key}",
                                    )
                                    move_teacher_teaching = users.get_user(move_chosen_teacher)[
                                        "teaching"
                                    ]
                                    if not move_teacher_teaching:
                                        st.caption(text["no_teaching_message"])
                                    else:
                                        move_teaching_labels = [
                                            f"{a['subject']} ({a['grade']})"
                                            for a in move_teacher_teaching
                                        ]
                                        move_chosen_label = st.selectbox(
                                            text["subject_label"],
                                            options=move_teaching_labels,
                                            key=f"move_subject_{link_base_key}",
                                        )
                                        move_chosen_assignment = move_teacher_teaching[
                                            move_teaching_labels.index(move_chosen_label)
                                        ]
                                        if st.button(
                                            text["confirm_move_button"],
                                            key=f"confirm_move_{link_base_key}",
                                        ):
                                            try:
                                                users.move_student_link(
                                                    student_username,
                                                    link["teacher"],
                                                    link["grade"],
                                                    link["subject"],
                                                    move_chosen_teacher,
                                                    move_chosen_assignment["grade"],
                                                    move_chosen_assignment["subject"],
                                                )
                                                st.session_state[moving_key] = False
                                                st.success(text["link_moved_message"])
                                                st.rerun()
                                            except ValueError:
                                                st.error(text["link_failed_error"])

                        st.write(f"**{text['add_link_header']}**")
                        all_teacher_usernames = [
                            u["username"] for u in users.list_all_users(role="teacher")
                        ]
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
                                chosen_assignment = teacher_teaching[
                                    teaching_labels.index(chosen_label)
                                ]
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

        elif screen == "bug_reports":
            st.header(text["bug_reports_header"])
            conn = db.get_connection()
            try:
                bug_rows = conn.execute(
                    "SELECT * FROM bug_reports ORDER BY created_at DESC"
                ).fetchall()
            finally:
                conn.close()
            if not bug_rows:
                st.caption(text["no_bug_reports_message"])
            else:
                for br in bug_rows:
                    label = (
                        f"{text['bug_report_from']}: {br['username']} ({br['role']}) — "
                        f"{br['created_at'][:10]}"
                    )
                    with st.expander(label):
                        st.write(br["description"])

        else:  # screen == "artemis"
            if not st.session_state.artemis_chat_loaded:
                existing_chats = chat_storage.load_chats(st.session_state.username)
                if existing_chats:
                    st.session_state.artemis_chat = existing_chats[0]
                else:
                    artemis_system_prompt = prompts.build_artemis_system_prompt(language)
                    st.session_state.artemis_chat = chat_storage.create_chat(
                        st.session_state.username, ARTEMIS_GRADE, ARTEMIS_SUBJECT, artemis_system_prompt
                    )
                st.session_state.artemis_chat_loaded = True

            with st.expander(text["artemis_abilities_header"]):
                for ability in artemis_actions.ABILITIES:
                    params_text = ", ".join(ability["params"])
                    st.markdown(f"- **{ability['name']}** ({params_text}): {ability['description']}")

            artemis_available_models = chat.get_available_models()

            if artemis_available_models:
                artemis_default_index = (
                    artemis_available_models.index(config.CHAT_MODEL_NAME)
                    if config.CHAT_MODEL_NAME in artemis_available_models
                    else 0
                )
                artemis_selected_model = st.selectbox(
                    text["model_label"],
                    artemis_available_models,
                    index=artemis_default_index,
                    key="artemis_model",
                )

                artemis_chat = st.session_state.artemis_chat
                has_visible_messages = any(m["role"] != "system" for m in artemis_chat["history"])
                if not has_visible_messages:
                    st.caption(text["artemis_intro_message"])

                for message in artemis_chat["history"]:
                    if message["role"] == "system":
                        continue
                    with st.chat_message(message["role"]):
                        st.write(message["content"])

                admin_message = st.chat_input(text["chat_placeholder"], key="artemis_chat_input")

                if admin_message:
                    with st.chat_message("user"):
                        st.write(admin_message)

                    try:
                        with st.spinner(text["thinking_spinner"]):
                            artemis_reply = chat.ask_assistant(
                                artemis_chat["history"], admin_message, artemis_selected_model
                            )
                    except Exception:
                        st.error(text["ollama_disconnected"])
                        st.stop()

                    with st.chat_message("assistant"):
                        st.write(artemis_reply)

                    chat_storage.add_message(artemis_chat["id"], "user", admin_message)
                    chat_storage.add_message(artemis_chat["id"], "assistant", artemis_reply)

                    # If Artemis proposed an action, run it right away -- no
                    # separate confirm step -- and add the result as its own
                    # follow-up message so it's part of the saved transcript.
                    action_result = run_proposed_artemis_action(artemis_reply, text)
                    if action_result:
                        with st.chat_message("assistant"):
                            st.write(action_result)
                        chat_storage.add_message(artemis_chat["id"], "assistant", action_result)
                        artemis_chat["history"].append({"role": "assistant", "content": action_result})

    elif role == "teacher":
        if screen == "main_menu":
            st.write(text["welcome_message"].format(username=st.session_state.username))
            st.write(f"{text['join_code_label']}: `{current_user['join_code']}`")

            stat_columns = st.columns(3)
            with stat_columns[0]:
                st.metric(text["stat_classes_taught"], len(current_user["teaching"]))
            with stat_columns[1]:
                st.metric(
                    text["stat_students_linked"],
                    len(users.students_linked_to_teacher(st.session_state.username)),
                )
            with stat_columns[2]:
                st.metric(
                    text["stat_tests_saved"],
                    len(exams.list_tests_for_teacher(st.session_state.username)),
                )

            st.divider()
            quick_col1, quick_col2 = st.columns(2)
            with quick_col1:
                if st.button(
                    f"📢 {text['screen_announcements']}",
                    use_container_width=True,
                    key="quick_announcements",
                ):
                    st.session_state.pending_screen_id = "announcements"
                    st.rerun()
            with quick_col2:
                if st.button(
                    f"📝 {text['screen_exercises']}",
                    use_container_width=True,
                    key="quick_exercises",
                ):
                    st.session_state.pending_screen_id = "exercises"
                    st.rerun()

        elif screen == "supervise":
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
                    timestamps = [
                        m["created_at"] for m in non_system_messages if m.get("created_at")
                    ]
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

        elif screen == "my_classes":
            st.header(text["add_teaching_header"])
            add_grade = st.selectbox(
                text["grade_label"], options=subjects.GRADES, key="add_teaching_grade"
            )
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
                    class_record = classes.get_or_create_class(
                        st.session_state.username, assignment["grade"], assignment["subject"]
                    )
                    class_student_usernames = classes.students_in_class(class_record["id"])
                    with st.expander(
                        f"{assignment['subject']} ({assignment['grade']}) — "
                        f"{len(class_student_usernames)} {text['admin_students_menu_header'].lower()}"
                    ):
                        if not class_student_usernames:
                            st.caption(text["no_students_message"])
                        else:
                            for student_username in class_student_usernames:
                                st.write(f"- {student_username}")

        elif screen == "tests":
            if not st.session_state.test_chats_loaded:
                st.session_state.test_chats = chat_storage.load_chats(st.session_state.username)
                st.session_state.active_test_chat_id = None
                st.session_state.test_chats_loaded = True

            logos_available_models = chat.get_available_models()

            if logos_available_models:
                logos_default_index = (
                    logos_available_models.index(config.CHAT_MODEL_NAME)
                    if config.CHAT_MODEL_NAME in logos_available_models
                    else 0
                )
                logos_selected_model = st.selectbox(
                    text["model_label"],
                    logos_available_models,
                    index=logos_default_index,
                    key="logos_model",
                )

                st.subheader(text["material_for_exams_header"])
                st.caption(text["upload_for_exams_help"])
                uploaded_exam_pdf = st.file_uploader(
                    text["upload_label"], type="pdf", key="logos_pdf_uploader"
                )
                if uploaded_exam_pdf is not None and st.button(
                    text["upload_button"], key="logos_upload_button"
                ):
                    os.makedirs(config.DOCUMENTS_DIR, exist_ok=True)
                    exam_pdf_path = os.path.join(config.DOCUMENTS_DIR, uploaded_exam_pdf.name)

                    with open(exam_pdf_path, "wb") as pdf_file:
                        pdf_file.write(uploaded_exam_pdf.getbuffer())

                    with st.spinner(text["upload_spinner"]):
                        num_chunks_added = rag.add_pdf_to_vector_store(
                            exam_pdf_path, collection_name=rag.TEACHER_MATERIALS_COLLECTION
                        )

                    st.success(text["upload_success"].format(num_chunks=num_chunks_added))

                st.subheader(text["logos_new_test_chat_header"])
                if not current_user["teaching"]:
                    st.caption(text["no_teaching_message"])
                else:
                    logos_mode_label = st.radio(
                        text["logos_mode_label"],
                        [text["logos_mode_draft"], text["logos_mode_analyze"]],
                        key="logos_new_chat_mode",
                    )
                    logos_teaching_labels = [
                        f"{a['subject']} ({a['grade']})" for a in current_user["teaching"]
                    ]
                    logos_chosen_label = st.selectbox(
                        text["subject_label"],
                        options=logos_teaching_labels,
                        key="logos_new_chat_subject",
                    )
                    logos_chosen_assignment = current_user["teaching"][
                        logos_teaching_labels.index(logos_chosen_label)
                    ]

                    if st.button(text["create_chat_button"], key="logos_create_chat"):
                        if logos_mode_label == text["logos_mode_draft"]:
                            logos_mode_id = "draft"
                            logos_system_prompt = prompts.build_logos_system_prompt(
                                logos_chosen_assignment["grade"],
                                logos_chosen_assignment["subject"],
                                language,
                            )
                            bank_questions = questions.list_questions_for_teacher(
                                st.session_state.username,
                                logos_chosen_assignment["grade"],
                                logos_chosen_assignment["subject"],
                            )
                            bank_context = prompts.build_question_bank_context(bank_questions)
                            if bank_context:
                                logos_system_prompt += "\n\n" + bank_context
                        else:
                            logos_mode_id = "analyze"
                            activity_summary = build_class_activity_summary(
                                st.session_state.username,
                                logos_chosen_assignment["grade"],
                                logos_chosen_assignment["subject"],
                            ) or text["no_student_activity_message"]
                            logos_system_prompt = prompts.build_logos_analysis_prompt(
                                logos_chosen_assignment["grade"],
                                logos_chosen_assignment["subject"],
                                language,
                                activity_summary,
                            )

                        new_test_chat = chat_storage.create_chat(
                            st.session_state.username,
                            logos_chosen_assignment["grade"],
                            logos_chosen_assignment["subject"],
                            logos_system_prompt,
                            mode=logos_mode_id,
                        )

                        # Both modes immediately ask Logos something, rather
                        # than leaving a blank chat the teacher has to prompt
                        # themselves -- "analyze" relies only on the activity
                        # summary already baked into the system prompt above
                        # (never mixing in exam-material RAG here), while
                        # "draft" uses ask_logos_with_material so any
                        # uploaded PDF is pulled in right away.
                        if logos_mode_id == "analyze":
                            opening_prompt_text = text["analysis_opening_prompt"]
                            opening_reply = chat.ask_assistant(
                                new_test_chat["history"], opening_prompt_text, logos_selected_model
                            )
                        else:
                            opening_prompt_text = text["draft_opening_prompt"]
                            opening_reply = chat.ask_logos_with_material(
                                new_test_chat["history"], opening_prompt_text, logos_selected_model
                            )

                        chat_storage.add_message(new_test_chat["id"], "user", opening_prompt_text)
                        chat_storage.add_message(new_test_chat["id"], "assistant", opening_reply)

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
                    (
                        c
                        for c in st.session_state.test_chats
                        if c["id"] == st.session_state.active_test_chat_id
                    ),
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

                        # "draft" chats can use the teacher's uploaded exam
                        # material as RAG context; "analyze" chats rely only
                        # on the student activity baked into their system
                        # prompt and must never pull in unrelated PDF content.
                        ask_logos = (
                            chat.ask_logos_with_material
                            if active_test_chat.get("mode") != "analyze"
                            else chat.ask_assistant
                        )
                        try:
                            with st.spinner(text["thinking_spinner"]):
                                logos_reply = ask_logos(
                                    active_test_chat["history"], teacher_message, logos_selected_model
                                )
                        except Exception:
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
                        if st.button(
                            text["save_test_button"], key=f"save_test_{active_test_chat['id']}"
                        ):
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
                    with st.expander(
                        f"{saved_test['title']} — {saved_test['subject']} ({saved_test['grade']})"
                    ):
                        st.write(saved_test["content"])
                        if st.button(text["delete_test_button"], key=f"delete_test_{saved_test['id']}"):
                            exams.delete_test(saved_test["id"], st.session_state.username)
                            st.rerun()

            st.subheader(text["generate_structured_test_header"])
            if not current_user["teaching"]:
                st.caption(text["no_teaching_message"])
            elif not logos_available_models:
                st.caption(text["ollama_unreachable"])
            else:
                gen_teaching_labels = [
                    f"{a['subject']} ({a['grade']})" for a in current_user["teaching"]
                ]
                gen_chosen_label = st.selectbox(
                    text["subject_label"], options=gen_teaching_labels, key="gen_test_subject"
                )
                gen_chosen_assignment = current_user["teaching"][
                    gen_teaching_labels.index(gen_chosen_label)
                ]
                num_questions = st.number_input(
                    text["num_questions_label"],
                    min_value=1,
                    max_value=20,
                    value=5,
                    key="gen_num_questions",
                )
                gen_test_title = st.text_input(text["test_title_label"], key="gen_test_title")

                if st.button(text["generate_test_button"], key="gen_test_button"):
                    with st.spinner(text["generating_test_spinner"]):
                        raw_test_text = chat.generate_structured_test(
                            gen_chosen_assignment["grade"],
                            gen_chosen_assignment["subject"],
                            language,
                            int(num_questions),
                            logos_selected_model,
                        )
                    parsed_questions = exams.parse_structured_test(raw_test_text)
                    st.session_state.generated_test_questions = parsed_questions
                    st.session_state.generated_test_grade = gen_chosen_assignment["grade"]
                    st.session_state.generated_test_subject = gen_chosen_assignment["subject"]

                    if not parsed_questions:
                        st.error(text["test_generation_failed_error"])
                    elif len(parsed_questions) < num_questions:
                        st.warning(
                            text["test_generation_partial_warning"].format(
                                parsed=len(parsed_questions), requested=int(num_questions)
                            )
                        )

                generated_questions = st.session_state.get("generated_test_questions")
                if generated_questions:
                    st.write(f"**{text['test_preview_header']}**")
                    for index, question in enumerate(generated_questions, start=1):
                        st.write(f"{text['question_label']} {index}: {question['question_text']}")
                        st.write(f"A) {question['option_a']}")
                        st.write(f"B) {question['option_b']}")
                        st.write(f"C) {question['option_c']}")
                        st.write(f"D) {question['option_d']}")
                        st.caption(f"{text['correct_answer_label']}: {question['correct_option']}")

                    if st.button(text["publish_test_button"], key="publish_test_button"):
                        if not gen_test_title:
                            st.error(text["signup_missing_fields_error"])
                        else:
                            exams.publish_test(
                                st.session_state.username,
                                st.session_state.generated_test_grade,
                                st.session_state.generated_test_subject,
                                gen_test_title,
                                generated_questions,
                            )
                            st.success(text["test_published_message"])
                            del st.session_state["generated_test_questions"]
                            st.rerun()

            st.subheader(text["published_tests_header"])
            published_tests = exams.list_published_tests_for_teacher(st.session_state.username)
            if not published_tests:
                st.caption(text["no_published_tests_message"])
            else:
                for published_test in published_tests:
                    with st.expander(
                        f"{published_test['title']} — {published_test['subject']} "
                        f"({published_test['grade']})"
                    ):
                        test_questions = exams.get_test_questions(published_test["id"])
                        submissions = exams.list_submissions(published_test["id"])
                        st.caption(f"{len(test_questions)} {text['question_label'].lower()}s")
                        st.write(f"{text['submissions_label']}: {len(submissions)}")
                        for submission in submissions:
                            st.write(
                                f"- {submission['student_username']}: "
                                f"{submission['score']}/{submission['total']}"
                            )
                        if st.button(
                            text["delete_test_button"], key=f"delete_published_{published_test['id']}"
                        ):
                            exams.delete_test(published_test["id"], st.session_state.username)
                            st.rerun()

        elif screen == "question_bank":
            st.header(text["screen_question_bank"])

            st.subheader(text["save_question_header"])
            if not current_user["teaching"]:
                st.caption(text["no_teaching_message"])
            else:
                qb_grade = st.selectbox(
                    text["grade_label"], options=subjects.GRADES, key="qb_grade"
                )
                qb_subject = st.selectbox(
                    text["subject_label"],
                    options=subjects.GRADE_SUBJECTS[qb_grade],
                    key="qb_subject",
                )
                qb_question = st.text_area(text["question_text_label"], key="qb_question_text")
                qb_answer = st.text_area(text["answer_text_label"], key="qb_answer_text")
                if st.button(text["save_question_button"]):
                    if qb_question.strip() and qb_answer.strip():
                        questions.save_question(
                            st.session_state.username,
                            qb_grade,
                            qb_subject,
                            qb_question.strip(),
                            qb_answer.strip(),
                        )
                        st.success(text["question_saved_message"])
                        st.rerun()
                    else:
                        st.error(text["signup_missing_fields_error"])

            st.subheader(text["your_questions_header"])
            qb_filter_grade = st.selectbox(
                text["question_bank_grade_filter"],
                options=[text["question_bank_all_option"]] + subjects.GRADES,
                key="qb_filter_grade",
            )
            selected_grade_filter = None if qb_filter_grade == text["question_bank_all_option"] else qb_filter_grade
            saved_questions = questions.list_questions_for_teacher(
                st.session_state.username, grade=selected_grade_filter
            )
            if not saved_questions:
                st.caption(text["no_questions_message"])
            else:
                for qb_q in saved_questions:
                    label = f"{qb_q['subject']} ({qb_q['grade']}): {qb_q['question_text'][:80]}..."
                    with st.expander(label):
                        st.write(f"**{text['question_text_label']}:** {qb_q['question_text']}")
                        st.write(f"**{text['answer_text_label']}:** {qb_q['answer_text']}")
                        if st.button(
                            text["delete_question_button"], key=f"del_q_{qb_q['id']}"
                        ):
                            questions.delete_question(qb_q["id"], st.session_state.username)
                            st.success(text["question_deleted_message"])
                            st.rerun()

        elif screen == "announcements":
            st.header(text["screen_announcements"])

            # Pick a class for the new announcement
            teacher_assignments = current_user.get("teaching", [])
            if not teacher_assignments:
                st.info(text["no_classes_message"] if "no_classes_message" in text else "No classes yet.")
            else:
                st.subheader(text["new_announcement_header"])
                ann_options = [
                    f"{a['subject']} — {a['grade']}" for a in teacher_assignments
                ]
                ann_selection = st.selectbox(
                    text["grade_label"] + " / " + text["subject_label"],
                    options=ann_options,
                    key="ann_class_select",
                )
                ann_idx = ann_options.index(ann_selection)
                ann_grade = teacher_assignments[ann_idx]["grade"]
                ann_subject = teacher_assignments[ann_idx]["subject"]

                ann_content = st.text_area(
                    text["announcement_content_label"], key="ann_content"
                )
                if st.button(text["post_announcement_button"]):
                    if ann_content.strip():
                        announcements.save_announcement(
                            st.session_state.username, ann_grade, ann_subject, ann_content.strip()
                        )
                        st.success(text["announcement_posted_message"])
                        st.rerun()
                    else:
                        st.error(text["signup_missing_fields_error"])

            st.subheader(text["your_announcements_header"])
            teacher_anns = announcements.list_announcements_for_teacher(st.session_state.username)
            if not teacher_anns:
                st.caption(text["no_announcements_teacher_message"])
            else:
                for ann in teacher_anns:
                    with st.expander(f"{ann['subject']} ({ann['grade']}) — {ann['created_at'][:10]}"):
                        st.write(ann["content"])
                        if st.button(
                            text["delete_announcement_button"], key=f"del_ann_{ann['id']}"
                        ):
                            announcements.delete_announcement(ann["id"], st.session_state.username)
                            st.success(text["announcement_deleted_message"])
                            st.rerun()

        elif screen == "exercises":
            st.header(text["screen_exercises"])

            teacher_assignments = current_user.get("teaching", [])
            if not teacher_assignments:
                st.info(text["no_classes_message"] if "no_classes_message" in text else "No classes yet.")
            else:
                st.subheader(text["new_exercise_header"])
                ex_options = [
                    f"{a['subject']} — {a['grade']}" for a in teacher_assignments
                ]
                ex_selection = st.selectbox(
                    text["grade_label"] + " / " + text["subject_label"],
                    options=ex_options,
                    key="ex_class_select",
                )
                ex_idx = ex_options.index(ex_selection)
                ex_grade = teacher_assignments[ex_idx]["grade"]
                ex_subject = teacher_assignments[ex_idx]["subject"]

                ex_title = st.text_input(text["exercise_title_label"], key="ex_title")
                ex_content = st.text_area(text["exercise_content_label"], key="ex_content")
                if st.button(text["publish_exercise_button"]):
                    if ex_title.strip() and ex_content.strip():
                        exercises.save_exercise(
                            st.session_state.username,
                            ex_grade,
                            ex_subject,
                            ex_title.strip(),
                            ex_content.strip(),
                        )
                        st.success(text["exercise_published_message"])
                        st.rerun()
                    else:
                        st.error(text["signup_missing_fields_error"])

            st.subheader(text["your_exercises_header"])
            teacher_exs = exercises.list_exercises_for_teacher(st.session_state.username)
            if not teacher_exs:
                st.caption(text["no_exercises_teacher_message"])
            else:
                for ex in teacher_exs:
                    with st.expander(f"{ex['title']} — {ex['subject']} ({ex['grade']})"):
                        st.write(ex["content"])
                        if st.button(
                            text["delete_exercise_button"], key=f"del_ex_{ex['id']}"
                        ):
                            exercises.delete_exercise(ex["id"], st.session_state.username)
                            st.success(text["exercise_deleted_message"])
                            st.rerun()

    else:  # role == "student"
        if not st.session_state.chats_loaded:
            st.session_state.chats = chat_storage.load_chats(st.session_state.username)
            st.session_state.active_chat_id = None
            st.session_state.chats_loaded = True

        if screen == "main_menu":
            st.write(text["welcome_message"].format(username=st.session_state.username))
            st.write(f"{text['grade_label']}: {current_user['grade']}")
            st.write(f"{text['homeroom_label']}: {current_user['homeroom_name'] or '—'}")

            stat_columns = st.columns(2)
            with stat_columns[0]:
                st.metric(text["stat_linked_classes"], len(current_user["subject_links"]))
            with stat_columns[1]:
                st.metric(text["stat_chats_started"], len(st.session_state.chats))

            student_announcements = announcements.list_announcements_for_student(
                st.session_state.username
            )
            if student_announcements:
                st.subheader(text["announcements_header"])
                for ann in student_announcements:
                    with st.expander(f"📢 {ann['subject']} ({ann['grade']}) — {ann['created_at'][:10]}"):
                        st.write(ann["content"])

        elif screen == "link_teacher":
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

        elif screen == "material":
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

        elif screen == "chat":
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

            available_models = chat.get_available_models()

            default_index = (
                available_models.index(config.CHAT_MODEL_NAME)
                if config.CHAT_MODEL_NAME in available_models
                else 0
            )
            selected_model = st.selectbox(text["model_label"], available_models, index=default_index)

            active_chat = next(
                (c for c in st.session_state.chats if c["id"] == st.session_state.active_chat_id),
                None,
            )

            # If the student arrived here via "Work with Socrates" from the
            # exercises screen, auto-create a chat and pre-fill the message.
            if st.session_state.get("prefill_exercise"):
                prefill_ex = st.session_state.pop("prefill_exercise")
                ex_grade = prefill_ex["grade"]
                ex_subject = prefill_ex["subject"]
                # Find an existing chat for this subject, or create one.
                existing = next(
                    (c for c in st.session_state.chats
                     if c["grade"] == ex_grade and c["subject"] == ex_subject),
                    None,
                )
                if existing is None:
                    sp = prompts.build_system_prompt(ex_grade, ex_subject, language)
                    existing = chat_storage.create_chat(
                        st.session_state.username, ex_grade, ex_subject, sp
                    )
                    st.session_state.chats.append(existing)
                st.session_state.active_chat_id = existing["id"]
                st.session_state.prefill_exercise_text = (
                    f"[{prefill_ex['title']}]\n\n{prefill_ex['content']}"
                )

            if active_chat is None:
                st.info(text["no_chats_message"])
            else:
                st.subheader(f"{active_chat['subject']} ({active_chat['grade']})")

                # Study goal
                current_goal = goals.get_goal(
                    st.session_state.username,
                    active_chat["grade"],
                    active_chat["subject"],
                )
                with st.expander(
                    f"🎯 {text['current_goal_label']}: {current_goal or '—'}",
                    expanded=False,
                ):
                    new_goal = st.text_input(
                        text["study_goal_header"],
                        value=current_goal or "",
                        placeholder=text["study_goal_placeholder"],
                        key=f"goal_input_{active_chat['id']}",
                    )
                    goal_col1, goal_col2 = st.columns(2)
                    with goal_col1:
                        if st.button(text["save_goal_button"], key=f"save_goal_{active_chat['id']}"):
                            if new_goal.strip():
                                goals.set_goal(
                                    st.session_state.username,
                                    active_chat["grade"],
                                    active_chat["subject"],
                                    new_goal.strip(),
                                )
                                st.success(text["goal_saved_message"])
                                st.rerun()
                    with goal_col2:
                        if current_goal and st.button(
                            text["clear_goal_button"], key=f"clear_goal_{active_chat['id']}"
                        ):
                            goals.delete_goal(
                                st.session_state.username,
                                active_chat["grade"],
                                active_chat["subject"],
                            )
                            st.success(text["goal_cleared_message"])
                            st.rerun()

                # Summarise + export buttons
                user_msgs_in_chat = [m for m in active_chat["history"] if m["role"] == "user"]
                action_cols = st.columns(2)
                with action_cols[0]:
                    if user_msgs_in_chat and st.button(
                        text["summarize_chat_button"],
                        key=f"summarize_{active_chat['id']}",
                    ):
                        with st.spinner(text["summarizing_spinner"]):
                            try:
                                chat_summary = chat.summarize_chat(
                                    active_chat["history"],
                                    active_chat["grade"],
                                    active_chat["subject"],
                                    language,
                                    selected_model,
                                )
                            except Exception:
                                chat_summary = None
                        if chat_summary:
                            with st.expander(text["summarize_header"], expanded=True):
                                st.write(chat_summary)
                        else:
                            st.warning(text["summary_too_short_error"])
                with action_cols[1]:
                    if user_msgs_in_chat:
                        export_lines = [
                            f"=== {active_chat['subject']} ({active_chat['grade']}) ===\n"
                        ]
                        for m in active_chat["history"]:
                            if m["role"] == "system":
                                continue
                            role_label = (
                                st.session_state.username
                                if m["role"] == "user"
                                else config.ASSISTANT_NAMES["student"]
                            )
                            export_lines.append(f"{role_label}: {m['content']}\n")
                        export_text = "\n".join(export_lines)
                        st.download_button(
                            label=text["export_chat_button"],
                            data=export_text,
                            file_name=f"chat_{active_chat['id']}.txt",
                            mime="text/plain",
                            key=f"export_{active_chat['id']}",
                        )

                # Chat messages with per-reply "Save note" button
                for msg_idx, message in enumerate(active_chat["history"]):
                    if message["role"] == "system":
                        continue
                    with st.chat_message(message["role"]):
                        st.write(message["content"])
                        if message["role"] == "assistant":
                            if st.button(
                                text["save_note_button"],
                                key=f"note_{active_chat['id']}_{msg_idx}",
                            ):
                                notes.save_note(
                                    st.session_state.username,
                                    active_chat["grade"],
                                    active_chat["subject"],
                                    message["content"],
                                )
                                st.success(text["note_saved_message"])

                # Pre-filled exercise text (from Exercises screen)
                prefill_text = st.session_state.pop("prefill_exercise_text", None)

                student_message = st.chat_input(
                    text["chat_placeholder"],
                    key="chat_input_main",
                )
                if prefill_text and not student_message:
                    student_message = prefill_text

                if student_message:
                    with st.chat_message("user"):
                        st.write(student_message)

                    try:
                        with st.spinner(text["thinking_spinner"]):
                            tutor_reply = chat.ask_tutor(
                                active_chat["history"], student_message, selected_model
                            )
                    except Exception:
                        st.error(text["ollama_disconnected"])
                        st.stop()

                    with st.chat_message("assistant"):
                        st.write(tutor_reply)

                    chat_storage.add_message(active_chat["id"], "user", student_message)
                    chat_storage.add_message(active_chat["id"], "assistant", tutor_reply)

        elif screen == "tests":
            st.header(text["available_tests_header"])
            available_tests = exams.list_published_tests_for_student(st.session_state.username)

            if not available_tests:
                st.caption(text["no_available_tests_message"])
            else:
                for available_test in available_tests:
                    submission = exams.get_submission(
                        available_test["id"], st.session_state.username
                    )
                    test_label = (
                        f"{available_test['title']} — {available_test['subject']} "
                        f"({available_test['grade']})"
                    )

                    if submission is not None:
                        st.write(
                            f"{test_label} — {text['test_completed_label']}: "
                            f"{submission['score']}/{submission['total']}"
                        )
                        continue

                    with st.expander(test_label):
                        taking_key = f"taking_test_{available_test['id']}"
                        if not st.session_state.get(taking_key) and st.button(
                            text["start_test_button"], key=f"start_{available_test['id']}"
                        ):
                            st.session_state[taking_key] = True

                        if st.session_state.get(taking_key):
                            test_questions = exams.get_test_questions(available_test["id"])
                            selected_answers = {}
                            for index, question in enumerate(test_questions, start=1):
                                st.write(f"**{text['question_label']} {index}**: {question['question_text']}")
                                options = {
                                    "A": question["option_a"],
                                    "B": question["option_b"],
                                    "C": question["option_c"],
                                    "D": question["option_d"],
                                }
                                choice_labels = [f"{letter}) {text_}" for letter, text_ in options.items()]
                                chosen = st.radio(
                                    text["question_label"],
                                    options=choice_labels,
                                    key=f"answer_{available_test['id']}_{question['id']}",
                                    index=None,
                                    label_visibility="collapsed",
                                )
                                if chosen is not None:
                                    selected_answers[question["id"]] = chosen[0]

                            if st.button(
                                text["submit_answers_button"], key=f"submit_{available_test['id']}"
                            ):
                                if len(selected_answers) < len(test_questions):
                                    st.error(text["answer_missing_error"])
                                else:
                                    result = exams.submit_test(
                                        available_test["id"],
                                        st.session_state.username,
                                        selected_answers,
                                    )
                                    st.session_state[taking_key] = False
                                    st.success(
                                        f"{text['your_score_label']}: "
                                        f"{result['score']}/{result['total']}"
                                    )
                                    st.rerun()

        elif screen == "progress":
            st.header(text["screen_progress"])
            all_chats = st.session_state.chats
            all_user_msgs = [
                m for c in all_chats for m in c["history"] if m["role"] == "user"
            ]

            metric_cols = st.columns(2)
            with metric_cols[0]:
                st.metric(text["stat_chats_started"], len(all_chats))
            with metric_cols[1]:
                st.metric(text["stats_total_messages"], len(all_user_msgs))

            if not all_chats:
                st.caption(text["stats_no_activity"])
            else:
                # Messages per subject
                st.subheader(text["stats_messages_by_subject"])
                subject_counts: dict[str, int] = {}
                for c in all_chats:
                    key = c["subject"]
                    count = sum(1 for m in c["history"] if m["role"] == "user")
                    subject_counts[key] = subject_counts.get(key, 0) + count

                if subject_counts:
                    col_label = "Mensajes" if language == "es" else "Messages"
                    df_subjects = pd.DataFrame(
                        {col_label: subject_counts}
                    )
                    st.bar_chart(df_subjects)

                # Weekly activity
                st.subheader(text["stats_weekly_activity"])
                from datetime import datetime as _dt
                weekly_counts: dict[str, int] = {}
                for msg in all_user_msgs:
                    ts = msg.get("created_at")
                    if not ts:
                        continue
                    try:
                        dt = _dt.fromisoformat(ts)
                        week_label = dt.strftime("%Y-W%V")
                        weekly_counts[week_label] = weekly_counts.get(week_label, 0) + 1
                    except Exception:
                        pass

                if weekly_counts:
                    sorted_weeks = sorted(weekly_counts.keys())
                    col_label = "Mensajes" if language == "es" else "Messages"
                    df_weekly = pd.DataFrame(
                        {col_label: [weekly_counts[w] for w in sorted_weeks]},
                        index=sorted_weeks,
                    )
                    st.bar_chart(df_weekly)
                else:
                    st.caption(text["stats_no_activity"])

        elif screen == "flashcards":
            st.header(text["flashcards_header"])
            flashcards = exams.list_flashcards_for_student(st.session_state.username)

            if not flashcards:
                st.caption(text["no_flashcards_message"])
            else:
                for flashcard in flashcards:
                    with st.expander(flashcard["question_text"]):
                        reveal_key = f"reveal_flashcard_{flashcard['id']}"
                        if st.button(text["show_answer_button"], key=f"show_{flashcard['id']}"):
                            st.session_state[reveal_key] = True

                        if st.session_state.get(reveal_key):
                            st.write(flashcard["correct_answer_text"])

                        if st.button(text["got_it_button"], key=f"got_it_{flashcard['id']}"):
                            exams.delete_flashcard(flashcard["id"], st.session_state.username)
                            st.rerun()

        elif screen == "exercises":
            st.header(text["screen_exercises"])
            st.caption(text["exercises_hint"])
            student_exs = exercises.list_exercises_for_student(st.session_state.username)
            if not student_exs:
                st.caption(text["no_exercises_student_message"])
            else:
                st.subheader(text["available_exercises_header"])
                for ex in student_exs:
                    with st.expander(f"{ex['title']} — {ex['subject']} ({ex['grade']})"):
                        st.write(ex["content"])
                        if st.button(
                            text["work_exercise_button"], key=f"work_ex_{ex['id']}"
                        ):
                            st.session_state.prefill_exercise = {
                                "grade": ex["grade"],
                                "subject": ex["subject"],
                                "title": ex["title"],
                                "content": ex["content"],
                            }
                            st.session_state.pending_screen_id = "chat"
                            st.rerun()

        elif screen == "notes":
            st.header(text["screen_notes"])
            filter_opts = [text["all_subjects_option"]] + [
                lnk["subject"] for lnk in current_user.get("subject_links", [])
            ]
            note_subject_filter = st.selectbox(
                text["filter_notes_label"], options=filter_opts, key="note_filter"
            )
            subject_arg = (
                None if note_subject_filter == text["all_subjects_option"] else note_subject_filter
            )
            student_note_list = notes.list_notes_for_student(
                st.session_state.username, subject=subject_arg
            )
            if not student_note_list:
                st.caption(text["no_notes_message"])
            else:
                st.subheader(text["notes_header"])
                for note in student_note_list:
                    header = f"{note['subject']} ({note['grade']}) — {note['created_at'][:10]}"
                    with st.expander(header):
                        st.write(note["content"])
                        if st.button(
                            text["delete_note_button"], key=f"del_note_{note['id']}"
                        ):
                            notes.delete_note(note["id"], st.session_state.username)
                            st.success(text["note_deleted_message"])
                            st.rerun()
