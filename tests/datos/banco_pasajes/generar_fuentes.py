"""Genera las fuentes del banco de pasajes (``es/corpus/*.md`` y ``es/casos.yaml``).

El banco mide el orden de pasajes dentro de documentos largos y entre secciones
«hermanas» (mismo tema, distinto actor, producto o cifra). Cada documento tiene
una sección por elemento; todas siguen el mismo esqueleto:

    3 párrafos generales -> hechos tempranos -> 2 generales -> hechos tardíos -> 2 generales

Así los hechos tardíos caen en la segunda mitad de una sección de más de 300
palabras. Las frases de hecho son paralelas entre hermanas y solo cambian el
actor y la cifra, que es lo que la recuperación debe distinguir.

Es determinista: la misma ejecución produce los mismos archivos. Las fuentes
generadas se versionan; este script documenta cómo se hicieron.

    python tests/datos/banco_pasajes/generar_fuentes.py
    python tests/datos/banco_pasajes/construir.py
"""
from __future__ import annotations

from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent
SALIDA = RAIZ / "es"

# --- Párrafos generales (sin cifras ni hechos consultables) --------------------
GENERALES = [
    "Esta sección («{H}») describe las reglas aplicables y complementa lo dispuesto en las demás secciones del "
    "documento. Cuando exista una diferencia entre la regla general y la regla particular, prevalece la "
    "regla particular. Las dudas de interpretación se resuelven consultando a la unidad responsable antes de "
    "iniciar cualquier trámite.",
    "La unidad responsable mantiene un registro de las solicitudes recibidas y de su resultado. Ese registro se "
    "revisa cada semestre para detectar demoras, trámites repetidos y errores frecuentes en los formularios. Los "
    "hallazgos se informan a la dirección y se incorporan en la siguiente versión de este documento.",
    "Los formularios se encuentran en el portal interno y deben completarse en su totalidad. Un formulario "
    "incompleto, con tachaduras o sin la firma correspondiente se devuelve sin tramitar, y el plazo se cuenta "
    "desde la fecha en que se recibe la versión corregida. Se recomienda conservar una copia de cada documento "
    "presentado.",
    "Quienes necesiten orientación pueden acercarse a la oficina de atención durante el horario habitual o "
    "escribir al correo de la unidad. Las consultas se responden por orden de llegada y, salvo casos urgentes, "
    "no se atienden por teléfono. Las respuestas por correo no reemplazan la resolución formal del trámite.",
    "Las situaciones no previstas en este documento se analizan caso a caso. La unidad responsable puede pedir "
    "antecedentes adicionales, y la decisión se comunica por escrito junto con sus fundamentos. Si la persona "
    "interesada no está de acuerdo, puede pedir una revisión a la dirección dentro del período que fija el "
    "reglamento general.",
    "Toda la información entregada se trata con reserva y se usa solo para el trámite en curso. Los datos "
    "personales se conservan el tiempo que exige la normativa de archivo y después se eliminan de forma segura. "
    "Las copias impresas se resguardan en el archivo central y no pueden retirarse sin autorización.",
    "Los cambios en esta sección se publican con al menos un mes de anticipación y se comunican por correo "
    "institucional. Mientras no entre en vigencia una nueva versión, se aplica la anterior. Las solicitudes "
    "presentadas antes del cambio se resuelven con las reglas vigentes a la fecha de presentación.",
    "El incumplimiento reiterado de estas reglas puede dar lugar a una observación en el expediente de la "
    "persona. Las observaciones se eliminan después de un año sin nuevas faltas. La unidad responsable avisa "
    "con anticipación antes de registrar cualquier observación y permite presentar descargos.",
    "Cuando el trámite requiere la intervención de más de una unidad, la unidad que lo recibe coordina las "
    "gestiones y mantiene informada a la persona interesada. No es necesario presentar los mismos documentos "
    "más de una vez, siempre que se indique el número de la solicitud original.",
    "Las fechas límite que caen en día inhábil se trasladan al siguiente día hábil. Los períodos de cierre "
    "institucional, como las vacaciones de invierno y las de fin de año, no se cuentan dentro de los plazos "
    "mientras las oficinas permanezcan cerradas.",
    "Para facilitar la revisión, se pide adjuntar los documentos en formato PDF, con buena resolución y en un "
    "único archivo por solicitud. Los archivos ilegibles o que superen el tamaño permitido por el portal se "
    "devuelven para su corrección.",
    "Las capacitaciones sobre este procedimiento se realizan al inicio de cada semestre y quedan grabadas en la "
    "intranet. La asistencia es voluntaria, pero se recomienda especialmente a quienes tramitan por primera vez "
    "o han tenido solicitudes rechazadas.",
]

# --- Documentos --------------------------------------------------------------
# Cada hecho: sentencia = "<prefijo>, <resto>"; ``resp`` es el comienzo de la
# oración hasta el dato (único por sección porque incluye al sujeto).
HECHOS = "tempranos"


def _doc(archivo, titulo, intro, tema, items, hechos, propios):
    return dict(archivo=archivo, titulo=titulo, intro=intro, tema=tema, items=items, hechos=hechos, propios=propios)


DOCS = []

