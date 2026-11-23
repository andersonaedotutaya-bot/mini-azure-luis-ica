import re
import unicodedata

# Diccionario de normalización de jerga agroindustrial y errores ortográficos comunes de Ica
ABREVIATURAS = {
    r"\bcam\.?\b": "camara",
    r"\btemp\.?\b": "temperatura",
    r"\bfaja transp\.?\b": "faja transportadora",
    r"\bimp\.?\b": "impresora",
    r"\bguia\b": "guia de remision",
    r"\bcont\.?\b": "contenedor",
    r"\bredglobe\b": "uva red globe",
    r"\bsweet globe\b": "uva sweet globe",
    r"\besparrago\b": "esparrago verde",
    r"\bmalogro\b": "falla",
    r"\bparada\b": "detenida",
    r"\bpodrida\b": "pudricion",
    r"\buvaz\b": "uva",
    r"\bstok\b": "stock",
    r"\bhumdad\b": "humedad",
    r"\bx\b": "por",
    r"\bq\b": "que",
    r"\burg\b": "urgente",
    r"\bpalet\b": "pallet",
    r"\bpalets\b": "pallets",
}

def limpiar_texto(texto: str) -> str:
    """Normaliza texto en español: minúsculas, sin tildes y expansión de jerga/abreviaturas locales."""
    if not texto:
        return ""
    texto = texto.lower().strip()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    for patron, reemplazo in ABREVIATURAS.items():
        texto = re.sub(patron, reemplazo, texto)
    texto = re.sub(r"[^a-z0-9\s\.\-]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

def extraer_entidades(texto_original: str) -> dict:
    """Extrae entidades de negocio del dominio agroexportador (AREA, PRODUCTO, CANTIDAD, CODIGO_LOTE)."""
    texto_norm = limpiar_texto(texto_original)
    entidades = {}

    # 1. Extracción de ÁREA
    match_area = re.search(
        r"\b(camara\s*(?:de\s*frio)?\s*\d+|linea\s*(?:de\s*empaque|de\s*seleccion|de\s*lavado)?\s*\d+|packing\s*\d+|muelle\s*\d+|tunel\s*(?:de\s*frio|de\s*preenfriado)?\s*\d+|almacen\s*(?:central|de\s*insumos)?|garita|patio\s*de\s*maniobras|sala\s*de\s*maquinas)\b",
        texto_norm
    )
    if match_area:
        entidades["AREA"] = match_area.group(1).strip()

    # 2. Extracción de PRODUCTO
    match_prod = re.search(
        r"\b(uva\s*(?:red\s*globe|sweet\s*globe|crimson|thompson|autumn\s*crisp)?|esparrago\s*(?:verde|blanco)?|palta\s*hass|arandano[s]?)\b",
        texto_norm
    )
    if match_prod:
        entidades["PRODUCTO"] = match_prod.group(1).strip()

    # 3. Extracción de CANTIDAD
    match_cant = re.search(
        r"\b(\d+(?:\.\d+)?\s*(?:cajas|pallets|jabas|kg|kilos|toneladas|contenedores|bolsas|racimos))\b",
        texto_norm
    )
    if match_cant:
        entidades["CANTIDAD"] = match_cant.group(1).strip()

    # 4. Extracción de CÓDIGO DE LOTE
    match_lote = re.search(
        r"\b(?:lote|cod(?:igo)?)[\s\-:#]*([a-z0-9\-]+)|\b(lt[\s\-:#]*\d+)\b",
        texto_norm
    )
    if match_lote:
        codigo = (match_lote.group(1) or match_lote.group(2)).strip().upper()
        if len(codigo) >= 2:
            entidades["CODIGO_LOTE"] = codigo

    return entidades

def extraer_palabras_clave(texto_original: str) -> list:
    """Extrae términos relevantes filtrando palabras vacías (stopwords)."""
    stopwords = {
        "el", "la", "los", "las", "de", "del", "en", "con", "por", "para",
        "un", "una", "se", "a", "y", "que", "esta", "al", "sin", "nos", "hay",
        "lo", "es", "son", "fue", "sus", "su", "como", "mas", "pero", "este"
    }
    tokens = limpiar_texto(texto_original).split()
    return [t for t in tokens if t not in stopwords and len(t) > 2]

def detectar_reaccion_emocional(texto_original: str) -> dict:
    """Detecta tono emocional, enojo, quejas agresivas, estafas o frustración en el mensaje."""
    texto_norm = limpiar_texto(texto_original)
    
    # Patrones de enojo, estafa, frustración e indignación
    patrones_enojo = [
        r"\bestafad[ao]s?\b", r"\bestafa[s]?\b", r"\btonteria[s]?\b", r"\bcolmo\b",
        r"\bporqueria[s]?\b", r"\bbasura\b", r"\bincompetenc\w*\b", r"\bharto\b",
        r"\bfurios[ao]s?\b", r"\benoj[ao]s?\b", r"\benojad[ao]s?\b", r"\bverguenza\b",
        r"\bburla\b", r"\bdesastre\b", r"\brobo\b", r"\bindigna\w*\b", r"\basco\b",
        r"\binept\w*\b", r"\bpesim[ao]s?\b", r"\bhorrible\b", r"\bbronca\b", r"\bmolest[ao]s?\b"
    ]
    palabras_enojo = [p for p in patrones_enojo if re.search(p, texto_norm)]
    
    # Patrones de satisfacción positiva
    patrones_satisfaccion = [
        r"\bexcelente\b", r"\bfelicitaciones\b", r"\bimpecable\b", r"\bgran trabajo\b",
        r"\bmaravilla\b", r"\bagradecid[ao]s?\b", r"\bperfecto\b", r"\bsatisfech[ao]s?\b"
    ]
    palabras_sat = [p for p in patrones_satisfaccion if re.search(p, texto_norm)]
    
    if palabras_enojo:
        return {
            "reaccion_emocional": "ENOJO_FRUSTRACION",
            "tono": "ENOJO",
            "es_emocional": True,
            "intensidad": "ALTA" if len(palabras_enojo) > 1 else "MEDIA"
        }
    elif palabras_sat:
        return {
            "reaccion_emocional": "SATISFACCION_POSITIVA",
            "tono": "POSITIVO",
            "es_emocional": True,
            "intensidad": "ALTA"
        }
    else:
        return {
            "reaccion_emocional": "NEUTRAL_OPERATIVO",
            "tono": "OPERATIVO",
            "es_emocional": False,
            "intensidad": "NORMAL"
        }
