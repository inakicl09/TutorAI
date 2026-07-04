"""One-off script to seed test accounts, so you can see the teacher/admin
dashboards and the student-activity/classes/homerooms views without
signing up 130 accounts by hand.

Run it yourself: python3 -m tutorai.seed_test_data

Creates 10 teachers (each teaching 5-8 classes) and 120 students (20 per
grade, each connected to 4-6 classes), all sharing the simple test
password below -- only ever linking within the student's own grade or one
grade below, never further -- and gives about half the students a sample
chat with a few backdated messages so "last active" timestamps vary.

Safe to re-run: accounts that already exist are skipped instead of being
recreated, but every test account's password is reset to PASSWORD on every
run, so it stays simple even if it was set under an older version.
"""

import random
from datetime import datetime, timedelta, timezone

from tutorai import chat_storage, classes, db, homerooms, prompts, subjects, users

PASSWORD = "1234"
NUM_TEACHERS = 10
STUDENTS_PER_GRADE = 20  # 20 × 6 grades = 120 students total


# Per-subject exchanges that sound like real Spanish secondary school students.
# Keys are matched by substring against the subject name (case-insensitive).
_EXCHANGES_BY_SUBJECT: dict[str, list[tuple[str, str]]] = {
    "Matemáticas": [
        (
            "No entiendo cómo factorizar x² + 5x + 6, no sé por dónde empezar.",
            "¿Qué dos números, al multiplicarlos, dan 6 y al sumarlos dan 5?",
        ),
        (
            "Me sale negativo cuando resuelvo esta ecuación de segundo grado y no sé si lo estoy haciendo bien.",
            "¿En qué paso crees que puede estar el error? ¿Has comprobado el discriminante?",
        ),
        (
            "No entiendo para qué sirve la derivada, mi profe dice que es la pendiente pero no lo pillo.",
            "Si la función te da la posición de un objeto en cada instante, ¿qué información te daría su derivada?",
        ),
        (
            "¿Cuándo se usa el teorema de Pitágoras? No sé en qué problemas aplicarlo.",
            "¿En qué tipo de triángulo se cumple ese teorema? ¿Qué sabes de sus lados?",
        ),
        (
            "No sé la diferencia entre perímetro y área, siempre las confundo en los exámenes.",
            "Si tuvieras que vallar un jardín, ¿qué medida necesitarías? ¿Y si quisieras cubrirlo de césped?",
        ),
        (
            "¿Cómo se resuelve un sistema de ecuaciones por sustitución?",
            "¿Qué significa 'despejar' una variable? ¿Cuál de las dos ecuaciones crees que es más sencilla para empezar?",
        ),
    ],
    "Historia": [
        (
            "No entiendo por qué empezó la Primera Guerra Mundial, parece que fue solo por el asesinato de un archiduque.",
            "¿Por qué crees que el asesinato de una sola persona pudo arrastrar a tantos países a la guerra? ¿Qué tensiones existían ya en Europa?",
        ),
        (
            "¿Cuál era la diferencia entre los aliados y las potencias centrales en la Gran Guerra?",
            "¿Qué países recuerdas que formaban cada bando? ¿Qué intereses o alianzas previas los unían?",
        ),
        (
            "No entiendo qué fue el feudalismo, me lío con los señores y los vasallos.",
            "¿Cómo crees que se organizaba la protección y la tierra en la Edad Media? ¿Quién protegía a quién y a cambio de qué?",
        ),
        (
            "¿Por qué cayó el Imperio Romano? En el libro hay mil causas y no sé cuál es la más importante.",
            "¿Qué problemas internos debilitaban al Imperio y qué presiones externas tenía al mismo tiempo?",
        ),
        (
            "No entiendo la diferencia entre el Antiguo Régimen y el liberalismo que vino después.",
            "¿Cómo se elegía a los gobernantes en el Antiguo Régimen? ¿Qué cambió con las ideas liberales?",
        ),
        (
            "¿Qué fue la Guerra Fría? Lo he leído pero no lo termino de entender.",
            "¿Qué dos países eran las superpotencias después de la Segunda Guerra Mundial? ¿En qué se diferenciaban sus sistemas políticos y económicos?",
        ),
    ],
    "Física": [
        (
            "No entiendo la diferencia entre velocidad y aceleración, para mí son lo mismo.",
            "Si vas en un coche a 90 km/h sin cambiar de velocidad, ¿cuánto vale tu aceleración en ese momento?",
        ),
        (
            "¿Para qué sirve la fórmula F = m·a? No sé cuándo usarla.",
            "Si empujas un objeto con más fuerza y su masa no cambia, ¿qué le pasará a su aceleración?",
        ),
        (
            "No entiendo la ley de Newton de acción y reacción, ¿cómo puede ser que las fuerzas sean iguales y opuestas?",
            "Si empujas una pared, ¿qué sientes en tu mano? ¿Quién ejerce esa fuerza sobre ti?",
        ),
        (
            "¿Qué es la energía potencial gravitatoria? No entiendo por qué depende de la altura.",
            "¿Qué le pasa a un objeto cuando cae desde mucho más alto? ¿Qué diferencia hace la altura en eso?",
        ),
        (
            "En el laboratorio me sale un resultado diferente al teórico, ¿lo habré hecho mal?",
            "¿Qué factores del experimento podrían explicar esa diferencia? ¿Hay algo que no pudieras controlar perfectamente?",
        ),
    ],
    "Química": [
        (
            "¿Cómo equilibro la ecuación H₂ + O₂ → H₂O? He intentado varias combinaciones.",
            "¿Cuántos átomos de hidrógeno y de oxígeno hay a cada lado ahora mismo? ¿Qué coeficiente tendría que cambiar?",
        ),
        (
            "No entiendo la diferencia entre un átomo y una molécula.",
            "Si el átomo es como una letra del alfabeto, ¿qué sería entonces una molécula?",
        ),
        (
            "¿Qué es el pH? Mi profe dice que mide la acidez pero no entiendo cómo.",
            "¿Has oído hablar de ácidos y bases en la vida cotidiana, como el zumo de limón o el bicarbonato? ¿Qué crees que tienen en común los ácidos entre sí?",
        ),
        (
            "No entiendo para qué sirve la tabla periódica en los exámenes.",
            "¿Qué información puedes leer de un elemento directamente en la tabla? ¿Qué te dice el número atómico?",
        ),
    ],
    "Biología": [
        (
            "¿Cómo funciona exactamente la fotosíntesis? Me sé los pasos de memoria pero no entiendo qué pasa de verdad.",
            "¿Qué ingredientes necesita la planta para realizarla y de dónde los obtiene?",
        ),
        (
            "No recuerdo la diferencia entre mitosis y meiosis, siempre las mezclo.",
            "¿Para qué sirve cada proceso en el organismo? ¿Qué tipo de células produce cada uno?",
        ),
        (
            "¿Qué es el ADN exactamente? Sé que tiene que ver con la herencia pero no entiendo cómo funciona.",
            "¿Cómo crees que el ADN puede contener toda la información necesaria para construir un ser vivo entero?",
        ),
        (
            "No entiendo cómo funciona la herencia genética con los genes dominantes y recesivos.",
            "Si tu madre tiene ojos marrones y tu padre ojos azules, ¿qué genes podría haber heredado cada uno de sus padres?",
        ),
        (
            "¿Qué diferencia hay entre una bacteria y un virus? En el examen nos preguntan eso siempre.",
            "¿Cuál de los dos tiene células propias? ¿Qué significa eso para cómo se reproducen?",
        ),
    ],
    "Lengua": [
        (
            "No sé cómo analizar sintácticamente esta oración: 'El perro de mi vecina ladra por las noches'.",
            "¿Cuál es el verbo principal de la oración? ¿Quién realiza esa acción?",
        ),
        (
            "¿Cuál es la diferencia entre una metáfora y un símil? Las confundo siempre.",
            "Cuando dices 'sus ojos son como estrellas', ¿qué palabra te indica que estás haciendo una comparación?",
        ),
        (
            "No entiendo el Lazarillo de Tormes, ¿de qué va exactamente?",
            "¿Quién cuenta la historia? ¿Qué tipo de vida lleva ese narrador al principio y cómo va cambiando?",
        ),
        (
            "¿Cuándo se pone coma antes de 'pero'? Mi profe dice que a veces sí y a veces no.",
            "¿Qué tipo de oración viene después del 'pero'? ¿Va uniendo dos ideas contrarias completas?",
        ),
        (
            "No entiendo qué es un complemento circunstancial. En el libro hay demasiados tipos.",
            "¿Qué información añade ese complemento a la oración: tiempo, lugar, modo...? ¿Puedes encontrar un ejemplo en el texto?",
        ),
    ],
    "Lengua Extranjera": [
        (
            "I don't understand when to use 'since' and 'for' with the present perfect.",
            "Think about what follows each word — is it a specific point in time or a length of time?",
        ),
        (
            "What's the difference between 'have gone' and 'have been' to a place?",
            "If someone 'has gone to London', where are they right now? What about someone who 'has been to London'?",
        ),
        (
            "When do I use Past Simple instead of Present Perfect? I always mix them up.",
            "Does the sentence mention a specific finished time in the past, like 'yesterday' or 'in 2020'?",
        ),
        (
            "I don't understand passive voice. Why does the sentence change so much?",
            "In 'The cake was eaten by María', who actually did the eating? How is the focus of the sentence different from 'María ate the cake'?",
        ),
        (
            "How do I use conditionals? There are so many types.",
            "Think about the first conditional: 'If it rains, I will stay home.' Is this situation possible or just imaginary?",
        ),
    ],
    "Geografía": [
        (
            "¿Por qué hay zonas climáticas tan diferentes en la Tierra?",
            "¿Cómo crees que el ángulo con el que los rayos del sol llegan a una zona afecta a su temperatura?",
        ),
        (
            "No entiendo la diferencia entre clima y tiempo atmosférico, para mí es lo mismo.",
            "Si mañana llueve en Madrid, ¿eso es el clima de Madrid o el tiempo de ese día? ¿Por qué?",
        ),
        (
            "¿Qué es la tasa de natalidad y cómo se calcula?",
            "¿Qué relación tiene el número de nacimientos con el total de la población? ¿Para qué le sirve eso a un geógrafo?",
        ),
        (
            "No entiendo por qué España tiene tanta variedad de paisajes.",
            "¿Qué factores geográficos podrían explicar que el norte y el sur de España tengan climas tan distintos?",
        ),
    ],
    "Filosofía": [
        (
            "No entiendo el imperativo categórico de Kant, lo he leído tres veces y nada.",
            "Imagina que vas a hacer algo. ¿Qué pasaría si todo el mundo en el mundo hiciera exactamente lo mismo que tú en esa situación?",
        ),
        (
            "¿Qué diferencia hay entre ética y moral? Para mí suenan igual.",
            "¿Crees que una norma moral puede cambiar de una cultura a otra? ¿Y una norma ética? ¿Eso marca alguna diferencia?",
        ),
        (
            "No entiendo el mito de la caverna de Platón. ¿Qué significa exactamente?",
            "¿Qué crees que representan las sombras en la pared de la caverna? ¿Y el prisionero que logra salir?",
        ),
        (
            "¿Por qué Descartes duda de todo al principio? Me parece un poco exagerado.",
            "¿Puedes pensar en algo de lo que estés absolutamente seguro que no puede ser falso o una ilusión?",
        ),
    ],
    "Literatura": [
        (
            "No entiendo de qué va el Quijote, lo he empezado y me aburre.",
            "¿Qué crees que le pasa al personaje al principio? ¿Por qué confunde molinos con gigantes?",
        ),
        (
            "¿Qué es el Modernismo? No lo distingo del Romanticismo.",
            "¿Qué actitud tienen los poetas románticos ante la sociedad? ¿Crees que los modernistas comparten esa misma actitud?",
        ),
        (
            "No entiendo el punto de vista narrativo. ¿Cuántos tipos hay?",
            "¿Quién cuenta la historia en el texto que tienes? ¿Participa en los hechos o los observa desde fuera?",
        ),
    ],
}