# 1. Reembolsos por tipo de personal ------------------------------------------
DOCS.append(_doc(
    "reglamento_reembolsos.md", "Reglamento de reembolso de gastos",
    "Este reglamento establece cómo se solicitan, aprueban y pagan los reembolsos de gastos realizados en nombre "
    "de la institución. Las reglas dependen del tipo de vínculo de la persona, por lo que cada sección trata un "
    "grupo distinto. Antes de gastar, conviene confirmar el grupo al que se pertenece.",
    "los reembolsos de gastos",
    [
        ("Personal de planta", "personal de planta", dict(a=30, b="la jefatura directa", c=10, d="350.000", m="transferencia a la cuenta de remuneraciones")),
        ("Personal a contrata", "personal a contrata", dict(a=20, b="la jefatura directa", c=12, d="250.000", m="transferencia a la cuenta de remuneraciones")),
        ("Personal a honorarios", "personal a honorarios", dict(a=15, b="la dirección administrativa", c=25, d="150.000", m="transferencia a la cuenta bancaria informada en el contrato")),
        ("Practicantes", "practicantes", dict(a=7, b="el tutor de la práctica", c=15, d="60.000", m="vale vista retirado en tesorería")),
        ("Académicos por horas", "académicos por horas", dict(a=45, b="la dirección del departamento", c=20, d="200.000", m="transferencia a la cuenta bancaria registrada en el departamento")),
        ("Personas invitadas", "personas invitadas", dict(a=10, b="la unidad que realizó la invitación", c=30, d="500.000", m="cheque nominativo emitido por tesorería")),
    ],
    [
        ("temprano", "Para {S}, la solicitud de reembolso debe presentarse dentro de {a} días hábiles desde la fecha del gasto.",
         "Para {S}, la solicitud de reembolso debe presentarse dentro de {a} días hábiles",
         "¿Cuántos días hábiles hay para presentar la solicitud de reembolso para {S}?",
         "¿hasta cuántos días después del gasto puedo pedir el reembolso si soy parte de {S}?"),
        ("temprano", "Para {S}, la solicitud la aprueba {b}.",
         "Para {S}, la solicitud la aprueba {b}",
         "¿Quién aprueba la solicitud de reembolso para {S}?",
         "¿a quién le toca aprobar mi reembolso si estoy en {S}?"),
        ("tardio", "Para {S}, el reembolso se paga en un máximo de {c} días hábiles tras la aprobación.",
         "Para {S}, el reembolso se paga en un máximo de {c} días hábiles",
         "¿En cuántos días hábiles se paga el reembolso para {S}?",
         "¿cuánto se demora en llegar la plata del reembolso para {S}?"),
        ("tardio", "Para {S}, el tope por rendición es de {d} pesos.",
         "Para {S}, el tope por rendición es de {d} pesos",
         "¿Cuál es el tope por rendición para {S}?",
         "¿cuánta plata como máximo puedo rendir en una sola vez como {S}?"),
        ("tardio", "Para {S}, el pago se realiza mediante {m}.",
         "Para {S}, el pago se realiza mediante {m}",
         "¿Cómo se paga el reembolso para {S}?",
         "¿en qué forma me depositan o pagan el reembolso si soy de {S}?"),
    ],
    [
        "Un reembolso solo procede cuando el gasto se realizó en cumplimiento de una función de la institución y se "
        "respalda con boleta o factura a nombre de la institución. Los gastos personales, las propinas y las "
        "multas no se reembolsan en ningún caso, aunque se hayan hecho durante una comisión.",
        "La rendición se arma con el formulario de reembolso, los comprobantes originales y una breve explicación "
        "del motivo de cada gasto. Los comprobantes se pegan en hojas tamaño carta, ordenados por fecha, y "
        "se entregan o se escanean según indique el portal.",
        "Si el monto rendido supera el tope vigente, la diferencia debe tramitarse como una solicitud aparte con "
        "autorización previa de la dirección administrativa. Dividir un gasto en varias rendiciones para evitar "
        "el tope se considera una falta.",
    ],
))

# 2. Garantía de equipos --------------------------------------------------------
DOCS.append(_doc(
    "garantia_equipos.md", "Política de garantía de equipos institucionales",
    "Esta política explica qué cubre la garantía de los equipos que la institución entrega a su personal y cómo "
    "se solicita el servicio. Cada tipo de equipo tiene condiciones propias, descritas en una sección distinta. "
    "Los plazos se cuentan desde la fecha de entrega registrada en el acta.",
    "la garantía de los equipos",
    [
        ("Notebooks", "notebooks", dict(n=24, c="fallas de placa, pantalla y batería", x="derrames de líquidos y golpes", s="el taller del edificio central", d=5)),
        ("Impresoras", "impresoras", dict(n=12, c="fallas del mecanismo de arrastre de papel", x="el uso de tinta o tóner no original", s="el taller del edificio de talleres", d=10)),
        ("Proyectores", "proyectores", dict(n=18, c="fallas de la placa y de la óptica", x="el desgaste de la lámpara", s="la bodega de audiovisual", d=7)),
        ("Tabletas", "tabletas", dict(n=12, c="fallas de pantalla táctil y de carga", x="pantallas quebradas por caídas", s="el taller del edificio central", d=3)),
        ("Monitores", "monitores", dict(n=36, c="píxeles defectuosos y fallas de la fuente interna", x="rayaduras en la pantalla", s="la bodega de audiovisual", d=8)),
        ("Routers", "routers", dict(n=48, c="fallas de la fuente de poder y de los puertos", x="daños por descargas eléctricas", s="la oficina de redes", d=2)),
    ],
    [
        ("temprano", "Para {S}, la garantía dura {n} meses desde la fecha de entrega.",
         "Para {S}, la garantía dura {n} meses",
         "¿Cuántos meses dura la garantía para {S}?",
         "¿por cuánto tiempo están en garantía {S}?"),
        ("temprano", "Para {S}, la garantía cubre {c}.",
         "Para {S}, la garantía cubre {c}",
         "¿Qué cubre la garantía para {S}?",
         "¿qué problemas me arreglan gratis en {S}?"),
        ("tardio", "Para {S}, la garantía no cubre {x}.",
         "Para {S}, la garantía no cubre {x}",
         "¿Qué no cubre la garantía para {S}?",
         "¿en qué casos pierdo la garantía de {S}?"),
        ("tardio", "Para {S}, el servicio técnico atiende en {s}.",
         "Para {S}, el servicio técnico atiende en {s}",
         "¿Dónde atiende el servicio técnico para {S}?",
         "¿adónde llevo a arreglar {S}?"),
        ("tardio", "Para {S}, el equipo de reemplazo se entrega en un plazo de {d} días hábiles.",
         "Para {S}, el equipo de reemplazo se entrega en un plazo de {d} días hábiles",
         "¿En cuántos días hábiles se entrega el equipo de reemplazo para {S}?",
         "¿cuánto demoran en darme otro equipo mientras reparan {S}?"),
    ],
    [
        "Para hacer efectiva la garantía, la persona debe informar la falla por el portal de soporte, indicando el "
        "número de inventario del equipo. El servicio técnico registra el ingreso y entrega un comprobante con la "
        "fecha y el diagnóstico inicial.",
        "El personal no debe abrir ni reparar los equipos por su cuenta. La manipulación interna, el cambio de "
        "piezas o la instalación de software no autorizado anulan la garantía y pueden obligar a reponer el equipo "
        "con cargo al centro de costos de la unidad.",
        "Al terminar la garantía, el equipo pasa al régimen de mantención, que se cobra al centro de costos de la "
        "unidad según el catálogo de servicios técnicos vigente. La unidad puede pedir la baja del equipo si el "
        "costo de la reparación supera la mitad de su valor.",
    ],
))

