import os
import json
import socket
from collections import Counter
from datetime import datetime
import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from preprocesamiento import (
    limpiar_texto,
    extraer_entidades,
    extraer_palabras_clave,
    detectar_reaccion_emocional
)

app = FastAPI(
    title="Mini-Azure LUIS - Agroexportadora Ica",
    description="Microservicio local de Procesamiento del Lenguaje Natural (NLP) para clasificación de intenciones, sentimiento, extracción de entidades y analítica operativa en red LAN.",
    version="1.0.0"
)

# Habilitar CORS para permitir peticiones HTTP desde cualquier cliente en la red LAN
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "..", "modelos")
STATS_FILE = os.path.join(BASE_DIR, "estadisticas_acumuladas.json")

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
        "historial": []
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
            "historial": estado["historial"]
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

    # Detección de reacción emocional (enojo, frustración, estafa, tontería)
    emocion = detectar_reaccion_emocional(texto_limpio)
    if emocion["tono"] == "ENOJO":
        sentimiento = "NEGATIVO"
        confianza = max(confianza, 0.95)
    elif emocion["tono"] == "POSITIVO":
        sentimiento = "POSITIVO"
        confianza = max(confianza, 0.90)

    # Regla de refuerzo heurístico para términos críticos del dominio agroexportador
    palabras_criticas = ["pudricion", "detenida", "malogrado", "fuga", "retrasados", "subio a", "falla", "alarma", "quiebre", "escasez"]
    if any(p in texto_limpio for p in palabras_criticas) and sentimiento != "NEGATIVO":
        sentimiento = "NEGATIVO"
        confianza = max(confianza, 0.85)

    return sentimiento, confianza, emocion

@app.get("/")
def raiz():
    """Endpoint informativo de bienvenida y verificación de estado en red LAN."""
    ip_lan = obtener_ip_local()
    return {
        "servicio": "Mini-Azure LUIS (Agroexportadora Ica)",
        "estado": "ACTIVO",
        "ip_servidor_lan": ip_lan,
        "puerto": 8001,
        "url_base_lan": f"http://{ip_lan}:8001",
        "endpoints": {
            "analisis_texto": "POST /nlp/analizar-texto",
            "entender_comando": "POST /nlp/entender-comando",
            "estadisticas": "GET /nlp/estadisticas",
            "reiniciar": "POST /nlp/estadisticas/reiniciar",
            "docs": "/docs"
        }
    }

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Evita registros 404 al abrir el servicio desde navegadores."""
    return {}

@app.post("/nlp/analizar-texto")
def analizar_texto(req: MensajeRequest):
    """Simulación de Azure Text Analytics: Análisis de polaridad de sentimiento, reacción emocional y frases clave."""
    if not req.texto or not req.texto.strip():
        raise HTTPException(status_code=400, detail="El texto no puede estar vacío.")

    texto_limpio = limpiar_texto(req.texto)
    sentimiento, conf_sent, emocion = inferir_sentimiento(texto_limpio)
    palabras_clave = extraer_palabras_clave(req.texto)

    return {
        "texto_original": req.texto,
        "sentimiento": sentimiento,
        "confianza": conf_sent,
        "confianza_sentimiento": conf_sent,
        "reaccion_emocional": emocion["reaccion_emocional"],
        "tono": emocion["tono"],
        "terminos_clave": palabras_clave,
        "frases_clave": palabras_clave
    }

@app.post("/nlp/entender-comando")
def entender_comando(req: MensajeRequest):
    """Simulación de Azure LUIS: Reconocimiento de intenciones, extracción de entidades y sugerencia de acción."""
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

    # Regla de incertidumbre / fallback: Si confianza < 0.65, o mensaje < 2 tokens
    if confianza < UMBRAL_CONFIANZA or len(tokens) < 2:
        intencion_final = "INTENCION_NO_CLARA"
        if emocion["es_emocional"] and emocion["tono"] == "ENOJO":
            accion_sugerida = "DERIVAR_A_SUPERVISOR_RECLAMO_EMOCIONAL"
        else:
            accion_sugerida = "DERIVAR_A_SUPERVISOR"
    else:
        intencion_final = intencion_pred
        accion_sugerida = ACCIONES_MAP.get((intencion_final, sentimiento), "REVISION_OPERATIVA")

    # Registro en métricas acumuladas
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
        "texto_original": req.texto,
        "intencion": intencion_final,
        "confianza_intencion": confianza,
        "sentimiento": sentimiento,
        "reaccion_emocional": emocion["reaccion_emocional"],
        "tono": emocion["tono"],
        "entidades": entidades,
        "accion_sugerida": accion_sugerida
    }

    estado["historial"].insert(0, resultado)
    estado["historial"] = estado["historial"][:30]
    guardar_estadisticas_disco()

    return resultado

@app.get("/nlp/estadisticas")
def obtener_estadisticas():
    """Analítica de Comunicaciones: Métricas acumuladas y bitácora reciente."""
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
        "bitacora_reciente": estado["historial"]
    }

@app.post("/nlp/estadisticas/reiniciar")
def reiniciar_estadisticas():
    """Control de sesión: Reinicia los contadores y la bitácora acumulada."""
    global estado
    estado = crear_estado_inicial()
    guardar_estadisticas_disco()
    return {"mensaje": "Estadísticas reiniciadas correctamente."}

if __name__ == "__main__":
    import uvicorn
    ip_detectada = obtener_ip_local()
    print("=" * 70)
    print("INICIANDO SERVIDOR MINI-AZURE LUIS - AGROEXPORTADORA ICA")
    print(f"IP Servidor en Red LAN : {ip_detectada}")
    print(f"Puerto                 : 8001")
    print(f"URL de Acceso LAN      : http://{ip_detectada}:8001")
    print(f"Documentación Swagger  : http://{ip_detectada}:8001/docs")
    print("=" * 70)
    uvicorn.run(app, host="0.0.0.0", port=8001)