_FALLBACK_EXCHANGES: list[tuple[str, str]] = [
    (
        "No entiendo este concepto, mi profe lo explicó pero no me quedó claro.",
        "¿Qué parte concretamente es la que más te cuesta? ¿Hay alguna palabra del tema que no conozcas?",
    ),
    (
        "¿Es correcta mi respuesta? No estoy seguro.",
        "¿Cómo podrías comprobarlo tú mismo antes de preguntar?",
    ),
    (
        "No sé cómo empezar este problema, me bloqueo.",
        "¿Qué información te da el enunciado? ¿Qué es exactamente lo que te piden encontrar?",
    ),
    (
        "No entiendo el enunciado de la pregunta del examen.",
        "¿Qué palabras del enunciado no te quedan claras? ¿Puedes identificar cuál es la pregunta principal?",
    ),
    (
        "¿Me puedes dar la respuesta directamente? No tengo tiempo.",
        "¿Cuál sería tu mejor hipótesis ahora mismo? ¿Por qué?",
    ),
]


def _exchanges_for_subject(subject: str) -> list[tuple[str, str]]:
    """Return the exchange list that best matches this subject name.
    Prefers the longest matching key so 'Inglés' beats 'Lengua' for
    'Lengua Extranjera (Inglés)'."""
    subject_lower = subject.lower()
    best_key = ""
    best_exchanges = _FALLBACK_EXCHANGES
    for key, exchanges in _EXCHANGES_BY_SUBJECT.items():
        if key.lower() in subject_lower and len(key) > len(best_key):
            best_key = key
            best_exchanges = exchanges
    return best_exchanges