# 3. Permisos y licencias ---------------------------------------------------------
DOCS.append(_doc(
    "reglamento_permisos.md", "Reglamento de permisos y licencias del personal",
    "Este reglamento regula los permisos con goce de remuneraciones a los que tiene derecho el personal y los "
    "trámites para solicitarlos. Cada tipo de permiso tiene su propia sección, con las condiciones que lo "
    "distinguen. Los permisos no solicitados dentro de plazo pueden perderse.",
    "los permisos del personal",
    [
        ("Permiso por matrimonio", "el permiso por matrimonio", dict(a=5, p=30, doc="el certificado de matrimonio", q="la dirección de personas", d="no se descuenta")),
        ("Permiso por nacimiento de un hijo", "el permiso por nacimiento de un hijo", dict(a=5, p=15, doc="el certificado de nacimiento", q="la jefatura directa", d="no se descuenta")),
        ("Permiso por fallecimiento de un familiar", "el permiso por fallecimiento de un familiar", dict(a=7, p=2, doc="el certificado de defunción", q="la jefatura directa", d="no se descuenta")),
        ("Permiso para estudios", "el permiso para estudios", dict(a=10, p=60, doc="el certificado de matrícula", q="la dirección de personas", d="se descuenta proporcionalmente")),
        ("Permiso por enfermedad de un hijo menor", "el permiso por enfermedad de un hijo menor", dict(a=10, p=3, doc="la licencia médica del menor", q="la jefatura directa", d="no se descuenta")),
        ("Permiso para trámites personales", "el permiso para trámites personales", dict(a=3, p=5, doc="un comprobante de la gestión realizada", q="la jefatura directa", d="se descuenta de las vacaciones")),
    ],
    [
        ("temprano", "Para {S}, se otorgan {a} días de permiso por año.",
         "Para {S}, se otorgan {a} días de permiso",
         "¿Cuántos días de permiso se otorgan para {S}?",
         "¿cuántos días me dan en {S}?"),
        ("temprano", "Para {S}, la solicitud debe presentarse con {p} días de anticipación.",
         "Para {S}, la solicitud debe presentarse con {p} días de anticipación",
         "¿Con cuántos días de anticipación se solicita {S}?",
         "¿con cuánta anticipación tengo que pedir {S}?"),
        ("tardio", "Para {S}, se exige como respaldo {doc}.",
         "Para {S}, se exige como respaldo {doc}",
         "¿Qué documento se exige como respaldo para {S}?",
         "¿qué papel tengo que llevar para {S}?"),
        ("tardio", "Para {S}, el permiso lo autoriza {q}.",
         "Para {S}, el permiso lo autoriza {q}",
         "¿Quién autoriza {S}?",
         "¿quién tiene que dar el visto bueno para {S}?"),
        ("tardio", "Para {S}, el tiempo de permiso {d}.",
         "Para {S}, el tiempo de permiso {d}",
         "¿Se descuenta el tiempo de permiso en {S}?",
         "¿me descuentan el sueldo por {S}?"),
    ],
    [
        "Los permisos se solicitan por el portal de personas, adjuntando el formulario firmado por la jefatura. La "
        "dirección de personas confirma la recepción por correo y registra el permiso en el sistema de asistencia.",
        "Los días de permiso se cuentan en días corridos, salvo que la sección indique lo contrario. Un permiso que "
        "comienza en un día inhábil se cuenta desde el siguiente día hábil, y no pueden acumularse permisos de "
        "distinto tipo en el mismo período sin autorización expresa.",
        "El permiso no utilizado dentro del año calendario no se acumula ni se compensa en dinero. Quien cambie de "
        "unidad conserva los días pendientes, y la nueva jefatura recibe un informe con el saldo al momento del "
        "traslado.",
    ],
))

