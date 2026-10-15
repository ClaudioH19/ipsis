"""Passage bank content in English: same documents, facts and figures as the Spanish bank.

Formal questions (``q``) and informal ones (``p``, the way people type in a chat window).
Consumed by ``generar_fuentes.py``.
"""
from __future__ import annotations

IDIOMA = "en"
UNIDADES = ("Science", "Engineering")


def _doc(archivo, titulo, intro, tema, items, hechos, propios):
    return dict(archivo=archivo, titulo=titulo, intro=intro, tema=tema, items=items, hechos=hechos, propios=propios)


GENERALES = [
    "This section («{H}») describes the applicable rules and complements the other sections of the "
    "document. When the general rule and the particular rule differ, the particular rule prevails. Questions of "
    "interpretation are settled by asking the responsible unit before starting any procedure.",
    "The responsible unit keeps a record of the requests received and of their outcome. That record is reviewed "
    "every semester to detect delays, repeated procedures and frequent mistakes in the forms. The findings are "
    "reported to management and included in the next version of this document.",
    "The forms are available on the internal portal and must be filled in completely. A form that is incomplete, "
    "has crossings-out or lacks the corresponding signature is returned unprocessed, and the deadline is counted "
    "from the date the corrected version is received. Keeping a copy of every submitted document is recommended.",
    "Anyone who needs guidance can visit the help desk during regular hours or write to the unit's email "
    "address. Questions are answered in order of arrival and, except in urgent cases, are not handled by "
    "phone. Answers sent by email do not replace the formal resolution of the procedure.",
    "Situations not covered by this document are analyzed case by case. The responsible unit may ask for "
    "additional information, and the decision is communicated in writing together with its grounds. A person "
    "who disagrees may ask management for a review within the period set by the general regulations.",
    "All the information provided is treated confidentially and used only for the procedure at hand. Personal "
    "data is kept for as long as the archiving rules require and then securely deleted. Paper copies are kept "
    "in the central archive and may not be removed without authorization.",
    "Changes to this section are published at least one month in advance and announced by institutional email. "
    "Until a new version takes effect, the previous one applies. Requests submitted before a change are "
    "resolved under the rules in force on the date of submission.",
    "Repeated failure to follow these rules may lead to a note in the person's file. Notes are removed after a "
    "year without further breaches. The responsible unit gives advance notice before recording any note and "
    "allows the person to respond.",
    "When a procedure requires more than one unit, the unit that receives it coordinates the steps and keeps "
    "the person informed. The same documents do not have to be submitted more than once, as long as the number "
    "of the original request is given.",
    "Deadlines that fall on a non-working day move to the next working day. Institutional closures, such as the "
    "winter and year-end breaks, do not count toward deadlines while the offices remain closed.",
    "To make the review easier, documents should be attached as PDF files, in good resolution and in a single "
    "file per request. Files that are unreadable or exceed the size allowed by the portal are returned for "
    "correction.",
    "Training sessions on this procedure are held at the start of each semester and recorded on the intranet. "
    "Attendance is voluntary, but it is especially recommended for people filing for the first time or whose "
    "requests have been rejected.",
]

DOCS = []

