"""Admin actions Artemis (the admin-facing assistant) can perform, and
the machinery to parse and run them.

Artemis requests an action in a strict format (see
build_action_format_instructions); app.py parses that out of its reply
and runs it immediately via execute_action -- no separate human
confirmation step, per the user's explicit request. The ability list
below is deliberately a subset of (never more than) what a human admin
can already do through the regular dashboard -- Artemis doesn't get any
power the UI doesn't already have, and execute_action separately
refuses to let it delete the currently-logged-in admin's own account.
"""

import re
from typing import Optional

from tutorai import subjects, users

ACTION_START = "ACTION:"
ACTION_END = "END_ACTION"

ABILITIES = [
    {
        "name": "create_student",
        "description": "Create a new student account.",
        "params": ["username", "password", "grade"],
    },
    {
        "name": "create_teacher",
        "description": "Create a new teacher account.",
        "params": ["username", "password"],
    },
    {
        "name": "delete_user",
        "description": (
            "Permanently delete a user account (student, teacher, or "
            "admin) and everything tied to it."
        ),
        "params": ["username"],
    },
    {
        "name": "reset_password",
        "description": "Set a new password for an existing user.",
        "params": ["username", "new_password"],
    },
    {
        "name": "add_teaching_assignment",
        "description": "Give a teacher a new class to teach (a grade+subject pair).",
        "params": ["teacher_username", "grade", "subject"],
    },
    {
        "name": "link_student_to_teacher",
        "description": (
            "Connect a student to a teacher's class (grade+subject), as "
            "long as the teacher actually teaches it and the grade is the "
            "student's own grade or exactly one grade below."
        ),
        "params": ["student_username", "teacher_username", "grade", "subject"],
    },
    {
        "name": "unlink_student_from_teacher",
        "description": "Disconnect a student from a teacher's class.",
        "params": ["student_username", "teacher_username", "grade", "subject"],
    },
    {
        "name": "regenerate_join_code",
        "description": "Replace a teacher's join code with a new one.",
        "params": ["teacher_username"],
    },
]

_ABILITY_NAMES = {ability["name"] for ability in ABILITIES}


def build_abilities_reference() -> str:
    """Render the abilities list as text, for both Artemis's system
    prompt and the admin-facing "what can Artemis do" display."""
    lines = []
    for ability in ABILITIES:
        params_text = ", ".join(ability["params"])
        lines.append(f"- {ability['name']}({params_text}): {ability['description']}")
    return "\n".join(lines)


def build_action_format_instructions() -> str:
    """Instructions for the exact format Artemis must use to request an
    action -- included in its system prompt."""
    return (
        "When the administrator asks you to do something that matches one "
        "of your abilities above, request it using exactly this format, "
        "with nothing else on those lines:\n\n"
        f"{ACTION_START} <ability name>\n"
        "PARAM_<param name>: <value>\n"
        "(one PARAM_ line per parameter, using the exact parameter names "
        "listed above)\n"
        f"{ACTION_END}\n\n"
        "This will be carried out automatically right after your reply, "
        "and the administrator will see whether it succeeded as a "
        "separate follow-up message -- you don't need to confirm it "
        "yourself or claim you've already done it. If the request "
        "doesn't match any of your abilities, say so plainly instead of "
        "inventing one."
    )


_ABILITY_NAME_ALTERNATION = "|".join(sorted(_ABILITY_NAMES, key=len, reverse=True))
_ACTION_LINE_PATTERN = re.compile(
    rf"^\s*(?:{re.escape(ACTION_START)}\s*)?(?P<action_name>{_ABILITY_NAME_ALTERNATION})\b",
    re.IGNORECASE | re.MULTILINE,
)
_PARAM_LINE_PATTERN = re.compile(r"^\s*PARAM_(?P<key>\w+):\s*(?P<value>.+?)\s*$", re.IGNORECASE)
_END_LINE_PATTERN = re.compile(r"^\s*" + re.escape(ACTION_END) + r"\s*$", re.IGNORECASE)