# 4. Compras por rango de monto -----------------------------------------------------
DOCS.append(_doc(
    "manual_compras.md", "Manual de compras y contrataciones",
    "Este manual define cómo se compran bienes y servicios según el monto. A mayor monto, más cotizaciones y "
    "más niveles de aprobación. Cada modalidad de compra se explica en una sección con las exigencias que le "
    "corresponden.",
    "las compras",
    [
        ("Compras menores", "compras menores", dict(m=10, b="la jefatura de la unidad", k=1, p=3, doc="la boleta o factura")),
        ("Compras directas", "compras directas", dict(m=100, b="la dirección administrativa", k=2, p=7, doc="la orden de compra firmada")),
        ("Cotización formal", "cotización formal", dict(m=500, b="la dirección administrativa", k=3, p=15, doc="el cuadro comparativo de cotizaciones")),
        ("Licitación privada", "licitación privada", dict(m=1000, b="el comité de compras", k=3, p=30, doc="el acta de evaluación de ofertas")),
        ("Licitación pública", "licitación pública", dict(m=5000, b="el comité de compras", k=5, p=60, doc="las bases de licitación aprobadas")),
        ("Compras de emergencia", "compras de emergencia", dict(m=300, b="la rectoría", k=1, p=2, doc="el informe de justificación de la emergencia")),
    ],
    [
        ("temprano", "Para {S}, el monto máximo es de {m} UF.",
         "Para {S}, el monto máximo es de {m} UF",
         "¿Cuál es el monto máximo para {S}?",
         "¿hasta cuántas UF puedo gastar en {S}?"),
        ("temprano", "Para {S}, la compra la aprueba {b}.",
         "Para {S}, la compra la aprueba {b}",
         "¿Quién aprueba la compra en {S}?",
         "¿quién firma las {S}?"),
        ("tardio", "Para {S}, se exigen como mínimo {k} cotizaciones.",
         "Para {S}, se exigen como mínimo {k} cotizaciones",
         "¿Cuántas cotizaciones se exigen como mínimo para {S}?",
         "¿cuántas cotizaciones tengo que juntar en {S}?"),
        ("tardio", "Para {S}, el plazo máximo del proceso es de {p} días hábiles.",
         "Para {S}, el plazo máximo del proceso es de {p} días hábiles",
         "¿Cuál es el plazo máximo del proceso para {S}?",
         "¿cuánto se demora todo el trámite en {S}?"),
        ("tardio", "Para {S}, el documento de cierre es {doc}.",
         "Para {S}, el documento de cierre es {doc}",
         "¿Cuál es el documento de cierre para {S}?",
         "¿qué papel cierra el trámite de {S}?"),
    ],
    [
        "Antes de iniciar cualquier compra, la unidad debe verificar que existe presupuesto disponible en su centro "
        "de costos. La dirección administrativa puede rechazar solicitudes sin disponibilidad, aunque cumplan el "
        "resto de las exigencias de este manual.",
        "Los proveedores deben estar inscritos en el registro institucional y no tener deudas tributarias ni "
        "sanciones vigentes. La inscripción se renueva cada año presentando los antecedentes legales y "
        "tributarios actualizados.",
        "Está prohibido dividir una compra en varias para quedar bajo un umbral. La dirección administrativa "
        "revisa mensualmente las compras repetidas al mismo proveedor y puede reclasificarlas en la modalidad "
        "que corresponda al monto total.",
    ],
))

# 5. Laboratorios -------------------------------------------------------------------------
DOCS.append(_doc(
    "protocolo_laboratorios.md", "Protocolo de uso de laboratorios",
    "Este protocolo fija las condiciones de seguridad y uso de los laboratorios de la institución. Cada "
    "laboratorio tiene riesgos distintos, por lo que sus reglas se describen en secciones separadas. Todo "
    "usuario debe leer la sección del laboratorio antes de su primera visita.",
    "los laboratorios",
    [
        ("Laboratorio de química", "el laboratorio de química", dict(a=20, e="delantal, antiparras y guantes de nitrilo", r="la técnica de laboratorio de química", h="8:30 a 18:00", p=48)),
        ("Laboratorio de biología", "el laboratorio de biología", dict(a=24, e="delantal, mascarilla y guantes de látex", r="el encargado de bioseguridad", h="8:00 a 17:30", p=72)),
        ("Laboratorio de física", "el laboratorio de física", dict(a=30, e="calzado cerrado y lentes de seguridad", r="el ayudante de laboratorio de física", h="9:00 a 19:00", p=24)),
        ("Laboratorio de electrónica", "el laboratorio de electrónica", dict(a=18, e="pulsera antiestática y lentes de seguridad", r="el técnico electrónico", h="9:00 a 20:00", p=24)),
        ("Laboratorio de cómputo", "el laboratorio de cómputo", dict(a=40, e="ninguno, pero se prohíbe ingresar alimentos", r="el administrador de redes", h="8:00 a 22:00", p=12)),
        ("Laboratorio de materiales", "el laboratorio de materiales", dict(a=15, e="casco, calzado de seguridad y protectores auditivos", r="el ingeniero de mantención", h="8:30 a 17:00", p=96)),
    ],
    [
        ("temprano", "Para {S}, el aforo máximo es de {a} personas.",
         "Para {S}, el aforo máximo es de {a} personas",
         "¿Cuál es el aforo máximo en {S}?",
         "¿cuánta gente puede entrar en {S} al mismo tiempo?"),
        ("temprano", "Para {S}, el horario de atención es de {h} horas.",
         "Para {S}, el horario de atención es de {h} horas",
         "¿Cuál es el horario de atención en {S}?",
         "¿a qué hora abre y cierra {S}?"),
        ("tardio", "Para {S}, el equipo de protección obligatorio incluye {e}.",
         "Para {S}, el equipo de protección obligatorio incluye {e}",
         "¿Qué equipo de protección es obligatorio en {S}?",
         "¿qué tengo que llevar puesto para entrar en {S}?"),
        ("tardio", "Para {S}, el responsable de la seguridad es {r}.",
         "Para {S}, el responsable de la seguridad es {r}",
         "¿Quién es el responsable de la seguridad en {S}?",
         "¿con quién hablo si hay un problema en {S}?"),
        ("tardio", "Para {S}, la reserva debe hacerse con {p} horas de anticipación.",
         "Para {S}, la reserva debe hacerse con {p} horas de anticipación",
         "¿Con cuántas horas de anticipación se reserva {S}?",
         "¿con cuánto tiempo antes tengo que reservar {S}?"),
    ],
    [
        "Nadie puede trabajar solo en un laboratorio fuera del horario de atención. Las excepciones requieren una "
        "autorización escrita del responsable y el aviso previo a la guardia de seguridad, que registra la hora de "
        "entrada y de salida.",
        "Los residuos se separan según las instrucciones de cada laboratorio y se depositan en los contenedores "
        "rotulados. Nunca se vierten sustancias por el desagüe sin autorización. Los residuos peligrosos los retira "
        "una empresa externa autorizada una vez al mes.",
        "Todo accidente, aunque parezca menor, se informa de inmediato al responsable y se registra en el libro de "
        "incidentes del laboratorio. Los botiquines y las duchas de emergencia se revisan cada mes y su estado queda "
        "anotado en una lista de verificación.",
    ],
))