# 1. Reimbursements by type of staff -----------------------------------------------------------
DOCS.append(_doc(
    "reimbursement_rules.md", "Expense Reimbursement Rules",
    "These rules establish how expenses incurred on behalf of the institution are claimed, approved and paid. "
    "The rules depend on the person's type of employment, so each section covers a different group. Before "
    "spending, confirm which group you belong to.",
    "expense reimbursements",
    [
        ("Permanent staff", "permanent staff", dict(a=30, b="the direct supervisor", c=10, d="350,000", m="bank transfer to the payroll account")),
        ("Contract staff", "contract staff", dict(a=20, b="the direct supervisor", c=12, d="250,000", m="bank transfer to the payroll account")),
        ("Fee-based staff", "fee-based staff", dict(a=15, b="the administrative office", c=25, d="150,000", m="bank transfer to the account named in the contract")),
        ("Interns", "interns", dict(a=7, b="the internship tutor", c=15, d="60,000", m="a cashier's check collected at the treasury")),
        ("Hourly lecturers", "hourly lecturers", dict(a=45, b="the department head", c=20, d="200,000", m="bank transfer to the account registered with the department")),
        ("Invited guests", "invited guests", dict(a=10, b="the unit that issued the invitation", c=30, d="500,000", m="a check issued by the treasury")),
    ],
    [
        ("temprano", "For {S}, the reimbursement request must be submitted within {a} business days of the expense date.",
         "For {S}, the reimbursement request must be submitted within {a} business days",
         "How many business days are there to submit the reimbursement request for {S}?",
         "how long after buying something can i ask for the refund if im {S}?"),
        ("temprano", "For {S}, the request is approved by {b}.",
         "For {S}, the request is approved by {b}",
         "Who approves the reimbursement request for {S}?",
         "who has to sign off my refund if im {S}?"),
        ("tardio", "For {S}, the reimbursement is paid within a maximum of {c} business days after approval.",
         "For {S}, the reimbursement is paid within a maximum of {c} business days",
         "Within how many business days is the reimbursement paid for {S}?",
         "how long does the money take to arrive for {S}?"),
        ("tardio", "For {S}, the limit per expense report is {d} pesos.",
         "For {S}, the limit per expense report is {d} pesos",
         "What is the limit per expense report for {S}?",
         "whats the max amount i can claim at once as {S}?"),
        ("tardio", "For {S}, payment is made by {m}.",
         "For {S}, payment is made by {m}",
         "How is the reimbursement paid for {S}?",
         "how do they pay me the refund if im {S}?"),
    ],
    [
        "A reimbursement applies only when the expense was incurred in the course of a duty for the institution and "
        "is backed by a receipt or invoice issued to the institution. Personal expenses, tips and fines are never "
        "reimbursed, even if incurred during an assignment.",
        "The expense report consists of the reimbursement form, the original receipts and a short explanation of "
        "the reason for each expense. Receipts are glued on letter-size sheets, in date order, and handed in or "
        "scanned as the portal indicates.",
        "If the amount claimed exceeds the current limit, the difference must be filed as a separate request with "
        "prior authorization from the administrative office. Splitting an expense across several reports to avoid "
        "the limit is considered a breach.",
    ],
))

# 2. Equipment warranty -------------------------------------------------------------------------
DOCS.append(_doc(
    "equipment_warranty.md", "Institutional Equipment Warranty Policy",
    "This policy explains what the warranty covers for the equipment the institution gives its staff and how "
    "to request service. Each type of equipment has its own conditions, described in a separate section. "
    "Deadlines are counted from the delivery date recorded in the handover record.",
    "the equipment warranty",
    [
        ("Laptops", "laptops", dict(n=24, c="motherboard, screen and battery failures", x="liquid spills and impact damage", s="the workshop in the main building", d=5)),
        ("Printers", "printers", dict(n=12, c="paper-feed mechanism failures", x="the use of non-original ink or toner", s="the workshop in the services building", d=10)),
        ("Projectors", "projectors", dict(n=18, c="board and optics failures", x="lamp wear", s="the audiovisual storeroom", d=7)),
        ("Tablets", "tablets", dict(n=12, c="touch screen and charging failures", x="screens broken by drops", s="the workshop in the main building", d=3)),
        ("Monitors", "monitors", dict(n=36, c="dead pixels and internal power supply failures", x="scratches on the screen", s="the audiovisual storeroom", d=8)),
        ("Routers", "routers", dict(n=48, c="power supply and port failures", x="damage caused by power surges", s="the networks office", d=2)),
    ],
    [
        ("temprano", "For {S}, the warranty lasts {n} months from the delivery date.",
         "For {S}, the warranty lasts {n} months",
         "How many months does the warranty last for {S}?",
         "how long are {S} under warranty?"),
        ("temprano", "For {S}, the warranty covers {c}.",
         "For {S}, the warranty covers {c}",
         "What does the warranty cover for {S}?",
         "what problems get fixed for free on {S}?"),
        ("tardio", "For {S}, the warranty does not cover {x}.",
         "For {S}, the warranty does not cover {x}",
         "What does the warranty not cover for {S}?",
         "when do i lose the warranty on {S}?"),
        ("tardio", "For {S}, technical service is provided at {s}.",
         "For {S}, technical service is provided at {s}",
         "Where is technical service provided for {S}?",
         "where do i take {S} to get them fixed?"),
        ("tardio", "For {S}, the replacement unit is delivered within {d} business days.",
         "For {S}, the replacement unit is delivered within {d} business days",
         "Within how many business days is the replacement unit delivered for {S}?",
         "how long until they give me another one while {S} get repaired?"),
    ],
    [
        "To claim the warranty, the person must report the failure through the support portal, giving the "
        "equipment's inventory number. Technical service logs the intake and issues a receipt with the date and "
        "the initial diagnosis.",
        "Staff must not open or repair the equipment on their own. Internal tampering, replacing parts or "
        "installing unauthorized software voids the warranty and may require replacing the equipment at the "
        "expense of the unit's cost center.",
        "When the warranty ends, the equipment moves to the maintenance regime, charged to the unit's cost center "
        "according to the current technical services catalog. The unit may request that the equipment be written "
        "off if the cost of repair exceeds half of its value.",
    ],
))

