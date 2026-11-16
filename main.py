import os
import json
import requests
import threading
import time
from flask import Flask, request
from datetime import datetime, timedelta

app = Flask(__name__)

# =====================================================================
# CONFIGURAÇÕES PRINCIPAIS (PREENCHA COM OS DADOS DO NOVO BOT)
# =====================================================================
BOT_AGENDADOR_TOKEN = "9255952434:AAHJpaYaG2ZVY8MRyeFj3h5PSPLg_-Svtow"
PREVIAS_JAQUE_GROUP_ID = "-1001994331287"
ADMIN_ID = "7008304182"

# Links diretos dos seus bots de venda (com ?start= para iniciar o funil na hora)
LINK_BOT_JAQUE = "https://t.me/Agendador_JaquePink_bot?start=previas"
LINK_BOT_PLAYBOX = "https://t.me/ADM_TudaoVIP_bot?start=jaqueprevias"

# Horários no fuso de Brasília (UTC-3)
HORA_ENQUETE_MANHA = "09:30"
HORA_MIDIA_NOITE = "21:00"
HORA_OFERTA_PLAYBOX = "15:30"
INTERVALO_DIAS_PLAYBOX = 3  # Envia a oferta da PlayBox a cada 3 dias

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_AGENDADOR_TOKEN}"
ARQUIVO_ESTADO = "estado_agendador.json"
lock_estado = threading.Lock()

_worker_pid = None
_lock_worker = threading.Lock()

# Estado persistente para não repetir mídia e nunca duplicar disparo no mesmo dia
estado = {
    "indice_enquete": 0,
    "indice_midia": 0,
    "ultimo_dia_enquete": "",
    "ultimo_dia_midia": "",
    "ultimo_dia_playbox": "",
    "dias_desde_playbox": 0
}

# =====================================================================
# VÍDEO 3 DA PLAYBOX (ENCAMINHE O VÍDEO 3 PARA ESTE BOT E COLE O ID AQUI)
# =====================================================================
VIDEO_PLAYBOX_ID = "COLE_AQUI_O_FILE_ID_DO_VIDEO_3_NESTE_BOT"

COPY_OFERTA_PLAYBOX = (
    "💣 **QUER ACESSO A UM ACERVO SECRETO QUE NÃO PODE FICAR ABERTO AQUI?** 🔞\n\n"
    "Além da Jaque Pink, liberamos poucas vagas para o **VIP VITALÍCIO DA PLAYBOX** — um grupo fechado e separado com conteúdo pesado e sem censura:\n\n"
    "🔥 **Casadas no sigilo absoluto**\n"
    "📸 **Flagras reais e câmeras escondidas**\n"
    "📂 **Vazados raros + Drive Secreto com +400 vídeos amadores**\n"
    "👑 **Acesso Vitalício** (paga uma única vez e fica para sempre)\n\n"
    "⚡ *Liberação automática via PIX em 5 segundos após o pagamento.*\n\n"
    "👇 **TOQUE NO BOTÃO ABAIXO E GARANTA SUA VAGA AGORA:**"
)

