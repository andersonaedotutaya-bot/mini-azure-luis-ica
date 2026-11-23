import os
import json
import hmac
import time
import base64
import hashlib
import secrets
import socket
from collections import Counter
from datetime import datetime
import joblib
import numpy as np
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from preprocesamiento import (
    limpiar_texto,
    extraer_entidades,
    extraer_palabras_clave,
    detectar_reaccion_emocional,
    tiene_contexto_operativo,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
MODEL_DIR = os.path.join(ROOT_DIR, "modelos")
STATS_FILE = os.path.join(BASE_DIR, "estadisticas_acumuladas.json")


def cargar_env_local():
    """Carga variables desde archivo .env si existe en el entorno local."""
    for ruta in (os.path.join(BASE_DIR, ".env"), os.path.join(ROOT_DIR, ".env")):
        if os.path.isfile(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea or linea.startswith("#") or "=" not in linea:
                        continue
                    clave, valor = linea.split("=", 1)
                    os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


cargar_env_local()

SECRET_KEY = os.getenv("JWT_SECRET_KEY") or secrets.token_hex(32)
TOKEN_EXPIRATION_SECONDS = int(os.getenv("TOKEN_EXPIRATION_SECONDS", "28800"))


def obtener_usuarios_configurados() -> dict:
    """Obtiene los usuarios autorizados desde variables de entorno (sin secretos en código)."""
    usuarios = {}
    op_user = os.getenv("USER_OPERADOR_NAME")
    op_pass = os.getenv("USER_OPERADOR_PASS")
    sup_user = os.getenv("USER_SUPERVISOR_NAME")
    sup_pass = os.getenv("USER_SUPERVISOR_PASS")

    if op_user and op_pass:
        usuarios[op_user] = {"password": op_pass, "role": "OPERADOR"}
    if sup_user and sup_pass:
        usuarios[sup_user] = {"password": sup_pass, "role": "SUPERVISOR"}
    return usuarios


def crear_token(username: str, role: str) -> str:
    """Genera un token firmado con HMAC-SHA256 (formato JWT compacto)."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload_data = {
        "sub": username,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_EXPIRATION_SECONDS,
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=").decode()
    signing_input = f"{header}.{payload}".encode()
    signature = hmac.new(SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{header}.{payload}.{sig_b64}"


def verificar_token(token: str) -> dict:
    """Verifica firma y expiración del token. Lanza HTTP 401 si no es válido."""
    try:
        partes = token.split(".")
        if len(partes) != 3:
            raise ValueError("Formato inválido")
        header_b64, payload_b64, sig_b64 = partes
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = hmac.new(SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).rstrip(b"=").decode()
        if not hmac.compare_digest(sig_b64, expected_b64):
            raise ValueError("Firma inválida")

        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding).decode())
        if payload.get("exp", 0) < int(time.time()):
            raise ValueError("Token expirado")
        return payload
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="No autenticado: token inválido, expirado o ausente.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(authorization: str = Header(default=None)) -> dict:
    """Dependencia FastAPI: exige autenticación Bearer válida (401 si falla)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Autenticación requerida: debe iniciar sesión y enviar Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    payload = verificar_token(token)
    return {"username": payload["sub"], "role": payload["role"]}


def require_supervisor(user: dict = Depends(get_current_user)) -> dict:
    """Dependencia FastAPI: exige rol SUPERVISOR (403 si es OPERADOR)."""
    if user.get("role") != "SUPERVISOR":
        raise HTTPException(
            status_code=403,
            detail="Acceso denegado (403 Forbidden): Su rol OPERADOR no tiene permiso para consultar el dashboard o estadísticas globales.",
        )
    return user


app = FastAPI(
    title="Mini-Azure LUIS v2 - Agroexportadora Ica",
    description="Microservicio NLP en la nube con autenticación JWT y control de acceso por rol (OPERADOR / SUPERVISOR).",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

modelo_intencion = joblib.load(os.path.join(MODEL_DIR, "modelo_intenciones.joblib"))
modelo_sentimiento = joblib.load(os.path.join(MODEL_DIR, "modelo_sentimiento.joblib"))

UMBRAL_CONFIANZA = 0.65

ACCIONES_MAP = {
    ("REPORTE_CALIDAD", "NEGATIVO"): "ALERTA_CRITICA_CALIDAD",
    ("REPORTE_CALIDAD", "NEUTRAL"): "REGISTRAR_INSPECCION_CALIDAD",
    ("REPORTE_CALIDAD", "POSITIVO"): "ARCHIVAR_CONFORMIDAD_CALIDAD",
    ("FALLA_EQUIPO", "NEGATIVO"): "ORDEN_MANTENIMIENTO_URGENTE",
    ("FALLA_EQUIPO", "NEUTRAL"): "PROGRAMAR_REVISION_TECNICA",
    ("FALLA_EQUIPO", "POSITIVO"): "CERRAR_TICKET_MANTENIMIENTO",
    ("CONSULTA_INVENTARIO", "NEGATIVO"): "ALERTA_QUIEBRE_STOCK",
    ("CONSULTA_INVENTARIO", "NEUTRAL"): "CONSULTAR_ERP_ALMACEN",
    ("CONSULTA_INVENTARIO", "POSITIVO"): "CONFIRMAR_DISPONIBILIDAD",
    ("SOLICITUD_DESPACHO", "NEGATIVO"): "PRIORIZAR_MUELLE_DESPACHO",
    ("SOLICITUD_DESPACHO", "NEUTRAL"): "GENERAR_GUIA_Y_PROGRAMAR",
    ("SOLICITUD_DESPACHO", "POSITIVO"): "CONFIRMAR_EMBARQUE_EXITOSO",
}


class LoginRequest(BaseModel):
    username: str
    password: str


class MensajeRequest(BaseModel):
    texto: str


def obtener_ip_local() -> str:
    """Detecta la IP privada de la PC Servidor en la red local (LAN)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def crear_estado_inicial():
    return {
        "total_mensajes": 0,
        "por_intencion": {
            "REPORTE_CALIDAD": 0,
            "FALLA_EQUIPO": 0,
            "CONSULTA_INVENTARIO": 0,
            "SOLICITUD_DESPACHO": 0,
            "INTENCION_NO_CLARA": 0,
        },
        "por_sentimiento": {
            "POSITIVO": 0,
            "NEUTRAL": 0,
            "NEGATIVO": 0,
        },
        "suma_confianza": 0.0,
        "derivados_supervisor": 0,
        "alertas_criticas": 0,
        "contador_entidades": Counter(),
        "historial": [],
    }


def guardar_estadisticas_disco():
    """Persiste las estadísticas acumuladas en archivo JSON para auditoría."""
    try:
        data = {
            "total_mensajes": estado["total_mensajes"],
            "por_intencion": estado["por_intencion"],
            "por_sentimiento": estado["por_sentimiento"],
            "suma_confianza": estado["suma_confianza"],
            "derivados_supervisor": estado["derivados_supervisor"],
            "alertas_criticas": estado["alertas_criticas"],
            "contador_entidades": dict(estado["contador_entidades"]),
            "historial": estado["historial"],
        }
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Aviso: No se pudo persistir estadísticas en disco: {e}")


estado = crear_estado_inicial()
guardar_estadisticas_disco()


def inferir_sentimiento(texto_limpio: str):
    probs = modelo_sentimiento.predict_proba([texto_limpio])[0]
    clases = modelo_sentimiento.classes_
    idx = int(np.argmax(probs))
    sentimiento = str(clases[idx])
    confianza = round(float(probs[idx]), 2)

    emocion = detectar_reaccion_emocional(texto_limpio)
    if emocion["tono"] == "ENOJO":
        sentimiento = "NEGATIVO"
        confianza = max(confianza, 0.95)
    elif emocion["tono"] == "POSITIVO":
        sentimiento = "POSITIVO"
        confianza = max(confianza, 0.90)
    elif emocion["tono"] == "ANGUSTIA":
        sentimiento = "NEGATIVO"
        confianza = max(confianza, 0.80)

    palabras_positivas_directas = [
        "felicidad", "feliz", "felices", "alegria", "alegre", "contento", "contenta",
        "reboso", "revoso", "rebosando", "revosando", "genial", "espectacular",
        "encantado", "encantada", "orgulloso", "orgullosa", "bien", "exito",
    ]
    if any(p in texto_limpio for p in palabras_positivas_directas) and sentimiento == "NEGATIVO":
        sentimiento = "POSITIVO"
        confianza = max(confianza, 0.80)

    palabras_criticas = [
        "pudricion", "detenida", "malogrado", "malogro", "fuga", "retrasados",
        "retraso", "subio a", "falla", "alarma", "quiebre", "escasez", "hongo",
        "hongos", "cancelo", "problema", "problemas", "danado", "roto", "urgente",
    ]
    tiene_critica = any(p in texto_limpio for p in palabras_criticas)

    if tiene_critica and sentimiento != "NEGATIVO":
        sentimiento = "NEGATIVO"
        confianza = max(confianza, 0.85)
    elif sentimiento == "NEGATIVO" and not tiene_critica and emocion["tono"] == "OPERATIVO" and confianza < 0.70:
        sentimiento = "NEUTRAL"

    return sentimiento, confianza, emocion


@app.get("/")
def raiz():
    """Endpoint informativo público de estado (health check)."""
    ip_lan = obtener_ip_local()
    return {
        "servicio": "Mini-Azure LUIS v2 (Agroexportadora Ica)",
        "estado": "ACTIVO",
        "autenticacion": "JWT Bearer (Roles: OPERADOR, SUPERVISOR)",
        "portal_web": "/portal",
        "ip_servidor_lan": ip_lan,
        "puerto": int(os.getenv("PORT", 8001)),
        "endpoints": {
            "login": "POST /auth/login",
            "perfil": "GET /auth/me",
            "analisis_texto": "POST /nlp/analizar-texto (OPERADOR / SUPERVISOR)",
            "entender_comando": "POST /nlp/entender-comando (OPERADOR / SUPERVISOR)",
            "estadisticas": "GET /nlp/estadisticas (Solo SUPERVISOR)",
            "reiniciar": "POST /nlp/estadisticas/reiniciar (Solo SUPERVISOR)",
            "docs": "/docs",
        },
    }


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return {}


@app.get("/portal", include_in_schema=False)
def portal_web():
    """Sirve el portal web unificado con login por rol para el despliegue en la nube."""
    ruta_portal = os.path.join(ROOT_DIR, "portal_cloud.html")
    if not os.path.isfile(ruta_portal):
        raise HTTPException(status_code=404, detail="Archivo portal_cloud.html no encontrado.")
    return FileResponse(ruta_portal, media_type="text/html")


@app.get("/cliente", include_in_schema=False)
def cliente_operador_web():
    """Sirve la interfaz dedicada del Integrante 2 (Operador) en la nube."""
    ruta_cliente = os.path.join(ROOT_DIR, "cliente_operador.html")
    if not os.path.isfile(ruta_cliente):
        raise HTTPException(status_code=404, detail="Archivo cliente_operador.html no encontrado.")
    return FileResponse(ruta_cliente, media_type="text/html")


@app.post("/auth/login")
def login(req: LoginRequest):
    """Autentica al usuario contra variables de entorno y devuelve un token JWT con su rol."""
    usuarios = obtener_usuarios_configurados()
    if not usuarios:
        raise HTTPException(
            status_code=500,
            detail="No hay usuarios configurados en las variables de entorno del servidor.",
        )

    usuario_info = usuarios.get(req.username.strip())
    if not usuario_info or not hmac.compare_digest(req.password, usuario_info["password"]):
        raise HTTPException(
            status_code=401,
            detail="Credenciales inválidas. Verifique usuario y contraseña.",
        )

    token = crear_token(req.username.strip(), usuario_info["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": req.username.strip(),
        "role": usuario_info["role"],
        "expires_in": TOKEN_EXPIRATION_SECONDS,
    }


@app.get("/auth/me")
def obtener_perfil(user: dict = Depends(get_current_user)):
    """Devuelve el perfil autenticado actual."""
    return user


@app.post("/nlp/analizar-texto")
def analizar_texto(req: MensajeRequest, user: dict = Depends(get_current_user)):
    """Simulación de Azure Text Analytics (requiere autenticación OPERADOR o SUPERVISOR)."""
    if not req.texto or not req.texto.strip():
        raise HTTPException(status_code=400, detail="El texto no puede estar vacío.")

    texto_limpio = limpiar_texto(req.texto)
    sentimiento, conf_sent, emocion = inferir_sentimiento(texto_limpio)
    palabras_clave = extraer_palabras_clave(req.texto)

    return {
        "texto_original": req.texto,
        "usuario": user["username"],
        "rol": user["role"],
        "sentimiento": sentimiento,
        "confianza": conf_sent,
        "confianza_sentimiento": conf_sent,
        "reaccion_emocional": emocion["reaccion_emocional"],
        "tono": emocion["tono"],
        "terminos_clave": palabras_clave,
        "frases_clave": palabras_clave,
    }


@app.post("/nlp/entender-comando")
def entender_comando(req: MensajeRequest, user: dict = Depends(get_current_user)):
    """Simulación de Azure LUIS (requiere autenticación OPERADOR o SUPERVISOR)."""
    if not req.texto or not req.texto.strip():
        raise HTTPException(status_code=400, detail="El texto no puede estar vacío.")

    texto_limpio = limpiar_texto(req.texto)
    tokens = texto_limpio.split()

    probs = modelo_intencion.predict_proba([texto_limpio])[0]
    clases = modelo_intencion.classes_
    idx = int(np.argmax(probs))
    intencion_pred = str(clases[idx])
    confianza = round(float(probs[idx]), 2)

    sentimiento, _, emocion = inferir_sentimiento(texto_limpio)
    entidades = extraer_entidades(req.texto)
    es_operativo = tiene_contexto_operativo(req.texto, entidades)

    if confianza < UMBRAL_CONFIANZA or len(tokens) < 2 or (emocion["es_emocional"] and not es_operativo):
        intencion_final = "INTENCION_NO_CLARA"
        if emocion["es_emocional"] and not es_operativo:
            confianza = min(confianza, 0.45)
        if emocion["es_emocional"] and emocion["tono"] == "ENOJO":
            accion_sugerida = "DERIVAR_A_SUPERVISOR_RECLAMO_EMOCIONAL"
        elif emocion["es_emocional"] and emocion["tono"] == "ANGUSTIA":
            accion_sugerida = "DERIVAR_A_SUPERVISOR_MENSAJE_PERSONAL"
        elif emocion["es_emocional"] and emocion["tono"] == "POSITIVO":
            accion_sugerida = "REGISTRAR_SATISFACCION_USUARIO"
        else:
            accion_sugerida = "DERIVAR_A_SUPERVISOR"
    else:
        intencion_final = intencion_pred
        accion_sugerida = ACCIONES_MAP.get((intencion_final, sentimiento), "REVISION_OPERATIVA")

    estado["total_mensajes"] += 1
    estado["por_intencion"][intencion_final] += 1
    estado["por_sentimiento"][sentimiento] += 1
    estado["suma_confianza"] += confianza

    if "DERIVAR" in accion_sugerida or intencion_final == "INTENCION_NO_CLARA":
        estado["derivados_supervisor"] += 1
    if "ALERTA" in accion_sugerida or "URGENTE" in accion_sugerida:
        estado["alertas_criticas"] += 1

    for tipo_ent, valor_ent in entidades.items():
        estado["contador_entidades"][f"{tipo_ent}: {valor_ent}"] += 1

    resultado = {
        "hora": datetime.now().strftime("%H:%M:%S"),
        "usuario": user["username"],
        "texto_original": req.texto,
        "intencion": intencion_final,
        "confianza_intencion": confianza,
        "sentimiento": sentimiento,
        "reaccion_emocional": emocion["reaccion_emocional"],
        "tono": emocion["tono"],
        "entidades": entidades,
        "accion_sugerida": accion_sugerida,
    }

    estado["historial"].insert(0, resultado)
    estado["historial"] = estado["historial"][:30]
    guardar_estadisticas_disco()

    return resultado


@app.get("/nlp/estadisticas")
def obtener_estadisticas(user: dict = Depends(require_supervisor)):
    """Analítica de Comunicaciones: Solo accesible para rol SUPERVISOR (403 para OPERADOR)."""
    total = estado["total_mensajes"]
    confianza_prom = round(estado["suma_confianza"] / total, 2) if total > 0 else 0.0
    tasa_deriv = round(estado["derivados_supervisor"] / total, 2) if total > 0 else 0.0

    return {
        "total_mensajes": total,
        "por_intencion": estado["por_intencion"],
        "por_sentimiento": estado["por_sentimiento"],
        "confianza_promedio": confianza_prom,
        "tasa_derivacion": tasa_deriv,
        "alertas_criticas": estado["alertas_criticas"],
        "entidades_frecuentes": dict(estado["contador_entidades"].most_common(5)),
        "bitacora_reciente": estado["historial"],
    }


@app.post("/nlp/estadisticas/reiniciar")
def reiniciar_estadisticas(user: dict = Depends(require_supervisor)):
    """Control de sesión: Solo accesible para rol SUPERVISOR."""
    global estado
    estado = crear_estado_inicial()
    guardar_estadisticas_disco()
    return {"mensaje": "Estadísticas reiniciadas correctamente."}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8001))
    ip_detectada = obtener_ip_local()
    print("=" * 70)
    print("INICIANDO SERVIDOR MINI-AZURE LUIS v2 - AGROEXPORTADORA ICA")
    print(f"IP Servidor en Red LAN : {ip_detectada}")
    print(f"Puerto                 : {port}")
    print(f"Portal Web Unificado   : http://{ip_detectada}:{port}/portal")
    print(f"Documentación Swagger  : http://{ip_detectada}:{port}/docs")
    print("=" * 70)
    uvicorn.run(app, host="0.0.0.0", port=port)