# 6. Viajes ----------------------------------------------------------------------------------
DOCS.append(_doc(
    "politica_viajes.md", "Política de viajes y viáticos",
    "Esta política establece cómo se solicitan y financian los viajes por trabajo. Las condiciones cambian "
    "según el tipo de viaje, y cada una se detalla en su propia sección. Ningún viaje puede iniciarse sin "
    "la autorización correspondiente.",
    "los viajes",
    [
        ("Viajes nacionales en bus", "viajes nacionales en bus", dict(a=5, v="45.000", b="la jefatura directa", s="seguro de accidentes personales", r=10)),
        ("Viajes nacionales en avión", "viajes nacionales en avión", dict(a=10, v="65.000", b="la dirección administrativa", s="seguro de accidentes personales y de equipaje", r=10)),
        ("Viajes internacionales", "viajes internacionales", dict(a=30, v="180 dólares", b="la vicerrectoría", s="seguro de asistencia en viaje con cobertura médica", r=15)),
        ("Congresos y seminarios", "congresos y seminarios", dict(a=45, v="120 dólares", b="la dirección de investigación", s="seguro de asistencia en viaje con cobertura médica", r=20)),
        ("Comisiones de servicio de un día", "comisiones de servicio de un día", dict(a=3, v="25.000", b="la jefatura directa", s="seguro de accidentes personales", r=5)),
        ("Trabajo en terreno", "trabajo en terreno", dict(a=15, v="55.000", b="la dirección del departamento", s="seguro de accidentes personales con cobertura rural", r=7)),
    ],
    [
        ("temprano", "Para {S}, la solicitud debe presentarse con {a} días hábiles de anticipación.",
         "Para {S}, la solicitud debe presentarse con {a} días hábiles de anticipación",
         "¿Con cuántos días hábiles de anticipación se solicita {S}?",
         "¿con cuánto tiempo antes tengo que pedir el viaje en {S}?"),
        ("temprano", "Para {S}, el viático diario es de {v} pesos o su equivalente.",
         "Para {S}, el viático diario es de {v}",
         "¿De cuánto es el viático diario para {S}?",
         "¿cuánta plata me dan por día en {S}?"),
        ("tardio", "Para {S}, el viaje lo autoriza {b}.",
         "Para {S}, el viaje lo autoriza {b}",
         "¿Quién autoriza {S}?",
         "¿a quién le pido el visto bueno para {S}?"),
        ("tardio", "Para {S}, la institución contrata un {s}.",
         "Para {S}, la institución contrata un {s}",
         "¿Qué seguro contrata la institución para {S}?",
         "¿qué seguro me ponen cuando salgo en {S}?"),
        ("tardio", "Para {S}, la rendición del viaje debe entregarse dentro de {r} días hábiles al regreso.",
         "Para {S}, la rendición del viaje debe entregarse dentro de {r} días hábiles",
         "¿En cuántos días hábiles debe entregarse la rendición para {S}?",
         "¿cuántos días tengo para rendir al volver de {S}?"),
    ],
    [
        "Los pasajes los compra la institución a través de la agencia contratada. No se reembolsan pasajes "
        "comprados por la propia persona, salvo que la agencia no pueda atender la solicitud y la dirección "
        "administrativa lo autorice por escrito.",
        "Los viáticos cubren alimentación, transporte local y alojamiento básico. Cuando la institución paga el "
        "alojamiento o las comidas directamente, el viático se reduce en la proporción que fija la tabla anexa de "
        "descuentos.",
        "Quien viaja debe dejar informada su ruta y un contacto de emergencia en la unidad. Los cambios de "
        "itinerario se avisan de inmediato a la jefatura, y los gastos derivados de cambios no autorizados quedan "
        "a cargo de la persona.",
    ],
))