# =====================================================================
# BANCO DE ENQUETES PICANTES (MANHÃ — ROTAÇÃO AUTOMÁTICA)
# =====================================================================
ENQUETES_MANHA = [
    {
        "pergunta": "🔥 Começando o dia sem filtro: o que você quer ver hoje à noite aqui no grupo?",
        "opcoes": [
            "🚕 Corrida do Uber paga no sigilo",
            "🤫 Os vídeos proibidos com o titio",
            "🔞 Encontro real com desconhecido",
            "📸 Fotos sem censura no espelho"
        ]
    },
    {
        "pergunta": "😈 Se você tivesse 10 minutos trancado com a Jaque agora, o que aconteceria primeiro?",
        "opcoes": [
            "🎥 Já ligava a câmera pra gravar tudo",
            "🔥 Ia direto pros finalmente sem enrolar",
            "🤫 Fazia no sigilo onde ninguém pode ver",
            "💦 Repetia até perder a conta"
        ]
    },
    {
        "pergunta": "👀 Qual desses conteúdos da Jaque te deixa mais louco?",
        "opcoes": [
            "🔞 Vídeos longos sem cortes e sem tarjas",
            "🚕 Gravações escondidas na rua / carro",
            "🔥 Áudios gemendo e provocação perto",
            "📂 Tudo isso liberado no VIP"
        ]
    },
    {
        "pergunta": "🚨 Seja sincero (voto anônimo): você já entrou no VIP oficial ou ainda tá só nas prévias?",
        "opcoes": [
            "👑 Já tô lá dentro aproveitando tudo",
            "💳 Vou entrar hoje ainda",
            "👀 Tô quase clicando no link",
            "🔥 Manda uma prévia braba hoje à noite"
        ]
    },
    {
        "pergunta": "🍑 Hoje à noite você prefere que eu solte o quê antes do VIP fechar vagas?",
        "opcoes": [
            "🎬 Vídeo provocante de quatro",
            "📸 Sequência de fotos bem perto",
            "🤫 Trecho vazado com o titio",
            "🔥 Os dois (foto + vídeo)"
        ]
    },
    {
        "pergunta": "🌡️ Temperatura subindo cedo: você curte mais assistir...",
        "opcoes": [
            "🎥 Vídeo amador real sem frescura",
            "🔥 Provocação lenta tirando tudo",
            "🔞 Cena pesada completa sem corte",
            "💦 Tudo junto no pacote VIP"
        ]
    },
    {
        "pergunta": "⚡ Se eu liberar uma condição relâmpago no VIP hoje à noite, você aproveita?",
        "opcoes": [
            "🔥 Com certeza, só mandar o link",
            "💎 Quero pegar o plano mensal",
            "👑 Vou direto no Vitalício",
            "👀 Quero ver a prévia das 21h primeiro"
        ]
    }
]

# =====================================================================
# COPYS GERAIS DE FECHAMENTO (VÃO LOGO ABAIXO DA LEGENDA ESPECÍFICA)
# =====================================================================
COPYS_GERAIS_CTA = [
    (
        "🔒 *Aqui no grupo aberto só passa a pontinha sem mostrar tudo...*\n\n"
        "O vídeo completo, **sem cortes, sem tarjas e com áudio original**, já está liberado agora no **VIP Oficial da Jaque Pink** (incluindo os vídeos no Uber, com desconhecidos e com o titio).\n\n"
        "👇 **Toque no botão abaixo e entre em 5 segundos:**"
    ),
    (
        "🚨 **ISSO AQUI É SÓ UMA AMOSTRA DO QUE ROLA LÁ DENTRO!**\n\n"
        "No **VIP Exclusivo** você assiste na íntegra sem censura, com atualizações novas toda semana e liberação automática assim que o PIX cai.\n\n"
        "👇 **Clique abaixo para destravar seu acesso agora:**"
    ),
    (
        "🔞 **QUER VER O RESTO SEM CORTES?**\n\n"
        "A versão completa dessa gravação + toda a galeria secreta da Jaque Pink está disponível agora a partir de **R$ 9,90**.\n\n"
        "👇 **Toque abaixo para chamar o bot e liberar sua entrada:**"
    ),
    (
        "🔥 **NÃO FIQUE SÓ NA VONTADE OLHANDO PRÉVIA...**\n\n"
        "Enquanto o pessoal aqui vê só 5 segundos cortados, quem está no **VIP** já assistiu tudo completo e sem censura.\n\n"
        "👇 **Garanta seu acesso imediato no botão abaixo:**"
    )
]

# =====================================================================
# ACERVO DE PRÉVIAS (COLE AQUI AS LINHAS GERADAS PELO MODO EXTRATOR)
# =====================================================================
ACERVO_PREVIAS = [
    # Exemplo de como fica cada item após encaminhar para o bot:
    # {"tipo": "video", "file_id": "BAACAgEAAxk...", "legenda": "Olha o que ela fez antes de sair de casa 😈"},
    # {"tipo": "photo", "file_id": "AgACAgEAAxk...", "legenda": "Sem filtro nenhum hoje 🔥"},
]


