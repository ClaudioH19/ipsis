"""Segunda colección de formas de preguntar, sin copiar preguntas de los bancos."""
from pathlib import Path
import json
import shutil

RAIZ = Path(__file__).resolve().parents[4]
EXTRA = {
    "es": {
        "umbral": ["¿Qué cantidad máxima de entradas puedo reservar?", "¿Cuál es el mínimo de asistentes para abrir el taller?", "¿Cuánto debe superar el ingreso para pagar ese impuesto?", "¿Por debajo de qué temperatura se detiene el aparato?", "¿Desde qué valor se exige una declaración?"],
        "inicio": ["¿Qué fecha marca el inicio de la campaña?", "¿Cuándo me activan la suscripción?", "¿Cuándo se habilita el acceso a la piscina?", "¿Desde qué momento rige la cobertura?", "¿En qué momento dan comienzo las clases?"],
        "fin": ["¿Cada cuánto caduca el pase de visitante?", "¿Con qué frecuencia vence el permiso de conducir?", "¿Cuándo tengo que renovar la licencia porque vence?", "¿En qué fecha deja de funcionar la tarjeta?", "¿Cuándo finaliza la vigencia del abono?"],
        "consecuencia": ["¿Qué me sucede por incumplir la inscripción?", "¿Qué resultado tiene rechazar la invitación?", "¿Qué efectos trae no entregar la declaración?", "¿Qué medidas toman cuando se pierde la llave?", "¿Cómo afecta que falte un documento?"],
        "responsable": ["¿A quién le toca revisar el inventario?", "¿Quién tiene la tarea de abrir la sala?", "¿Qué entidad se ocupa de cobrar la matrícula?", "¿Quién lleva el control de las visitas?", "¿A cargo de quién está la reserva del alojamiento?"],
        "requisito": ["¿Qué se exige para que acepten la inscripción?", "¿Qué antecedentes hacen falta para postular?", "¿Qué características debe tener una foto válida?", "¿Cuántas páginas como mínimo debe tener el informe?", "¿Cuáles son las condiciones para recibir el permiso?"],
        "procedimiento": ["Olvidé mi código de acceso, ¿cómo lo recupero?", "No encuentro mi carné, ¿qué hago para recuperarlo?", "Me cancelaron la reserva, ¿qué hago ahora?", "Necesito cambiar mis datos, ¿cómo lo tramito?", "¿De qué forma consigo un duplicado de la credencial?"],
    },
    "en": {
        "umbral": ["What is the maximum number of tickets I can book?", "What is the minimum attendance needed to open the workshop?", "Above what income must that tax be paid?", "Below which temperature does the device stop?", "From what value is a declaration required?"],
        "inicio": ["Which date marks the start of the campaign?", "When will my subscription be activated?", "When is access to the pool enabled?", "From which moment does the coverage apply?", "At which point do classes commence?"],
        "fin": ["How often does the visitor pass expire?", "How frequently does the driving permit expire?", "When must I renew the licence because it expires?", "On which date does the card stop working?", "When does the season ticket cease to be valid?"],
        "consecuencia": ["What happens to me for failing to complete registration?", "What is the outcome of rejecting the invitation?", "What are the effects of not submitting the declaration?", "What measures are taken when a key is lost?", "How does a missing document affect the application?"],
        "responsable": ["Whose job is it to review the inventory?", "Who has the task of opening the room?", "Which organisation handles collecting tuition?", "Who keeps track of visits?", "Whose responsibility is booking the accommodation?"],
        "requisito": ["What is demanded for registration to be accepted?", "What supporting information is necessary to apply?", "What characteristics must a valid photo have?", "How many pages at minimum must the report contain?", "What conditions apply to receiving the permit?"],
        "procedimiento": ["I forgot my access code, how do I recover it?", "I cannot find my membership card, what do I do to recover it?", "My booking was cancelled, what do I do now?", "I need to change my details, how is that arranged?", "In what way can I obtain a duplicate credential?"],
    },
    "pt": {
        "umbral": ["Qual é a quantidade máxima de ingressos que posso reservar?", "Qual é o mínimo de participantes para abrir a oficina?", "Acima de que renda é preciso pagar esse imposto?", "Abaixo de que temperatura o aparelho para?", "A partir de que valor se exige uma declaração?"],
        "inicio": ["Que data marca o início da campanha?", "Quando minha assinatura será ativada?", "Quando é liberado o acesso à piscina?", "Desde que momento vale a cobertura?", "Em que momento as aulas têm início?"],
        "fin": ["A cada quanto tempo vence o passe de visitante?", "Com que frequência vence a licença para dirigir?", "Quando preciso renovar a licença porque vence?", "Em que data o cartão deixa de funcionar?", "Quando termina a validade do passe mensal?"],
        "consecuencia": ["O que ocorre comigo por não concluir a inscrição?", "Qual é o resultado de rejeitar o convite?", "Quais são os efeitos de não entregar a declaração?", "Que medidas são tomadas quando se perde a chave?", "Como a falta de um documento afeta o pedido?"],
        "responsable": ["A quem cabe revisar o inventário?", "Quem tem a tarefa de abrir a sala?", "Que entidade se ocupa de cobrar a matrícula?", "Quem controla as visitas?", "Quem fica encarregado de reservar a hospedagem?"],
        "requisito": ["O que é exigido para que aceitem a inscrição?", "Que informações são necessárias para se candidatar?", "Que características deve ter uma foto válida?", "Quantas páginas no mínimo o relatório precisa ter?", "Quais são as condições para receber a licença?"],
        "procedimiento": ["Esqueci meu código de acesso, como faço para recuperá-lo?", "Não encontro minha carteirinha, o que faço para recuperá-la?", "Cancelaram minha reserva, o que faço agora?", "Preciso mudar meus dados, como faço isso?", "De que forma consigo uma segunda via da credencial?"],
    },
}

if __name__ == "__main__":
    anterior = Path(__file__).resolve().parent / "intenciones-dev-test.json"
    shutil.copy2(anterior, anterior.with_name("intenciones-intento-1.json"))
    for idioma, grupos in EXTRA.items():
        ruta = RAIZ / f"ipsis/recursos/idiomas/{idioma}.yaml"
        texto = ruta.read_text(encoding="utf-8")
        for nombre, ejemplos in grupos.items():
            ancla = f"  {nombre}:\n    ejemplos:\n"
            assert texto.count(ancla) == 1
            bloque = "\n".join("    - " + json.dumps(e, ensure_ascii=False) for e in ejemplos)
            texto = texto.replace(ancla, ancla + bloque + "\n")
        ruta.write_text(texto, encoding="utf-8", newline="\n")