# 3. Leave and permits ------------------------------------------------------------------------------
DOCS.append(_doc(
    "leave_rules.md", "Staff Leave and Permit Rules",
    "These rules govern the paid leave to which staff are entitled and the procedures to request it. Each "
    "type of leave has its own section, with the conditions that distinguish it. Leave not requested on time "
    "may be lost.",
    "staff leave",
    [
        ("Marriage leave", "marriage leave", dict(a=5, p=30, doc="the marriage certificate", q="the people office", d="is not deducted")),
        ("Leave for the birth of a child", "leave for the birth of a child", dict(a=5, p=15, doc="the birth certificate", q="the direct supervisor", d="is not deducted")),
        ("Bereavement leave", "bereavement leave", dict(a=7, p=2, doc="the death certificate", q="the direct supervisor", d="is not deducted")),
        ("Study leave", "study leave", dict(a=10, p=60, doc="the enrollment certificate", q="the people office", d="is deducted proportionally")),
        ("Leave for the illness of a young child", "leave for the illness of a young child", dict(a=10, p=3, doc="the child's medical certificate", q="the direct supervisor", d="is not deducted")),
        ("Leave for personal errands", "leave for personal errands", dict(a=3, p=5, doc="proof of the errand carried out", q="the direct supervisor", d="is deducted from vacation days")),
    ],
    [
        ("temprano", "For {S}, {a} days of leave are granted per year.",
         "For {S}, {a} days of leave are granted",
         "How many days of leave are granted for {S}?",
         "how many days do i get for {S}?"),
        ("temprano", "For {S}, the request must be submitted {p} days in advance.",
         "For {S}, the request must be submitted {p} days in advance",
         "How many days in advance must {S} be requested?",
         "how early do i have to ask for {S}?"),
        ("tardio", "For {S}, the required supporting document is {doc}.",
         "For {S}, the required supporting document is {doc}",
         "What supporting document is required for {S}?",
         "what paper do i have to bring for {S}?"),
        ("tardio", "For {S}, the leave is authorized by {q}.",
         "For {S}, the leave is authorized by {q}",
         "Who authorizes {S}?",
         "who has to approve {S}?"),
        ("tardio", "For {S}, the time off {d}.",
         "For {S}, the time off {d}",
         "Is the time off deducted for {S}?",
         "do they take money off my pay for {S}?"),
    ],
    [
        "Leave is requested through the people portal, attaching the form signed by the supervisor. The people "
        "office confirms receipt by email and records the leave in the attendance system.",
        "Days of leave are counted as calendar days unless the section says otherwise. Leave that begins on a "
        "non-working day is counted from the next working day, and leave of different types may not be combined "
        "in the same period without express authorization.",
        "Leave not used within the calendar year is neither carried over nor paid out. A person who changes units "
        "keeps the pending days, and the new supervisor receives a report with the balance at the time of the "
        "transfer.",
    ],
))