def seed_teachers() -> list[str]:
    teacher_usernames = []
    for index in range(1, NUM_TEACHERS + 1):
        username = f"profesor_test_{index:02d}"
        teacher_usernames.append(username)
        if users.username_exists(username):
            continue

        users.create_teacher(username, PASSWORD)
        # 5-8 assignments so there are enough classes for students needing 4-6 links.
        num_assignments = random.randint(5, 8)
        for _ in range(num_assignments):
            grade = random.choice(subjects.GRADES)
            subject = random.choice(subjects.GRADE_SUBJECTS[grade])
            users.add_teaching_assignment(username, grade, subject)

    return teacher_usernames


def top_up_teacher_assignments(teacher_usernames: list[str]) -> int:
    """Existing teachers seeded under an older, lower range may have fewer
    than 5 classes. Add more until each has at least 5. Returns how many
    assignments were added."""
    added = 0
    for username in teacher_usernames:
        teaching = users.get_user(username)["teaching"]
        target = random.randint(5, 8)
        attempts = 0
        while len(teaching) < target and attempts < 30:
            attempts += 1
            grade = random.choice(subjects.GRADES)
            subject = random.choice(subjects.GRADE_SUBJECTS[grade])
            if any(a["grade"] == grade and a["subject"] == subject for a in teaching):
                continue
            users.add_teaching_assignment(username, grade, subject)
            teaching.append({"grade": grade, "subject": subject})
            added += 1

    return added