# =====================================================================
# PERSISTÊNCIA E HORA DE BRASÍLIA (UTC-3)
# =====================================================================
def agora_brasilia():
    return datetime.utcnow() - timedelta(hours=3)


def salvar_estado():
    with lock_estado:
        try:
            with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
                json.dump(estado, f, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar estado: {e}", flush=True)


def carregar_estado():
    global estado
    if not os.path.exists(ARQUIVO_ESTADO):
        return
    try:
        with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
            dados = json.load(f)
        estado.update(dados)
    except Exception as e:
        print(f"Erro ao carregar estado: {e}", flush=True)


# =====================================================================
# FUNÇÕES DE ENVIO TELEGRAM
# =====================================================================
def enviar_mensagem(chat_id, texto, markup=None):
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"}
    if markup:
        payload["reply_markup"] = markup
    try:
        req = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload, timeout=15)
        if req.status_code != 200:
            payload.pop("parse_mode", None)
            requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload, timeout=15)
    except Exception as e:
        print(f"Erro sendMessage: {e}", flush=True)


def enviar_enquete(chat_id, pergunta, opcoes):
    payload = {
        "chat_id": chat_id,
        "question": pergunta[:300],
        "options": [{"text": str(o)[:100]} for o in opcoes],
        "is_anonymous": True
    }
    try:
        req = requests.post(f"{TELEGRAM_API_URL}/sendPoll", json=payload, timeout=15)
        if req.status_code == 200:
            return True
        # Fallback para versões legadas caso necessário
        payload["options"] = [str(o)[:100] for o in opcoes]
        req2 = requests.post(f"{TELEGRAM_API_URL}/sendPoll", json=payload, timeout=15)
        return req2.status_code == 200
    except Exception as e:
        print(f"Erro sendPoll: {e}", flush=True)
        return False


def enviar_midia(chat_id, tipo, file_id, legenda, markup=None):
    endpoint = "sendPhoto" if tipo == "photo" else "sendVideo"
    campo_midia = "photo" if tipo == "photo" else "video"

    payload = {
        "chat_id": chat_id,
        campo_midia: file_id,
        "caption": legenda[:1024],
        "parse_mode": "Markdown"
    }
    if markup:
        payload["reply_markup"] = markup

    try:
        req = requests.post(f"{TELEGRAM_API_URL}/{endpoint}", json=payload, timeout=30)
        if req.status_code == 200:
            return True
        print(f"⚠️ Erro {endpoint} ({req.status_code}): {req.text}", flush=True)
        payload.pop("parse_mode", None)
        req2 = requests.post(f"{TELEGRAM_API_URL}/{endpoint}", json=payload, timeout=30)
        return req2.status_code == 200
    except Exception as e:
        print(f"❌ Exceção {endpoint}: {e}", flush=True)
        return False


# =====================================================================
# DISPARADORES DO CRONOGRAMA
# =====================================================================
def disparar_enquete_manha(forcar=False):
    if not ENQUETES_MANHA:
        return False
    idx = int(estado.get("indice_enquete", 0)) % len(ENQUETES_MANHA)
    enquete = ENQUETES_MANHA[idx]

    ok = enviar_enquete(PREVIAS_JAQUE_GROUP_ID, enquete["pergunta"], enquete["opcoes"])
    if ok:
        estado["indice_enquete"] = (idx + 1) % len(ENQUETES_MANHA)
        if not forcar:
            estado["ultimo_dia_enquete"] = agora_brasilia().strftime("%Y-%m-%d")
        salvar_estado()
        print(f"📊 Enquete #{idx + 1} enviada no grupo!", flush=True)
    return ok