# 4. Purchasing by amount ---------------------------------------------------------------------------
DOCS.append(_doc(
    "purchasing_manual.md", "Purchasing and Procurement Manual",
    "This manual defines how goods and services are bought according to the amount. The higher the amount, the "
    "more quotes and the more levels of approval. Each purchasing method is explained in a section with the "
    "requirements that apply to it.",
    "purchases",
    [
        ("Small purchases", "small purchases", dict(m=10, b="the unit head", k=1, p=3, doc="the receipt or invoice")),
        ("Direct purchases", "direct purchases", dict(m=100, b="the administrative office", k=2, p=7, doc="the signed purchase order")),
        ("Formal quotation", "formal quotation purchases", dict(m=500, b="the administrative office", k=3, p=15, doc="the quote comparison table")),
        ("Private tender", "private tenders", dict(m=1000, b="the purchasing committee", k=3, p=30, doc="the bid evaluation record")),
        ("Public tender", "public tenders", dict(m=5000, b="the purchasing committee", k=5, p=60, doc="the approved tender terms")),
        ("Emergency purchases", "emergency purchases", dict(m=300, b="the president's office", k=1, p=2, doc="the emergency justification report")),
    ],
    [
        ("temprano", "For {S}, the maximum amount is {m} UF.",
         "For {S}, the maximum amount is {m} UF",
         "What is the maximum amount for {S}?",
         "up to how many UF can i spend on {S}?"),
        ("temprano", "For {S}, the purchase is approved by {b}.",
         "For {S}, the purchase is approved by {b}",
         "Who approves the purchase for {S}?",
         "who signs off {S}?"),
        ("tardio", "For {S}, at least {k} quotes are required.",
         "For {S}, at least {k} quotes are required",
         "How many quotes are required as a minimum for {S}?",
         "how many quotes do i need to collect for {S}?"),
        ("tardio", "For {S}, the maximum duration of the process is {p} business days.",
         "For {S}, the maximum duration of the process is {p} business days",
         "What is the maximum duration of the process for {S}?",
         "how long does the whole process take for {S}?"),
        ("tardio", "For {S}, the closing document is {doc}.",
         "For {S}, the closing document is {doc}",
         "What is the closing document for {S}?",
         "what paper closes the process for {S}?"),
    ],
    [
        "Before starting any purchase, the unit must check that its cost center has an available budget. The "
        "administrative office may reject requests without funds even if they meet the other requirements of "
        "this manual.",
        "Suppliers must be registered in the institutional register and must not have tax debts or active "
        "sanctions. Registration is renewed every year by submitting the updated legal and tax documents.",
        "Splitting a purchase into several to stay under a threshold is forbidden. The administrative office "
        "reviews repeated purchases from the same supplier every month and may reclassify them under the method "
        "that corresponds to the total amount.",
    ],
))

# 5. Laboratories -------------------------------------------------------------------------------------
DOCS.append(_doc(
    "laboratory_protocol.md", "Laboratory Use Protocol",
    "This protocol sets the safety and use conditions of the institution's laboratories. Each laboratory has "
    "different risks, so its rules are described in separate sections. Every user must read the section for "
    "the laboratory before their first visit.",
    "the laboratories",
    [
        ("Chemistry laboratory", "the chemistry laboratory", dict(a=20, e="a lab coat, goggles and nitrile gloves", r="the chemistry lab technician", h="8:30 to 18:00", p=48)),
        ("Biology laboratory", "the biology laboratory", dict(a=24, e="a lab coat, a mask and latex gloves", r="the biosafety officer", h="8:00 to 17:30", p=72)),
        ("Physics laboratory", "the physics laboratory", dict(a=30, e="closed shoes and safety glasses", r="the physics lab assistant", h="9:00 to 19:00", p=24)),
        ("Electronics laboratory", "the electronics laboratory", dict(a=18, e="an antistatic wristband and safety glasses", r="the electronics technician", h="9:00 to 20:00", p=24)),
        ("Computing laboratory", "the computing laboratory", dict(a=40, e="nothing, but food is not allowed inside", r="the network administrator", h="8:00 to 22:00", p=12)),
        ("Materials laboratory", "the materials laboratory", dict(a=15, e="a helmet, safety shoes and ear protection", r="the maintenance engineer", h="8:30 to 17:00", p=96)),
    ],
    [
        ("temprano", "For {S}, the maximum occupancy is {a} people.",
         "For {S}, the maximum occupancy is {a} people",
         "What is the maximum occupancy of {S}?",
         "how many people can be in {S} at the same time?"),
        ("temprano", "For {S}, the opening hours are {h}.",
         "For {S}, the opening hours are {h}",
         "What are the opening hours of {S}?",
         "what time does {S} open and close?"),
        ("tardio", "For {S}, the mandatory protective equipment includes {e}.",
         "For {S}, the mandatory protective equipment includes {e}",
         "What protective equipment is mandatory in {S}?",
         "what do i have to wear to go into {S}?"),
        ("tardio", "For {S}, the person responsible for safety is {r}.",
         "For {S}, the person responsible for safety is {r}",
         "Who is responsible for safety in {S}?",
         "who do i talk to if theres a problem in {S}?"),
        ("tardio", "For {S}, bookings must be made {p} hours in advance.",
         "For {S}, bookings must be made {p} hours in advance",
         "How many hours in advance must {S} be booked?",
         "how far ahead do i need to book {S}?"),
    ],
    [
        "Nobody may work alone in a laboratory outside opening hours. Exceptions require written authorization "
        "from the person responsible and prior notice to the security guard, who records the entry and exit "
        "times.",
        "Waste is sorted according to each laboratory's instructions and placed in the labeled containers. "
        "Substances are never poured down the drain without authorization. Hazardous waste is collected once a "
        "month by an authorized outside company.",
        "Every accident, however minor it seems, is reported immediately to the person responsible and entered in "
        "the laboratory's incident book. First-aid kits and emergency showers are checked every month and their "
        "condition is noted on a checklist.",
    ],
))