def fix_invalid_subject_links() -> int:
    """Remove any subject_link created before the "own grade or one grade
    below" rule existed. Returns how many were removed."""
    removed = 0
    for user in users.list_all_users():
        if user["role"] != "student":
            continue

        student = users.get_user(user["username"])
        allowed_grades = users.allowed_link_grades(student["grade"])
        for link in student["subject_links"]:
            if link["grade"] not in allowed_grades:
                users.unlink_student_from_teacher(
                    user["username"], link["teacher"], link["grade"], link["subject"]
                )
                removed += 1

    return removed


def _candidate_assignments_for_grade(grade: str, teacher_usernames: list[str]) -> list[tuple]:
    """List (teacher_username, assignment) pairs valid for a student of this
    grade -- i.e. the teacher teaches at the student's own grade or one below."""
    allowed_grades = users.allowed_link_grades(grade)
    return [
        (teacher_username, assignment)
        for teacher_username in teacher_usernames
        for assignment in users.get_user(teacher_username)["teaching"]
        if assignment["grade"] in allowed_grades
    ]


def seed_students(teacher_usernames: list[str]) -> list[str]:
    """Create 20 students per grade (120 total), each linked to 4-6 classes."""
    student_usernames = []
    # Build the full list of (grade, index) pairs so students are distributed
    # evenly: 20 per grade in a fixed order, not randomly.
    grade_sequence = [
        (grade, index)
        for grade in subjects.GRADES
        for index in range(1, STUDENTS_PER_GRADE + 1)
    ]

    for global_index, (grade, grade_index) in enumerate(grade_sequence, start=1):
        username = f"alumno_test_{global_index:03d}"
        student_usernames.append(username)
        if users.username_exists(username):
            continue

        users.create_student(username, PASSWORD, grade)

        candidate_assignments = _candidate_assignments_for_grade(grade, teacher_usernames)
        if not candidate_assignments:
            continue

        num_links = min(random.randint(4, 6), len(candidate_assignments))
        for teacher_username, assignment in random.sample(candidate_assignments, num_links):
            users.link_student_to_teacher(
                username, teacher_username, assignment["grade"], assignment["subject"]
            )

    return student_usernames