def disparar_midia_noite(forcar=False):
    if not ACERVO_PREVIAS:
        print("⚠️ ACERVO_PREVIAS está vazio! Encaminhe as mídias para o bot primeiro.", flush=True)
        return False

    idx = int(estado.get("indice_midia", 0)) % len(ACERVO_PREVIAS)
    item = ACERVO_PREVIAS[idx]
    copy_cta = COPYS_GERAIS_CTA[idx % len(COPYS_GERAIS_CTA)]

    legenda_especifica = item.get("legenda", "").strip()
    if legenda_especifica:
        legenda_final = f"{legenda_especifica}\n\n{copy_cta}"
    else:
        legenda_final = copy_cta

    markup_jaque = {
        "inline_keyboard": [
            [{"text": "🔞 ACESSAR VIP JAQUE PINK AGORA 🔥", "url": LINK_BOT_JAQUE}]
        ]
    }

    ok = enviar_midia(PREVIAS_JAQUE_GROUP_ID, item["tipo"], item["file_id"], legenda_final, markup_jaque)
    if ok:
        estado["indice_midia"] = (idx + 1) % len(ACERVO_PREVIAS)
        if not forcar:
            estado["ultimo_dia_midia"] = agora_brasilia().strftime("%Y-%m-%d")
        salvar_estado()
        print(f"🎬 Mídia #{idx + 1} ({item['tipo']}) enviada no grupo!", flush=True)
    return ok


def disparar_oferta_playbox(forcar=False):
    if not VIDEO_PLAYBOX_ID or VIDEO_PLAYBOX_ID.startswith("COLE_AQUI"):
        print("⚠️ VIDEO_PLAYBOX_ID não configurado.", flush=True)
        return False

    markup_pb = {
        "inline_keyboard": [
            [{"text": "💣 ENTRAR NO VIP VITALÍCIO PLAYBOX 👑", "url": LINK_BOT_PLAYBOX}]
        ]
    }
    ok = enviar_midia(PREVIAS_JAQUE_GROUP_ID, "video", VIDEO_PLAYBOX_ID, COPY_OFERTA_PLAYBOX, markup_pb)
    if ok:
        if not forcar:
            estado["ultimo_dia_playbox"] = agora_brasilia().strftime("%Y-%m-%d")
            estado["dias_desde_playbox"] = 0
        salvar_estado()
        print("💣 Oferta PlayBox enviada no grupo!", flush=True)
    return ok


# =====================================================================
# LOOP VIGILANTE DO RELÓGIO (VERIFICA A CADA 15 SEGUNDOS)
# =====================================================================
def _loop_agendador():
    print(f"🚀 Agendador Jaque Pink ativo no PID {os.getpid()}!", flush=True)
    ultimo_dia_contado = agora_brasilia().strftime("%Y-%m-%d")

    while True:
        try:
            agora = agora_brasilia()
            hoje_str = agora.strftime("%Y-%m-%d")
            hora_atual = agora.strftime("%H:%M")

            # Virada de dia: incrementa contador de dias para a oferta da PlayBox
            if hoje_str != ultimo_dia_contado:
                ultimo_dia_contado = hoje_str
                estado["dias_desde_playbox"] = int(estado.get("dias_desde_playbox", 0)) + 1
                salvar_estado()

            # 1. Enquete da manhã
            if hora_atual == HORA_ENQUETE_MANHA and estado.get("ultimo_dia_enquete") != hoje_str:
                disparar_enquete_manha(forcar=False)

            # 2. Oferta PlayBox a cada N dias
            if (
                hora_atual == HORA_OFERTA_PLAYBOX
                and estado.get("ultimo_dia_playbox") != hoje_str
                and int(estado.get("dias_desde_playbox", 0)) >= INTERVALO_DIAS_PLAYBOX
            ):
                disparar_oferta_playbox(forcar=False)

            # 3. Mídia principal da noite
            if hora_atual == HORA_MIDIA_NOITE and estado.get("ultimo_dia_midia") != hoje_str:
                disparar_midia_noite(forcar=False)

        except Exception as e:
            print(f"❌ Erro no loop do agendador: {e}", flush=True)

        time.sleep(15)


def garantir_loop_worker():
    global _worker_pid
    pid_atual = os.getpid()
    if _worker_pid != pid_atual:
        with _lock_worker:
            if _worker_pid != pid_atual:
                _worker_pid = pid_atual
                threading.Thread(target=_loop_agendador, daemon=True).start()


@app.before_request
def antes_de_requisicao():
    garantir_loop_worker()