# 6. Travel ----------------------------------------------------------------------------------------------
DOCS.append(_doc(
    "travel_policy.md", "Travel and Per Diem Policy",
    "This policy sets out how work travel is requested and funded. The conditions change with the type of "
    "trip, and each one is detailed in its own section. No trip may begin without the corresponding "
    "authorization.",
    "travel",
    [
        ("Domestic bus trips", "domestic bus trips", dict(a=5, v="45,000", b="the direct supervisor", s="personal accident insurance", r=10)),
        ("Domestic flights", "domestic flights", dict(a=10, v="65,000", b="the administrative office", s="personal accident and baggage insurance", r=10)),
        ("International trips", "international trips", dict(a=30, v="180 dollars", b="the vice presidency", s="travel assistance insurance with medical coverage", r=15)),
        ("Conferences and seminars", "conferences and seminars", dict(a=45, v="120 dollars", b="the research office", s="travel assistance insurance with medical coverage", r=20)),
        ("One-day service assignments", "one-day service assignments", dict(a=3, v="25,000", b="the direct supervisor", s="personal accident insurance", r=5)),
        ("Fieldwork", "fieldwork", dict(a=15, v="55,000", b="the department head", s="personal accident insurance with rural coverage", r=7)),
    ],
    [
        ("temprano", "For {S}, the request must be submitted {a} business days in advance.",
         "For {S}, the request must be submitted {a} business days in advance",
         "How many business days in advance must the request be submitted for {S}?",
         "how early do i have to ask for approval for {S}?"),
        ("temprano", "For {S}, the daily per diem is {v} pesos or its equivalent.",
         "For {S}, the daily per diem is {v}",
         "What is the daily per diem for {S}?",
         "how much money do i get per day for {S}?"),
        ("tardio", "For {S}, the trip is authorized by {b}.",
         "For {S}, the trip is authorized by {b}",
         "Who authorizes {S}?",
         "who do i ask for the ok on {S}?"),
        ("tardio", "For {S}, the institution contracts {s}.",
         "For {S}, the institution contracts {s}",
         "What insurance does the institution contract for {S}?",
         "what insurance do they give me for {S}?"),
        ("tardio", "For {S}, the trip expense report must be submitted within {r} business days of returning.",
         "For {S}, the trip expense report must be submitted within {r} business days",
         "Within how many business days must the expense report be submitted for {S}?",
         "how many days do i have to file my expenses after {S}?"),
    ],
    [
        "Tickets are bought by the institution through the contracted agency. Tickets bought by the person are not "
        "reimbursed, unless the agency cannot handle the request and the administrative office authorizes it in "
        "writing.",
        "Per diems cover food, local transport and basic lodging. When the institution pays for lodging or meals "
        "directly, the per diem is reduced in the proportion set by the attached table of deductions.",
        "Travelers must leave their route and an emergency contact with the unit. Itinerary changes are reported "
        "to the supervisor immediately, and costs arising from unauthorized changes are borne by the person.",
    ],
))