# --- Gemelos: se definen a mano con frases explícitas para mantener la redacción natural ---
GEM = {
    "biblioteca": {
        "titulo": "Reglamento de biblioteca de la Facultad de {U}",
        "intro": "Este reglamento regula el uso de la biblioteca de la Facultad de {U}. Cada servicio se describe en su propia sección, con las condiciones vigentes para estudiantes y personal de la facultad.",
        "tema": "los servicios de la biblioteca",
        "secciones": [
            ("Préstamo de libros", "el préstamo de libros",
             [("temprano", "En la Facultad de {U}, el préstamo de libros dura {a} días corridos.", "En la Facultad de {U}, el préstamo de libros dura {a} días corridos",
               "¿Cuántos días dura el préstamo de libros en la Facultad de {U}?", "¿por cuántos días puedo llevarme un libro de la biblioteca de {U}?"),
              ("tardio", "En la Facultad de {U}, cada estudiante puede renovar un libro hasta {b} veces.", "En la Facultad de {U}, cada estudiante puede renovar un libro hasta {b} veces",
               "¿Cuántas veces se puede renovar un libro en la Facultad de {U}?", "¿cuántas renovaciones me dejan hacer de un libro en la biblioteca de {U}?")]),
            ("Préstamo de notebooks", "el préstamo de notebooks",
             [("temprano", "En la Facultad de {U}, el préstamo de notebooks se otorga por {a} horas.", "En la Facultad de {U}, el préstamo de notebooks se otorga por {a} horas",
               "¿Por cuántas horas se presta un notebook en la Facultad de {U}?", "¿cuántas horas me dejan usar un notebook de la biblioteca de {U}?"),
              ("tardio", "En la Facultad de {U}, el depósito en garantía por un notebook es de {b} pesos.", "En la Facultad de {U}, el depósito en garantía por un notebook es de {b} pesos",
               "¿De cuánto es el depósito en garantía por un notebook en la Facultad de {U}?", "¿cuánta plata dejo en garantía por un notebook en la biblioteca de {U}?")]),
            ("Salas de estudio", "las salas de estudio",
             [("temprano", "En la Facultad de {U}, las salas de estudio se reservan por bloques de {a} horas.", "En la Facultad de {U}, las salas de estudio se reservan por bloques de {a} horas",
               "¿De cuántas horas son los bloques de reserva de salas de estudio en la Facultad de {U}?", "¿por cuántas horas puedo reservar una sala de estudio en la biblioteca de {U}?"),
              ("tardio", "En la Facultad de {U}, la reserva de una sala se pierde tras {b} minutos de atraso.", "En la Facultad de {U}, la reserva de una sala se pierde tras {b} minutos de atraso",
               "¿Cuántos minutos de atraso hacen perder la reserva de una sala en la Facultad de {U}?", "¿cuánto me puedo atrasar antes de que me quiten la sala en la biblioteca de {U}?")]),
            ("Multas por atraso", "las multas por atraso",
             [("temprano", "En la Facultad de {U}, la multa por atraso es de {a} pesos por día y por libro.", "En la Facultad de {U}, la multa por atraso es de {a} pesos por día y por libro",
               "¿De cuánto es la multa diaria por atraso en la Facultad de {U}?", "¿cuánto cobran por día de atraso con un libro en la biblioteca de {U}?"),
              ("tardio", "En la Facultad de {U}, la multa acumulada se suspende al llegar a {b} pesos.", "En la Facultad de {U}, la multa acumulada se suspende al llegar a {b} pesos",
               "¿En qué monto se suspende la multa acumulada en la Facultad de {U}?", "¿hasta cuánto puede subir la multa total en la biblioteca de {U}?")]),
            ("Reserva de material", "la reserva de material",
             [("temprano", "En la Facultad de {U}, el material reservado se guarda durante {a} días hábiles.", "En la Facultad de {U}, el material reservado se guarda durante {a} días hábiles",
               "¿Cuántos días hábiles se guarda el material reservado en la Facultad de {U}?", "¿cuánto tiempo me guardan un libro reservado en la biblioteca de {U}?"),
              ("tardio", "En la Facultad de {U}, cada persona puede mantener hasta {b} reservas activas.", "En la Facultad de {U}, cada persona puede mantener hasta {b} reservas activas",
               "¿Cuántas reservas activas se permiten por persona en la Facultad de {U}?", "¿cuántas reservas puedo tener a la vez en la biblioteca de {U}?")]),
        ],
        "valores": {
            "Ciencias": [dict(a=14, b=2), dict(a=3, b="50.000"), dict(a=2, b=15), dict(a="300", b="6.000"), dict(a=5, b=3)],
            "Ingeniería": [dict(a=21, b=3), dict(a=4, b="80.000"), dict(a=3, b=10), dict(a="500", b="10.000"), dict(a=7, b=5)],
        },
    },
    "titulacion": {
        "titulo": "Reglamento de titulación de la Facultad de {U}",
        "intro": "Este reglamento describe las etapas del proceso de titulación en la Facultad de {U}. Cada etapa tiene su propia sección, con plazos, responsables y requisitos.",
        "tema": "el proceso de titulación",
        "secciones": [
            ("Inscripción del tema", "la inscripción del tema",
             [("temprano", "En la Facultad de {U}, el tema de titulación se inscribe ante {a}.", "En la Facultad de {U}, el tema de titulación se inscribe ante {a}",
               "¿Ante quién se inscribe el tema de titulación en la Facultad de {U}?", "¿adónde tengo que ir a inscribir mi tema de título en la facultad de {U}?"),
              ("tardio", "En la Facultad de {U}, el tema inscrito tiene una vigencia de {b} meses.", "En la Facultad de {U}, el tema inscrito tiene una vigencia de {b} meses",
               "¿Cuántos meses de vigencia tiene el tema inscrito en la Facultad de {U}?", "¿cuánto dura inscrito mi tema de título en la facultad de {U}?")]),
            ("Comisión evaluadora", "la comisión evaluadora",
             [("temprano", "En la Facultad de {U}, la comisión evaluadora la integran {a} profesores.", "En la Facultad de {U}, la comisión evaluadora la integran {a} profesores",
               "¿Cuántos profesores integran la comisión evaluadora en la Facultad de {U}?", "¿cuántos profesores hay en mi comisión de título en la facultad de {U}?"),
              ("tardio", "En la Facultad de {U}, la comisión se constituye dentro de {b} días hábiles desde la inscripción.", "En la Facultad de {U}, la comisión se constituye dentro de {b} días hábiles",
               "¿En cuántos días hábiles se constituye la comisión en la Facultad de {U}?", "¿cuánto se demoran en armar la comisión en la facultad de {U}?")]),
            ("Defensa", "la defensa",
             [("temprano", "En la Facultad de {U}, la defensa se rinde ante la comisión en un máximo de {a} minutos de exposición.", "En la Facultad de {U}, la defensa se rinde ante la comisión en un máximo de {a} minutos de exposición",
               "¿Cuántos minutos de exposición tiene la defensa en la Facultad de {U}?", "¿cuánto tiempo tengo para exponer mi defensa en la facultad de {U}?"),
              ("tardio", "En la Facultad de {U}, la nota mínima para aprobar la defensa es {b}.", "En la Facultad de {U}, la nota mínima para aprobar la defensa es {b}",
               "¿Cuál es la nota mínima para aprobar la defensa en la Facultad de {U}?", "¿con qué nota apruebo la defensa en la facultad de {U}?")]),
            ("Entrega final", "la entrega final",
             [("temprano", "En la Facultad de {U}, la versión final del trabajo se entrega dentro de {a} días hábiles tras la defensa.", "En la Facultad de {U}, la versión final del trabajo se entrega dentro de {a} días hábiles",
               "¿En cuántos días hábiles se entrega la versión final después de la defensa en la Facultad de {U}?", "¿cuántos días tengo para entregar la versión final en la facultad de {U}?"),
              ("tardio", "En la Facultad de {U}, el trabajo final se entrega en {b} ejemplares impresos.", "En la Facultad de {U}, el trabajo final se entrega en {b} ejemplares impresos",
               "¿Cuántos ejemplares impresos del trabajo final se entregan en la Facultad de {U}?", "¿cuántas copias impresas tengo que dejar en la facultad de {U}?")]),
            ("Certificado de título", "el certificado de título",
             [("temprano", "En la Facultad de {U}, el certificado de título se emite en {a} días hábiles.", "En la Facultad de {U}, el certificado de título se emite en {a} días hábiles",
               "¿En cuántos días hábiles se emite el certificado de título en la Facultad de {U}?", "¿cuánto demoran en darme el certificado de título en la facultad de {U}?"),
              ("tardio", "En la Facultad de {U}, el certificado de título cuesta {b} pesos.", "En la Facultad de {U}, el certificado de título cuesta {b} pesos",
               "¿Cuánto cuesta el certificado de título en la Facultad de {U}?", "¿cuánta plata hay que pagar por el certificado de título en la facultad de {U}?")]),
        ],
        "valores": {
            "Ciencias": [dict(a="la coordinación de titulación", b=12), dict(a=3, b=20), dict(a=30, b="5,0"), dict(a=15, b=4), dict(a=10, b="8.000")],
            "Ingeniería": [dict(a="la jefatura de carrera", b=18), dict(a=5, b=30), dict(a=40, b="5,5"), dict(a=20, b=2), dict(a=15, b="12.000")],
        },
    },
}


