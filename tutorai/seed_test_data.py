"""One-off script to seed test accounts, so you can see the teacher/admin
dashboards and the student-activity/classes/homerooms views without
signing up 130 accounts by hand.

Run it yourself: python3 -m tutorai.seed_test_data

Creates 10 teachers (each teaching 5-8 classes) and 120 students (20 per
grade, each connected to 4-6 classes), all sharing the simple test
password below -- only ever linking within the student's own grade or one
grade below, never further -- and gives every student one chat per
linked subject, with subject-specific questions and backdated timestamps
so "last active" varies.

Safe to re-run: accounts that already exist are skipped instead of being
recreated, students who already have chats get no new ones, and every test
account's password is reset to PASSWORD on every run, so it stays simple
even if it was set under an older version.

seed_demo_if_empty() at the bottom is the automatic version app.py runs
on startup, for the hosted demo whose database starts empty on every boot.
"""

import random
from datetime import datetime, timedelta, timezone

from tutorai import chat_storage, classes, db, homerooms, prompts, subjects, users

PASSWORD = "1234"
NUM_TEACHERS = 10
STUDENTS_PER_GRADE = 20  # 20 × 6 grades = 120 students total

# Only used by seed_demo_if_empty (the hosted demo's automatic setup).
DEMO_ADMIN_USERNAME = "admin_demo"
DEMO_RANDOM_SEED = 2026


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
    # Keys below are chosen so the longest-match rule in
    # _exchanges_for_subject picks the right list: "Educación Física" must
    # beat "Física", "Historia del Arte" must beat "Historia", and
    # "Modelos de Negocio" must beat "Diseño".
    # Usually French in Madrid schools; without its own key it would match
    # "Lengua Extranjera" above and get the English questions.
    "Segunda Lengua Extranjera": [
        (
            "No entiendo cuándo se usa 'avoir' y cuándo 'être' en el passé composé.",
            "Fíjate en los verbos que usan 'être': aller, venir, partir, arriver... ¿Qué tienen en común todos ellos?",
        ),
        (
            "¿Por qué en francés se dice 'je ne sais pas' con dos palabras para negar?",
            "¿Dónde se colocan 'ne' y 'pas' respecto al verbo? ¿Qué pasa con esa estructura cuando hablas de forma coloquial?",
        ),
        (
            "Me cuesta pronunciar la 'u' francesa, me sale como la española.",
            "Prueba a poner los labios como para decir 'u' y la lengua como para decir 'i'. ¿Notas la diferencia en el sonido?",
        ),
    ],
    "Educación Física": [
        (
            "No entiendo por qué tenemos que calentar antes de correr, a mí me parece perder el tiempo.",
            "¿Qué crees que les pasa a tus músculos cuando pasan de estar en reposo a hacer un esfuerzo fuerte de golpe?",
        ),
        (
            "¿Cuál es la diferencia entre resistencia aeróbica y anaeróbica? Nos lo preguntan en el examen teórico.",
            "Piensa en correr una maratón y en hacer un sprint de 100 metros. ¿En cuál de los dos podrías seguir respirando con normalidad?",
        ),
        (
            "¿Cómo se calcula la frecuencia cardíaca máxima? El profe lo dijo muy rápido.",
            "¿Crees que la frecuencia máxima de una persona de 15 años y la de una de 60 deberían ser iguales? ¿De qué crees que depende?",
        ),
    ],
    "Historia del Arte": [
        (
            "No sé distinguir una iglesia románica de una gótica, para mí son todas iguales.",
            "Fíjate en las ventanas y en la altura de los muros. ¿Cuál de los dos estilos crees que deja entrar más luz y por qué?",
        ),
        (
            "¿Por qué se dice que el Renacimiento recupera la Antigüedad clásica?",
            "¿Qué tienen en común una escultura griega y el David de Miguel Ángel en cómo representan el cuerpo humano?",
        ),
        (
            "No entiendo qué tiene de especial Las Meninas de Velázquez.",
            "¿A quién está mirando la infanta? ¿Y qué ves reflejado en el espejo del fondo de la sala?",
        ),
    ],
    "Lengua Castellana": [
        (
            "No sé cómo analizar sintácticamente esta oración: 'El perro de mi vecina ladra por las noches'.",
            "¿Cuál es el verbo principal de la oración? ¿Quién realiza esa acción?",
        ),
        (
            "¿Cuál es la diferencia entre una metáfora y un símil? Las confundo siempre.",
            "Cuando dices 'sus ojos son como estrellas', ¿qué palabra te indica que estás haciendo una comparación?",
        ),
        (
            "No entiendo de qué va el Quijote, lo he empezado y me aburre.",
            "¿Qué crees que le pasa al personaje al principio? ¿Por qué confunde molinos con gigantes?",
        ),
        (
            "¿Cuándo lleva tilde 'solo'? Cada profesor me dice una cosa.",
            "¿Qué dice la norma actual de la RAE sobre la tilde diacrítica en 'solo'? ¿Hay alguna frase en la que sin tilde no se entienda?",
        ),
    ],
    "Ciencias Aplicadas": [
        (
            "No entiendo para qué sirve el método científico si en el taller ya sabemos cómo se hacen las cosas.",
            "Si una receta de limpieza deja de funcionar, ¿cómo averiguarías qué ha cambiado sin probarlo todo a la vez?",
        ),
        (
            "¿Por qué no se pueden mezclar lejía y amoníaco? Lo pone en todas las etiquetas.",
            "¿Qué crees que puede pasar cuando dos sustancias reaccionan en un espacio cerrado? ¿Qué podría desprenderse?",
        ),
        (
            "No sé qué es un residuo peligroso y uno que no lo es.",
            "¿Qué características podría tener un residuo para que sea peligroso tirarlo a la basura normal?",
        ),
    ],
    "Computación": [
        (
            "Mi bucle while no termina nunca y no sé por qué.",
            "¿Qué condición comprueba el bucle? ¿Qué línea dentro del bucle debería hacer que esa condición acabe siendo falsa?",
        ),
        (
            "No entiendo la recursividad, ¿cómo puede una función llamarse a sí misma?",
            "Si una función se llama a sí misma con un problema un poco más pequeño cada vez, ¿qué tiene que pasar para que pare?",
        ),
        (
            "¿Qué diferencia hay entre una lista y un diccionario en Python?",
            "Si quieres guardar el teléfono de cada amigo y buscarlo por su nombre, ¿cuál de las dos estructuras te lo pone más fácil?",
        ),
    ],
    "Cultura Audiovisual": [
        (
            "No entiendo la diferencia entre un plano general y un plano medio.",
            "En un plano general, ¿cuánto del entorno ves alrededor del personaje? ¿Y en un plano medio?",
        ),
        (
            "¿Por qué los directores usan el contrapicado?",
            "Si la cámara mira a un personaje desde abajo, ¿cómo lo ves: más grande y poderoso, o más pequeño?",
        ),
        (
            "No sé qué es el montaje paralelo.",
            "Si ves alternarse a un tren que se acerca y a alguien atrapado en las vías, ¿qué sensación crea mostrar las dos escenas intercaladas?",
        ),
    ],
    "Cultura Clásica": [
        (
            "No entiendo por qué los dioses griegos se portan tan mal en los mitos.",
            "¿Qué crees que querían explicar los griegos sobre el mundo y sobre las personas dando a sus dioses defectos humanos?",
        ),
        (
            "¿Qué diferencia hay entre la democracia ateniense y la nuestra?",
            "¿Quiénes podían votar en la Atenas clásica? ¿Podían hacerlo las mujeres o los esclavos?",
        ),
        (
            "No sé por qué es tan importante la Odisea.",
            "¿Qué tipo de pruebas tiene que superar Ulises para volver a casa? ¿Qué valores crees que premia la historia?",
        ),
    ],
    "Dibujo Artístico": [
        (
            "Mis dibujos de caras siempre salen raros, los ojos me quedan muy arriba.",
            "Si mides una cabeza de la barbilla a la coronilla, ¿a qué altura crees que quedan los ojos de verdad?",
        ),
        (
            "No entiendo cómo dar volumen con el sombreado.",
            "¿De dónde viene la luz en tu modelo? ¿Qué zonas de la forma quedan más lejos de ella?",
        ),
        (
            "¿Para qué sirve hacer encaje antes de dibujar?",
            "Si empiezas por los detalles de un ojo, ¿cómo sabes que la cabeza entera va a caber bien en el papel?",
        ),
    ],
    "Dibujo Técnico": [
        (
            "No sé cómo trazar la mediatriz de un segmento con compás.",
            "¿Qué propiedad tienen todos los puntos de la mediatriz respecto a los dos extremos del segmento?",
        ),
        (
            "No entiendo el sistema diédrico, me pierdo con la planta y el alzado.",
            "Si miras una caja desde arriba y luego de frente, ¿qué medidas de la caja aparecen en cada vista?",
        ),
        (
            "¿Cómo se construye un pentágono regular inscrito en una circunferencia?",
            "¿Cuántos grados abarca cada lado del pentágono desde el centro de la circunferencia?",
        ),
    ],
    "Diseño": [
        (
            "No entiendo por qué mi cartel no se lee bien, tiene toda la información.",
            "Si alguien pasa por delante en tres segundos, ¿qué es lo primero que ve? ¿Es eso lo más importante del cartel?",
        ),
        (
            "¿Qué es la jerarquía visual?",
            "En una portada de periódico, ¿cómo sabes qué noticia es la más importante sin leer nada todavía?",
        ),
        (
            "No sé elegir colores que combinen.",
            "¿Qué sensación quieres transmitir con tu diseño: calma, energía, seriedad? ¿Qué colores asocias a esa sensación?",
        ),
    ],
    "Economía": [
        (
            "No entiendo el coste de oportunidad.",
            "Si esta tarde eliges ir al cine en lugar de trabajar en una cafetería, ¿qué estás dejando de ganar?",
        ),
        (
            "¿Por qué sube el precio cuando hay poca oferta?",
            "Si solo quedan diez entradas para un concierto y mil personas las quieren, ¿qué crees que pasaría con su precio?",
        ),
        (
            "No sé qué es la inflación ni por qué es mala.",
            "Si tu paga semanal sigue igual pero todo lo que compras cuesta un 10% más, ¿qué te pasa a ti?",
        ),
    ],
    "Plástica": [
        (
            "No entiendo qué son los colores complementarios.",
            "En el círculo cromático, ¿qué color queda justo enfrente del rojo? ¿Qué pasa si los pones juntos?",
        ),
        (
            "¿Cómo se hace la perspectiva cónica? Me salen las calles torcidas.",
            "¿Hacia dónde parecen juntarse las vías de un tren cuando miras a lo lejos?",
        ),
        (
            "No sé qué técnica usar para mi trabajo, ¿acuarela o témpera?",
            "¿Quieres un acabado transparente o colores opacos que tapen lo de debajo? ¿Qué técnica hace cada cosa?",
        ),
    ],
    "Valores Cívicos": [
        (
            "¿Por qué tengo que respetar una ley si me parece injusta?",
            "¿Qué pasaría en una sociedad si cada persona decidiera por su cuenta qué leyes cumple? ¿Qué otras vías hay para cambiar una ley?",
        ),
        (
            "No entiendo la diferencia entre igualdad y equidad.",
            "Si a tres personas de distinta altura les das la misma caja para mirar por encima de una valla, ¿ven todas el partido?",
        ),
        (
            "¿Qué son los derechos humanos y quién los decide?",
            "¿Crees que alguien tiene derecho a algo solo por ser persona, aunque su país no lo reconozca?",
        ),
    ],
    "Modelos de Negocio": [
        (
            "No entiendo el modelo Canvas, tiene demasiadas casillas.",
            "Antes de rellenar nada, ¿a quién quieres vender y qué problema concreto le resuelves?",
        ),
        (
            "¿Qué es una propuesta de valor?",
            "¿Por qué un cliente te elegiría a ti en lugar de a la competencia? ¿Qué le das que no le dan otros?",
        ),
        (
            "No sé cómo calcular si mi negocio sería rentable.",
            "¿Qué gastos tendrías cada mes aunque no vendieras nada? ¿Cuánto ganas con cada venta?",
        ),
    ],
    "Griego": [
        (
            "No sé leer el alfabeto griego, confundo la eta con la n.",
            "¿Cómo se pronuncia la letra η? ¿Hay alguna palabra en español que venga del griego y la contenga?",
        ),
        (
            "No entiendo para qué sirven los casos en griego.",
            "En español, ¿cómo sabes quién hace la acción en 'el perro muerde al gato'? ¿Y si el orden de las palabras pudiera cambiar?",
        ),
        (
            "¿Qué palabras del español vienen del griego?",
            "¿Qué crees que significa 'bio' en 'biología'? ¿Y 'logía'?",
        ),
    ],
    "Emprendedora": [
        (
            "Tengo una idea de negocio pero no sé si es buena.",
            "¿Has preguntado a posibles clientes si pagarían por ella? ¿Qué problema suyo resuelve?",
        ),
        (
            "No entiendo qué es un emprendedor social.",
            "Si una empresa gana dinero, pero su objetivo principal es resolver un problema de la comunidad, ¿en qué se diferencia de otra empresa?",
        ),
        (
            "¿Qué es el análisis DAFO?",
            "¿Qué cosas dependen de tu propio proyecto y cuáles vienen de fuera, del mercado o la competencia?",
        ),
    ],
    "Latín": [
        (
            "No sé cómo traducir 'Puella rosam amat'.",
            "¿Qué palabra está en nominativo y cuál en acusativo? ¿Qué te dice cada caso sobre quién hace qué?",
        ),
        (
            "Me lío con las declinaciones, hay demasiadas terminaciones.",
            "¿En qué termina el genitivo singular de 'rosa'? ¿Te ayuda eso a saber de qué declinación es?",
        ),
        (
            "¿Por qué hay que estudiar latín si es una lengua muerta?",
            "¿Cuántas palabras de la oración que acabas de escribir en español crees que vienen del latín?",
        ),
    ],
    "Música": [
        (
            "No entiendo cómo se lee el compás de 3/4.",
            "¿Qué te indica el número de arriba? ¿Y qué figura vale un pulso según el número de abajo?",
        ),
        (
            "¿Qué diferencia hay entre melodía y armonía?",
            "Si cantas sola una canción, ¿qué estás haciendo? ¿Y qué añade la guitarra que te acompaña tocando acordes?",
        ),
        (
            "No sé distinguir el Barroco del Clasicismo cuando escucho.",
            "¿La música que oyes tiene muchas voces entrelazándose a la vez, o una melodía clara con acompañamiento?",
        ),
    ],
    "Proyecto de Investigación": [
        (
            "No sé cómo elegir el tema de mi proyecto.",
            "¿Qué te has preguntado alguna vez que todavía no sepas responder? ¿Podrías investigarlo con lo que tienes a mano?",
        ),
        (
            "¿Cuál es la diferencia entre la pregunta de investigación y la hipótesis?",
            "Si te preguntas si el móvil afecta al sueño, ¿qué crees tú que vas a descubrir? ¿Eso es la pregunta o otra cosa?",
        ),
        (
            "No sé cómo citar las fuentes en mi trabajo.",
            "Si alguien quiere comprobar de dónde sacaste un dato, ¿qué información necesitaría para encontrarlo?",
        ),
    ],
    "Psicología": [
        (
            "No entiendo el condicionamiento clásico de Pavlov.",
            "¿Por qué crees que el perro empezaba a salivar al oír la campana, aunque todavía no viera comida?",
        ),
        (
            "¿Qué diferencia hay entre memoria a corto y a largo plazo?",
            "¿Por qué crees que te acuerdas de tu primer día de colegio, pero no del número de teléfono que te dijeron hace un minuto?",
        ),
        (
            "No sé qué es un sesgo cognitivo.",
            "¿Te ha pasado alguna vez que solo te fijabas en la información que te daba la razón? ¿Por qué crees que ocurre?",
        ),
    ],
    "Religión": [
        (
            "¿Por qué hay tantas religiones distintas?",
            "¿Qué preguntas sobre la vida y la muerte crees que intentan responder todas ellas?",
        ),
        (
            "No entiendo qué es una parábola.",
            "Cuando se cuenta la historia del buen samaritano, ¿crees que lo importante es lo que pasó o la enseñanza que transmite?",
        ),
        (
            "¿Qué tienen en común el cristianismo, el judaísmo y el islam?",
            "¿A qué figura de la Antigüedad consideran las tres religiones su antepasado común?",
        ),
    ],
    "Ingeniería": [
        (
            "No entiendo cómo funciona una palanca.",
            "Si quieres levantar una piedra muy pesada con una barra, ¿dónde pondrías el punto de apoyo para hacer menos fuerza?",
        ),
        (
            "¿Qué diferencia hay entre un circuito en serie y uno en paralelo?",
            "Si se funde una bombilla de una guirnalda en serie, ¿qué les pasa a las demás? ¿Y en paralelo?",
        ),
        (
            "No sé calcular la resistencia con la ley de Ohm.",
            "Si conoces el voltaje y la intensidad, ¿cómo los relaciona la ley de Ohm para obtener la resistencia?",
        ),
    ],
    "Digitalización": [
        (
            "No entiendo qué es el sistema binario.",
            "Si solo tuvieras dos dedos, uno levantado y otro bajado, ¿cuántas combinaciones distintas podrías hacer?",
        ),
        (
            "¿Cómo sé si una contraseña es segura?",
            "Si alguien probara todas las combinaciones posibles, ¿qué haría más difícil adivinar tu contraseña: que sea larga o que sea tu nombre?",
        ),
        (
            "No sé qué es la huella digital en internet.",
            "¿Qué información tuya crees que queda guardada cada vez que publicas una foto o das un 'me gusta'?",
        ),
    ],
    "Tutoría": [
        (
            "No sé organizarme para estudiar, siempre lo dejo todo para el último día.",
            "¿Cuántos días faltan para tu próximo examen? ¿Cómo podrías repartir el temario entre esos días?",
        ),
        (
            "Me pongo muy nervioso en los exámenes y me quedo en blanco.",
            "¿Qué haces justo antes de empezar el examen? ¿Hay algo que te ayude a calmarte en otras situaciones?",
        ),
        (
            "No sé qué bachillerato elegir.",
            "¿Qué asignaturas disfrutas de verdad, no solo las que apruebas? ¿Qué te imaginas haciendo dentro de cinco años?",
        ),
    ],
    "Volumen": [
        (
            "No entiendo la diferencia entre talla y modelado.",
            "Cuando trabajas la piedra, ¿añades material o lo quitas? ¿Y cuando trabajas con barro?",
        ),
        (
            "¿Por qué se me cae la figura de barro mientras la hago?",
            "¿Qué tiene dentro tu figura para sostenerse? ¿Cómo crees que se mantienen en pie las esculturas grandes?",
        ),
        (
            "No sé cómo hacer que mi escultura se vea bien desde todos los lados.",
            "¿Cuántas veces giras la pieza mientras trabajas? ¿Qué ves desde atrás que no veías de frente?",
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


def _seed_one_chat(username: str, link: dict) -> None:
    """Create one backdated chat for this subject link, with 2-3 different
    subject-specific questions and the tutor's Socratic replies."""
    days_ago = random.randint(0, 30)
    hours_ago = random.randint(0, 23)
    base_time = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)

    system_prompt = prompts.build_system_prompt(link["grade"], link["subject"], "es")
    chat = chat_storage.create_chat(
        username, link["grade"], link["subject"], system_prompt,
        created_at=base_time.isoformat(),
    )

    subject_exchanges = _exchanges_for_subject(link["subject"])
    num_exchanges = min(random.randint(2, 3), len(subject_exchanges))
    # sample, not choice: the same question twice in one chat looks fake.
    chosen_exchanges = random.sample(subject_exchanges, num_exchanges)
    for exchange_index, (student_line, tutor_line) in enumerate(chosen_exchanges):
        message_time = base_time + timedelta(minutes=exchange_index * 3)
        chat_storage.add_message(
            chat["id"], "user", student_line, created_at=message_time.isoformat()
        )
        chat_storage.add_message(
            chat["id"], "assistant", tutor_line,
            created_at=(message_time + timedelta(seconds=30)).isoformat(),
        )


def seed_chat_activity(student_usernames: list[str]) -> None:
    """Give every student one chat per subject they're linked to, so each
    student account opens with real-looking conversations about its own
    classes. Students who already have chats are skipped, so re-running
    this script doesn't pile up duplicate chats."""
    for username in student_usernames:
        if chat_storage.load_chats(username):
            continue

        for link in users.get_user(username)["subject_links"]:
            _seed_one_chat(username, link)


def reset_test_passwords(usernames: list[str]) -> None:
    """Force every test account's password back to PASSWORD."""
    for username in usernames:
        users.set_password(username, PASSWORD)


def seed_demo_if_empty() -> bool:
    """Fill a brand-new, empty database with the demo data: an admin, the
    test teachers and students, and every student's chats. Does nothing if
    any account already exists. Returns True if it seeded.

    Called by app.py on startup. On the hosted copy (Streamlit Community
    Cloud) the database file is wiped whenever the app restarts, so this
    is what makes every boot open with the same ready-to-explore data.
    On your own machine the database already has users, so it's a no-op.
    """
    if users.list_all_users():
        return False

    # A fixed seed makes every boot produce the identical demo data, so
    # the same students have the same classes and chats every time.
    random.seed(DEMO_RANDOM_SEED)

    users.create_admin(DEMO_ADMIN_USERNAME, PASSWORD)
    teacher_usernames = seed_teachers()
    student_usernames = seed_students(teacher_usernames)
    seed_chat_activity(student_usernames)
    return True


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