GEM = {
    "biblioteca": {
        "archivos": {"Science": "library_rules_science.md", "Engineering": "library_rules_engineering.md"},
        "titulo": "Library Rules of the Faculty of {U}",
        "intro": "These rules govern the use of the library of the Faculty of {U}. Each service is described in its own section, with the conditions currently in force for students and faculty staff.",
        "tema": "the library services",
        "secciones": [
            ("Book loans", "book loans",
             [("temprano", "In the Faculty of {U}, a book loan lasts {a} calendar days.", "In the Faculty of {U}, a book loan lasts {a} calendar days",
               "How many days does a book loan last in the Faculty of {U}?", "how many days can i take a book home from the {U} library?"),
              ("tardio", "In the Faculty of {U}, each student can renew a book up to {b} times.", "In the Faculty of {U}, each student can renew a book up to {b} times",
               "How many times can a book be renewed in the Faculty of {U}?", "how many renewals do they let me do on a book at the {U} library?")]),
            ("Laptop loans", "laptop loans",
             [("temprano", "In the Faculty of {U}, a laptop is lent for {a} hours.", "In the Faculty of {U}, a laptop is lent for {a} hours",
               "For how many hours is a laptop lent in the Faculty of {U}?", "how many hours can i use a laptop from the {U} library?"),
              ("tardio", "In the Faculty of {U}, the security deposit for a laptop is {b} pesos.", "In the Faculty of {U}, the security deposit for a laptop is {b} pesos",
               "How much is the security deposit for a laptop in the Faculty of {U}?", "how much money do i leave as a deposit for a laptop at the {U} library?")]),
            ("Study rooms", "study rooms",
             [("temprano", "In the Faculty of {U}, study rooms are booked in blocks of {a} hours.", "In the Faculty of {U}, study rooms are booked in blocks of {a} hours",
               "How long are the booking blocks for study rooms in the Faculty of {U}?", "for how many hours can i book a study room at the {U} library?"),
              ("tardio", "In the Faculty of {U}, a room booking is lost after {b} minutes of delay.", "In the Faculty of {U}, a room booking is lost after {b} minutes of delay",
               "How many minutes of delay make you lose a room booking in the Faculty of {U}?", "how late can i be before they take my room away at the {U} library?")]),
            ("Late fines", "late fines",
             [("temprano", "In the Faculty of {U}, the late fine is {a} pesos per day and per book.", "In the Faculty of {U}, the late fine is {a} pesos per day and per book",
               "How much is the daily late fine in the Faculty of {U}?", "how much do they charge per day if a book is late at the {U} library?"),
              ("tardio", "In the Faculty of {U}, the accumulated fine stops growing at {b} pesos.", "In the Faculty of {U}, the accumulated fine stops growing at {b} pesos",
               "At what amount does the accumulated fine stop in the Faculty of {U}?", "whats the most the total fine can get to at the {U} library?")]),
            ("Material reservations", "material reservations",
             [("temprano", "In the Faculty of {U}, reserved material is held for {a} business days.", "In the Faculty of {U}, reserved material is held for {a} business days",
               "How many business days is reserved material held in the Faculty of {U}?", "how long do they keep a reserved book for me at the {U} library?"),
              ("tardio", "In the Faculty of {U}, each person can keep up to {b} active reservations.", "In the Faculty of {U}, each person can keep up to {b} active reservations",
               "How many active reservations are allowed per person in the Faculty of {U}?", "how many reservations can i have at once at the {U} library?")]),
        ],
        "valores": {
            "Science": [dict(a=14, b=2), dict(a=3, b="50,000"), dict(a=2, b=15), dict(a="300", b="6,000"), dict(a=5, b=3)],
            "Engineering": [dict(a=21, b=3), dict(a=4, b="80,000"), dict(a=3, b=10), dict(a="500", b="10,000"), dict(a=7, b=5)],
        },
    },
    "titulacion": {
        "archivos": {"Science": "graduation_rules_science.md", "Engineering": "graduation_rules_engineering.md"},
        "titulo": "Graduation Rules of the Faculty of {U}",
        "intro": "These rules describe the stages of the graduation process in the Faculty of {U}. Each stage has its own section, with deadlines, responsible parties and requirements.",
        "tema": "the graduation process",
        "secciones": [
            ("Topic registration", "topic registration",
             [("temprano", "In the Faculty of {U}, the graduation topic is registered with {a}.", "In the Faculty of {U}, the graduation topic is registered with {a}",
               "Who is the graduation topic registered with in the Faculty of {U}?", "where do i go to register my thesis topic in the faculty of {U}?"),
              ("tardio", "In the Faculty of {U}, a registered topic is valid for {b} months.", "In the Faculty of {U}, a registered topic is valid for {b} months",
               "How many months is a registered topic valid in the Faculty of {U}?", "how long does my registered thesis topic last in the faculty of {U}?")]),
            ("Examining committee", "the examining committee",
             [("temprano", "In the Faculty of {U}, the examining committee has {a} professors.", "In the Faculty of {U}, the examining committee has {a} professors",
               "How many professors make up the examining committee in the Faculty of {U}?", "how many professors are on my thesis committee in the faculty of {U}?"),
              ("tardio", "In the Faculty of {U}, the committee is formed within {b} business days of registration.", "In the Faculty of {U}, the committee is formed within {b} business days",
               "Within how many business days is the committee formed in the Faculty of {U}?", "how long do they take to put the committee together in the faculty of {U}?")]),
            ("Defense", "the defense",
             [("temprano", "In the Faculty of {U}, the defense is given before the committee in a maximum of {a} minutes of presentation.", "In the Faculty of {U}, the defense is given before the committee in a maximum of {a} minutes of presentation",
               "How many minutes of presentation does the defense have in the Faculty of {U}?", "how much time do i get to present my defense in the faculty of {U}?"),
              ("tardio", "In the Faculty of {U}, the minimum grade to pass the defense is {b}.", "In the Faculty of {U}, the minimum grade to pass the defense is {b}",
               "What is the minimum grade to pass the defense in the Faculty of {U}?", "what grade do i need to pass the defense in the faculty of {U}?")]),
            ("Final submission", "the final submission",
             [("temprano", "In the Faculty of {U}, the final version of the work is submitted within {a} business days after the defense.", "In the Faculty of {U}, the final version of the work is submitted within {a} business days",
               "Within how many business days is the final version submitted after the defense in the Faculty of {U}?", "how many days do i have to hand in the final version in the faculty of {U}?"),
              ("tardio", "In the Faculty of {U}, the final work is submitted in {b} printed copies.", "In the Faculty of {U}, the final work is submitted in {b} printed copies",
               "How many printed copies of the final work are submitted in the Faculty of {U}?", "how many printed copies do i have to leave in the faculty of {U}?")]),
            ("Degree certificate", "the degree certificate",
             [("temprano", "In the Faculty of {U}, the degree certificate is issued in {a} business days.", "In the Faculty of {U}, the degree certificate is issued in {a} business days",
               "In how many business days is the degree certificate issued in the Faculty of {U}?", "how long do they take to give me the degree certificate in the faculty of {U}?"),
              ("tardio", "In the Faculty of {U}, the degree certificate costs {b} pesos.", "In the Faculty of {U}, the degree certificate costs {b} pesos",
               "How much does the degree certificate cost in the Faculty of {U}?", "how much do i have to pay for the degree certificate in the faculty of {U}?")]),
        ],
        "valores": {
            "Science": [dict(a="the graduation coordination office", b=12), dict(a=3, b=20), dict(a=30, b="5.0"), dict(a=15, b=4), dict(a=10, b="8,000")],
            "Engineering": [dict(a="the program head", b=18), dict(a=5, b=30), dict(a=40, b="5.5"), dict(a=20, b=2), dict(a=15, b="12,000")],
        },
    },
}

