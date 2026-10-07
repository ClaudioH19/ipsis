"""Ejemplos independientes de los bancos; inserción que conserva sus comentarios."""
from pathlib import Path
import json

RAIZ = Path(__file__).resolve().parents[4]
EJEMPLOS = {
    "es": {
        "umbral": ["¿A partir de qué edad se permite entrar al museo?", "¿Cuál es el límite de peso del equipaje?", "¿Qué importe mínimo activa el descuento?", "¿Desde cuántas personas se considera un grupo?", "¿Qué temperatura máxima soporta el horno?"],
        "inicio": ["¿Qué tiene que pasar para que arranque la inscripción?", "¿Cuándo comienza la temporada de pesca?", "¿A partir de cuándo entra en vigor la norma?", "¿En qué momento puedo empezar a usar el abono?", "¿Qué da inicio al periodo de matrícula?"],
        "fin": ["¿En qué fecha se acaba la promoción?", "¿Hasta cuándo sigue vigente el permiso?", "¿Cuándo deja de ser válido el cupón?", "¿En qué momento termina la convocatoria?", "¿Cuál es el último día para inscribirse?"],
        "consecuencia": ["¿Qué ocurre si llego tarde a la función?", "¿Qué pasa cuando se interrumpe el suministro?", "¿Qué sucede si el paquete llega dañado?", "¿Cuál es el efecto de cancelar la reserva?", "¿Y si falta la firma en el formulario?"],
        "responsable": ["¿Qué persona revisa las reservas del hotel?", "¿Quién se encarga del mantenimiento del ascensor?", "¿A qué oficina corresponde emitir el certificado?", "¿Quién autoriza el acceso al laboratorio?", "¿De quién es la responsabilidad de actualizar el registro?"],
        "requisito": ["¿Qué documentos debo llevar para renovar el permiso?", "¿Qué condiciones tengo que cumplir para obtener una beca?", "¿Qué hace falta para inscribirse en el taller?", "¿Cuáles son los requisitos para adoptar un animal?", "¿Qué debo presentar para acreditar mi residencia?"],
        "procedimiento": ["¿Cómo tramito una devolución en la tienda?", "¿Qué pasos debo seguir para reservar una sala?", "¿De qué manera se registra un visitante?", "¿Cuál es el procedimiento para cambiar una cita?", "Se perdió mi carné, ¿cómo consigo otro?"],
    },
    "en": {
        "umbral": ["At what age can someone enter the museum?", "What is the luggage weight limit?", "What minimum amount qualifies for the discount?", "How many people are needed to count as a group?", "What is the maximum temperature the oven can withstand?"],
        "inicio": ["What needs to happen before enrolment can start?", "When does the fishing season begin?", "From when does the rule take effect?", "At what point can I start using the pass?", "What triggers the start of the registration period?"],
        "fin": ["On what date does the promotion end?", "Until when is the permit valid?", "When does the coupon stop being valid?", "At what point does the call for applications close?", "What is the last day to sign up?"],
        "consecuencia": ["What happens if I arrive late for the show?", "What occurs when the supply is interrupted?", "What happens if the parcel arrives damaged?", "What is the effect of cancelling the booking?", "And if the form has no signature?"],
        "responsable": ["Which person reviews the hotel bookings?", "Who is in charge of maintaining the lift?", "Which office is responsible for issuing the certificate?", "Who authorises access to the laboratory?", "Whose responsibility is it to update the register?"],
        "requisito": ["What documents must I bring to renew the permit?", "What conditions must I meet to obtain a scholarship?", "What is needed to enrol in the workshop?", "What are the requirements for adopting an animal?", "What must I provide to prove my residence?"],
        "procedimiento": ["How do I arrange a return at the shop?", "What steps should I follow to book a room?", "In what way is a visitor registered?", "What is the procedure for changing an appointment?", "I lost my membership card, how do I get another one?"],
    },
    "pt": {
        "umbral": ["A partir de que idade é permitido entrar no museu?", "Qual é o limite de peso da bagagem?", "Que valor mínimo dá direito ao desconto?", "A partir de quantas pessoas se considera um grupo?", "Qual é a temperatura máxima que o forno suporta?"],
        "inicio": ["O que precisa acontecer para que a inscrição comece?", "Quando começa a temporada de pesca?", "A partir de quando a norma entra em vigor?", "Em que momento posso começar a usar o passe?", "O que dá início ao período de matrícula?"],
        "fin": ["Em que data acaba a promoção?", "Até quando a licença continua válida?", "Quando o cupom deixa de ser válido?", "Em que momento termina a chamada para inscrições?", "Qual é o último dia para se inscrever?"],
        "consecuencia": ["O que acontece se eu chegar atrasado ao espetáculo?", "O que ocorre quando o fornecimento é interrompido?", "O que acontece se a encomenda chegar danificada?", "Qual é o efeito de cancelar a reserva?", "E se faltar a assinatura no formulário?"],
        "responsable": ["Que pessoa revisa as reservas do hotel?", "Quem é responsável pela manutenção do elevador?", "A que setor cabe emitir o certificado?", "Quem autoriza o acesso ao laboratório?", "De quem é a responsabilidade de atualizar o cadastro?"],
        "requisito": ["Que documentos devo levar para renovar a licença?", "Que condições preciso cumprir para obter uma bolsa?", "O que é necessário para se inscrever na oficina?", "Quais são os requisitos para adotar um animal?", "O que devo apresentar para comprovar minha residência?"],
        "procedimiento": ["Como solicito uma devolução na loja?", "Que passos devo seguir para reservar uma sala?", "De que maneira se cadastra um visitante?", "Qual é o procedimento para mudar uma consulta?", "Perdi minha carteirinha, como consigo outra?"],
    },
}


if __name__ == "__main__":
    for idioma, intenciones in EJEMPLOS.items():
        ruta = RAIZ / f"ipsis/recursos/idiomas/{idioma}.yaml"
        texto = ruta.read_text(encoding="utf-8")
        if "respaldo_intencion:" in texto:
            raise ValueError(f"{ruta}: ejemplos ya insertados")
        for nombre, ejemplos in intenciones.items():
            ancla = f"  {nombre}:\n    patrones:"
            assert texto.count(ancla) == 1, ancla
            bloque = "\n".join("    - " + json.dumps(e, ensure_ascii=False) for e in ejemplos)
            texto = texto.replace(ancla, f"  {nombre}:\n    ejemplos:\n{bloque}\n    patrones:")
        # Inactivo hasta medir los umbrales con dev, sin tocar la política de respuestas.
        texto = texto.replace("intenciones:\n", "respaldo_intencion:\n  intfloat/multilingual-e5-small:\n    similitud: 0.999\n    margen: 1.0\nintenciones:\n", 1)
        ruta.write_text(texto, encoding="utf-8", newline="\n")