def _seccion(h2, S, pre_idx, pool, tema, tempranos, tardios, vals, extra_unidad=None):
    """Compone una sección: 3 generales, hechos tempranos, 2 generales, hechos tardíos, 2 generales."""
    fmt = dict(vals)
    fmt["S"] = S
    fmt["H"] = h2
    fmt["t"] = tema
    if extra_unidad:
        fmt["U"] = extra_unidad
    n = len(pool)
    gen = [pool[(pre_idx * 3 + k) % n].format(**fmt) for k in range(7)]
    parrafos = [gen[0], gen[1], gen[2]]
    parrafos.append(" ".join(f["sent"].format(**fmt) for f in tempranos))
    parrafos += [gen[3], gen[4]]
    parrafos.append(" ".join(f["sent"].format(**fmt) for f in tardios))
    parrafos += [gen[5], gen[6]]
    return "## " + h2 + "\n\n" + "\n\n".join(parrafos) + "\n"


def _normalizar_hechos(hechos):
    out = []
    for fase, sent, resp, q, p in hechos:
        out.append(dict(fase=fase, sent=sent, resp=resp, q=q, p=p))
    return out


def construir_documento(titulo, intro, tema, secciones, pool, propios, unidad=None):
    """secciones: lista de (h2, S, hechos_normalizados, vals)."""
    partes = ["# " + titulo + "\n", intro + "\n"]
    for i, (h2, S, hechos, vals) in enumerate(secciones):
        tem = [h for h in hechos if h["fase"] == "temprano"]
        tar = [h for h in hechos if h["fase"] == "tardio"]
        # Los párrafos propios del documento se mezclan con los generales.
        grupo = list(propios) + pool
        partes.append(_seccion(h2, S, i, grupo, tema, tem, tar, vals, unidad))
    return "\n".join(partes)



TRAMPAS = [
    ("reglamento_reembolsos.md", "¿Cuál es el tope por rendición para voluntarios?"),
    ("reglamento_reembolsos.md", "¿Cuál es el viático diario para practicantes?"),
    ("reglamento_reembolsos.md", "¿Cuántos días hábiles tienen los practicantes para apelar el rechazo de un reembolso?"),
    ("garantia_equipos.md", "¿Cuántos meses dura la garantía para teléfonos celulares?"),
    ("garantia_equipos.md", "¿Qué cubre la garantía para escáneres?"),
    ("garantia_equipos.md", "¿Dónde atiende el servicio técnico para servidores?"),
    ("reglamento_permisos.md", "¿Cuántos días de permiso se otorgan para el permiso por cambio de domicilio?"),
    ("reglamento_permisos.md", "¿Quién autoriza el permiso por mudanza?"),
    ("manual_compras.md", "¿Cuál es el monto máximo para compras de arriendo de inmuebles?"),
    ("manual_compras.md", "¿Cuántas cotizaciones se exigen como mínimo para compras internacionales?"),
    ("protocolo_laboratorios.md", "¿Cuál es el aforo máximo en el laboratorio de astronomía?"),
    ("protocolo_laboratorios.md", "¿Qué equipo de protección es obligatorio en el laboratorio de geología?"),
    ("politica_viajes.md", "¿De cuánto es el viático diario para viajes nacionales en tren?"),
    ("politica_viajes.md", "¿Con cuántos días hábiles de anticipación se solicita un viaje en barco?"),
    ("reglamento_biblioteca_ciencias.md", "¿Cuántos días dura el préstamo de libros en la Facultad de Medicina?"),
]