TRAMPAS = [
    ("reimbursement_rules.md", "What is the limit per expense report for volunteers?"),
    ("reimbursement_rules.md", "What is the daily per diem for interns?"),
    ("reimbursement_rules.md", "How many business days do interns have to appeal the rejection of a reimbursement?"),
    ("equipment_warranty.md", "How many months does the warranty last for cell phones?"),
    ("equipment_warranty.md", "What does the warranty cover for scanners?"),
    ("equipment_warranty.md", "Where is technical service provided for servers?"),
    ("leave_rules.md", "How many days of leave are granted for leave for moving house?"),
    ("leave_rules.md", "Who authorizes leave for a house move?"),
    ("purchasing_manual.md", "What is the maximum amount for property rental purchases?"),
    ("purchasing_manual.md", "How many quotes are required as a minimum for international purchases?"),
    ("laboratory_protocol.md", "What is the maximum occupancy of the astronomy laboratory?"),
    ("laboratory_protocol.md", "What protective equipment is mandatory in the geology laboratory?"),
    ("travel_policy.md", "What is the daily per diem for domestic train trips?"),
    ("travel_policy.md", "How many business days in advance must a ship trip be requested?"),
    ("library_rules_science.md", "How many days does a book loan last in the Faculty of Medicine?"),
]