def top_up_student_links(student_usernames: list[str], teacher_usernames: list[str]) -> int:
    """Existing students with fewer than 4 links get more added.
    Returns how many links were added."""
    added = 0
    for username in student_usernames:
        student = users.get_user(username)
        candidate_assignments = _candidate_assignments_for_grade(
            student["grade"], teacher_usernames
        )
        existing = {
            (link["teacher"], link["grade"], link["subject"])
            for link in student["subject_links"]
        }
        remaining_candidates = [
            (teacher_username, assignment)
            for teacher_username, assignment in candidate_assignments
            if (teacher_username, assignment["grade"], assignment["subject"]) not in existing
        ]

        target = random.randint(4, 6)
        num_to_add = min(max(target - len(existing), 0), len(remaining_candidates))
        if num_to_add <= 0:
            continue

        for teacher_username, assignment in random.sample(remaining_candidates, num_to_add):
            users.link_student_to_teacher(
                username, teacher_username, assignment["grade"], assignment["subject"]
            )
            added += 1

    return added


def seed_chat_activity(student_usernames: list[str]) -> None:
    for username in student_usernames:
        if random.random() > 0.5:
            continue  # leave about half the students with no activity

        subject_links = users.get_user(username)["subject_links"]
        if not subject_links:
            continue

        link = random.choice(subject_links)
        days_ago = random.randint(0, 30)
        base_time = datetime.now(timezone.utc) - timedelta(days=days_ago)

        system_prompt = prompts.build_system_prompt(link["grade"], link["subject"], "es")
        chat = chat_storage.create_chat(
            username, link["grade"], link["subject"], system_prompt,
            created_at=base_time.isoformat(),
        )

        num_exchanges = random.randint(1, 3)
        subject_exchanges = _exchanges_for_subject(link["subject"])
        for exchange_index in range(num_exchanges):
            student_line, tutor_line = random.choice(subject_exchanges)
            message_time = base_time + timedelta(minutes=exchange_index * 2)
            chat_storage.add_message(
                chat["id"], "user", student_line, created_at=message_time.isoformat()
            )
            chat_storage.add_message(
                chat["id"], "assistant", tutor_line,
                created_at=(message_time + timedelta(seconds=30)).isoformat(),
            )


def reset_test_passwords(usernames: list[str]) -> None:
    """Force every test account's password back to PASSWORD."""
    for username in usernames:
        users.set_password(username, PASSWORD)


def main() -> None:
    db.init_db()
    classes.sync_with_teaching_assignments()
    homerooms.backfill_homerooms()

    teacher_usernames = seed_teachers()
    topped_up_teaching_count = top_up_teacher_assignments(teacher_usernames)
    removed_count = fix_invalid_subject_links()
    student_usernames = seed_students(teacher_usernames)
    topped_up_links_count = top_up_student_links(student_usernames, teacher_usernames)
    seed_chat_activity(student_usernames)
    reset_test_passwords(teacher_usernames + student_usernames)

    total_students = STUDENTS_PER_GRADE * len(subjects.GRADES)
    print(f"Seeded {len(teacher_usernames)} teachers and {total_students} students "
          f"({STUDENTS_PER_GRADE} per grade).")
    print(f"Added {topped_up_teaching_count} teaching assignment(s) so every teacher has at least 5.")
    print(f"Removed {removed_count} subject link(s) that were too far from a student's grade.")
    print(f"Added {topped_up_links_count} subject link(s) so every student has at least 4 classes.")
    print(f"All seeded accounts use the password: {PASSWORD}")


if __name__ == "__main__":
    main()