def _dar_formato(plantilla, S, vals, U):
    fmt = dict(vals)
    fmt["S"] = S
    if U:
        fmt["U"] = U
    return plantilla.format(**fmt)


def generar_casos(casos_spec) -> list[dict]:
    """Elige las preguntas de forma determinista a partir de los hechos."""
    por_doc: dict[str, list] = {}
    for archivo, h2, S, hechos, vals, U in casos_spec:
        por_doc.setdefault(archivo, []).append((h2, S, hechos, vals, U))
    principales = [d["archivo"] for d in DOCS]
    gemelos = [a for a in por_doc if a not in principales]
    usados: set = set()
    casos: list[dict] = []

    def agregar(clase, archivo, item, idx, variante):
        h2, S, hechos, vals, U = por_doc[archivo][item]
        h = hechos[idx]
        usados.add((archivo, item, idx))
        casos.append(dict(
            clase=clase, documento=archivo, seccion=h2,
            pregunta=_dar_formato(h[variante], S, vals, U),
            respuesta=_dar_formato(h["resp"], S, vals, U),
            fase=h["fase"],
        ))

    # 42 de la segunda mitad: hechos tardíos de los 6 documentos principales.
    for archivo in principales:
        for k in range(7):
            item = k % 6
            tardios = [i for i, h in enumerate(por_doc[archivo][item][2]) if h["fase"] == "tardio"]
            agregar("segunda", archivo, item, tardios[(k + k // 6) % len(tardios)], "q")
    # 36 hermanas en los principales (hechos tempranos) y 16 en los gemelos.
    for archivo in principales:
        for k in range(6):
            tempranos = [i for i, h in enumerate(por_doc[archivo][k][2]) if h["fase"] == "temprano"]
            agregar("hermana", archivo, k, tempranos[k % len(tempranos)], "q")
    for archivo in gemelos:
        for k in range(5):
            if k == 1:
                continue
            fases = [i for i, h in enumerate(por_doc[archivo][k][2])]
            agregar("hermana", archivo, k, fases[(k + len(archivo)) % len(fases)], "q")
    # 22 paráfrasis informales: hechos que aún no tienen pregunta.
    for archivo in principales:
        quedan = [(it, i) for it in range(6) for i in range(len(por_doc[archivo][it][2]))
                  if (archivo, it, i) not in usados]
        for it, i in quedan[::7][:3]:
            agregar("parafrasis", archivo, it, i, "p")
    for archivo in gemelos:
        quedan = [(it, i) for it in range(5) for i in range(2) if (archivo, it, i) not in usados]
        agregar("parafrasis", archivo, *quedan[0], "p")

    # Contadores por clase y trampas emparejadas con una hermana del mismo documento.
    n = {}
    for c in casos:
        n[c["clase"]] = n.get(c["clase"], 0) + 1
        c["id"] = f"es-{c['clase']}-{n[c['clase']]:03d}"
    hermanas = {}
    for c in casos:
        if c["clase"] == "hermana":
            hermanas.setdefault(c["documento"], c["id"])
    for j, (archivo, pregunta) in enumerate(TRAMPAS, 1):
        casos.append(dict(id=f"es-trampa-{j:03d}", clase="trampa", documento=archivo, par=hermanas[archivo],
                          pregunta=pregunta))
    return casos


def main() -> None:
    corpus = SALIDA / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    casos_spec = []

    for d in DOCS:
        hechos = _normalizar_hechos(d["hechos"])
        secciones = [(h2, S, hechos, vals) for h2, S, vals in d["items"]]
        texto = construir_documento(d["titulo"], d["intro"], d["tema"], secciones, GENERALES, d["propios"])
        (corpus / d["archivo"]).write_text(texto, encoding="utf-8")
        for h2, S, vals in d["items"]:
            casos_spec.append((d["archivo"], h2, S, hechos, vals, None))

    for clave, g in GEM.items():
        for unidad in ("Ciencias", "Ingeniería"):
            archivo = f"reglamento_{clave}_{'ciencias' if unidad == 'Ciencias' else 'ingenieria'}.md"
            secciones = []
            for (h2, S, hs), vals in zip(g["secciones"], g["valores"][unidad]):
                secciones.append((h2, S, _normalizar_hechos(hs), vals))
            texto = construir_documento(g["titulo"].format(U=unidad), g["intro"].format(U=unidad), g["tema"],
                                        secciones, GENERALES, [], unidad)
            (corpus / archivo).write_text(texto, encoding="utf-8")
            for h2, S, hechos, vals in secciones:
                casos_spec.append((archivo, h2, S, hechos, vals, unidad))

    casos = generar_casos(casos_spec)
    cabecera = ("# Banco de pasajes (fuente generada por generar_fuentes.py). La clase sale del id: segunda,\n"
                "# hermana, parafrasis y trampa. construir.py calcula evidencias, offsets y particiones.\n")
    cuerpo = yaml.safe_dump(
        [{k: v for k, v in c.items() if k != "fase"} for c in casos],
        allow_unicode=True, sort_keys=False, width=1000)
    (SALIDA / "casos.yaml").write_text(cabecera + cuerpo, encoding="utf-8")


if __name__ == "__main__":
    main()