# =====================================================================
# ROTAS WEB E WEBHOOK (COM MODO EXTRATOR AUTOMÁTICO DE MÍDIAS)
# =====================================================================
@app.route("/", methods=["GET"])
def home():
    garantir_loop_worker()
    return f"Agendador Prévias Jaque Pink Ativo! | Hora BR: {agora_brasilia().strftime('%H:%M:%S')}", 200


@app.route("/status", methods=["GET"])
def status():
    garantir_loop_worker()
    return {
        "worker_pid": _worker_pid,
        "hora_brasilia": agora_brasilia().strftime("%Y-%m-%d %H:%M:%S"),
        "total_midias_acervo": len(ACERVO_PREVIAS),
        "estado_atual": estado
    }, 200


@app.route("/setup", methods=["GET"])
def setup():
    garantir_loop_worker()
    host = request.host
    webhook_url = f"https://{host}/webhook/telegram/{BOT_AGENDADOR_TOKEN}"
    res = requests.post(f"{TELEGRAM_API_URL}/setWebhook", json={"url": webhook_url}).json()
    return f"Webhook Agendador configurado: {res}", 200


@app.route(f"/webhook/telegram/{BOT_AGENDADOR_TOKEN}", methods=["POST"])
def telegram_webhook():
    garantir_loop_worker()
    update = request.get_json(silent=True)
    if not update or "message" not in update:
        return {"status": "ok"}, 200

    msg = update["message"]
    chat_id = str(msg["chat"]["id"])

    # Só responde ao ADMIN no privado
    if chat_id != ADMIN_ID:
        return {"status": "ok"}, 200

    texto = msg.get("text", "")

    # MODO EXTRATOR: Encaminhe qualquer foto ou vídeo para o bot e ele gera a linha pronta!
    if "video" in msg or "photo" in msg:
        if "video" in msg:
            tipo = "video"
            file_id = msg["video"]["file_id"]
        else:
            tipo = "photo"
            file_id = msg["photo"][-1]["file_id"]  # Pega a maior resolução da foto

        legenda_orig = (msg.get("caption") or "").replace('"', '\\"').replace("\n", "\\n")
        linha_codigo = f'{{"tipo": "{tipo}", "file_id": "{file_id}", "legenda": "{legenda_orig}"}},'

        enviar_mensagem(
            chat_id,
            f"✅ **Mídia capturada!** Copie e cole dentro de `ACERVO_PREVIAS`:\n\n`{linha_codigo}`\n\n"
            f"💡 *Se for o Vídeo 3 da PlayBox, copie apenas o ID:*\n`{file_id}`"
        )
        return {"status": "ok"}, 200

    # Comandos de teste rápido para validar tudo na hora
    if texto.startswith("/start"):
        enviar_mensagem(
            chat_id,
            "🤖 **Agendador da Jaque Pink Pronto!**\n\n"
            "• **Encaminhe** qualquer foto ou vídeo do grupo de prévias aqui que eu te mando o código pronto com a legenda original.\n"
            "• `/testar_enquete` — Dispara uma enquete agora no grupo\n"
            "• `/testar_midia` — Dispara a próxima mídia + copy + botão agora\n"
            "• `/testar_playbox` — Dispara a oferta da PlayBox agora"
        )
    elif texto.startswith("/testar_enquete"):
        ok = disparar_enquete_manha(forcar=True)
        enviar_mensagem(chat_id, "✅ Enquete disparada no grupo!" if ok else "❌ Erro ao disparar enquete.")
    elif texto.startswith("/testar_midia"):
        ok = disparar_midia_noite(forcar=True)
        enviar_mensagem(chat_id, "✅ Mídia + Copy + Botão disparados!" if ok else "❌ Acervo vazio ou erro no envio.")
    elif texto.startswith("/testar_playbox"):
        ok = disparar_oferta_playbox(forcar=True)
        enviar_mensagem(chat_id, "✅ Oferta PlayBox disparada!" if ok else "❌ Configure o `VIDEO_PLAYBOX_ID` primeiro.")

    return {"status": "ok"}, 200


carregar_estado()
garantir_loop_worker()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