def parse_proposed_action(text: str) -> Optional[dict]:
    """Find a requested action in Artemis's reply, if any. Returns
    {"name": ..., "params": {...}}, or None if nothing parseable is
    found.

    Deliberately tolerant of a small local model not following the
    requested format exactly -- e.g. Mistral has been observed dropping
    the "ACTION:" prefix and the "END_ACTION" terminator entirely, and
    varying the casing of both the ability name and the PARAM_ keys.
    Only the ability name needs to start a line (after an optional
    "ACTION:" prefix); PARAM_ lines are then collected from straight
    after it until a blank line, an unrelated line, or END_ACTION.
    """
    match = _ACTION_LINE_PATTERN.search(text)
    if not match:
        return None

    action_name = match["action_name"].strip().lower()

    params = {}
    for line in text[match.end():].splitlines():
        if not line.strip():
            if params:
                break
            continue
        if _END_LINE_PATTERN.match(line):
            break
        param_match = _PARAM_LINE_PATTERN.match(line)
        if not param_match:
            break
        params[param_match["key"].lower()] = param_match["value"].strip()

    return {"name": action_name, "params": params}


def describe_action(action: dict) -> str:
    """Plain technical summary of a proposed action, for the
    confirmation prompt (e.g. "create_student(username=ana, ...)")."""
    params_text = ", ".join(f"{key}={value}" for key, value in action["params"].items())
    return f"{action['name']}({params_text})"


def _validate_grade(grade: str) -> None:
    """Guard against a hallucinated grade string -- e.g. a model writing
    "1er ESO" instead of "1º ESO" would otherwise silently create a
    student whose grade isn't in subjects.GRADES, which later crashes
    users.allowed_link_grades (it indexes into that list) the first time
    anyone tries to link them to a teacher."""
    if grade not in subjects.GRADES:
        raise ValueError(f"Unknown grade {grade!r} (must be one of {subjects.GRADES})")


def _validate_subject(grade: str, subject: str) -> None:
    _validate_grade(grade)
    if subject not in subjects.GRADE_SUBJECTS[grade]:
        raise ValueError(f"{subject!r} is not an official subject for {grade!r}")


def execute_action(action: dict, current_admin_username: str) -> Optional[str]:
    """Run a confirmed action. Returns an extra detail string if there is
    one worth showing (e.g. a generated join code), or None. Raises
    ValueError for invalid input -- a missing parameter, an unrecognized
    grade or subject, an unknown action, or trying to delete your own
    logged-in account."""
    name = action["name"]
    params = action["params"]

    try:
        if name == "create_student":
            _validate_grade(params["grade"])
            users.create_student(params["username"], params["password"], params["grade"])
            return None
        if name == "create_teacher":
            return f"join_code={users.create_teacher(params['username'], params['password'])}"
        if name == "delete_user":
            if params["username"] == current_admin_username:
                raise ValueError("Cannot delete your own logged-in account")
            users.delete_user(params["username"])
            return None
        if name == "reset_password":
            users.set_password(params["username"], params["new_password"])
            return None
        if name == "add_teaching_assignment":
            _validate_subject(params["grade"], params["subject"])
            users.add_teaching_assignment(
                params["teacher_username"], params["grade"], params["subject"]
            )
            return None
        if name == "link_student_to_teacher":
            _validate_subject(params["grade"], params["subject"])
            users.link_student_to_teacher(
                params["student_username"],
                params["teacher_username"],
                params["grade"],
                params["subject"],
            )
            return None
        if name == "unlink_student_from_teacher":
            users.unlink_student_from_teacher(
                params["student_username"],
                params["teacher_username"],
                params["grade"],
                params["subject"],
            )
            return None
        if name == "regenerate_join_code":
            return f"join_code={users.regenerate_join_code(params['teacher_username'])}"
    except KeyError as error:
        raise ValueError(f"Missing parameter: {error}") from error

    raise ValueError(f"Unknown action: {name}")
