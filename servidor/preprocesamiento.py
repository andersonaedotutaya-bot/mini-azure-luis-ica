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
    """Extrae entidades de negocio del dominio agroexportador (AREA, PRODUCTO, CANTIDAD, CODIGO_LOTE, TEMPERATURA, EQUIPO)."""
    texto_norm = limpiar_texto(texto_original)
    entidades = {}

    # 1. Extracción de ÁREA
    match_area = re.search(
        r"\b(camara\s*(?:de\s*frio)?\s*\d*|linea\s*(?:de\s*empaque|de\s*seleccion|de\s*lavado)?\s*\d+|packing\s*\d*|muelle\s*\d*|tunel\s*(?:de\s*frio|de\s*preenfriado)?\s*\d*|almacen\s*(?:central|de\s*insumos)?|zona\s*de\s*(?:embarque|carga|recepcion|despacho)|patio\s*de\s*maniobras|sala\s*de\s*maquinas|garita|recepcion|puerto|planta|campo|fundo)\b",
        texto_norm,
    )
    if match_area:
        entidades["AREA"] = match_area.group(1).strip()

    # 2. Extracción de PRODUCTO
    match_prod = re.search(
        r"\b(uva\s*(?:red\s*globe|sweet\s*globe|crimson|thompson|autumn\s*crisp|sugarone)?|esparrago[s]?\s*(?:verde|blanco)?|palta\s*(?:hass)?|arandano[s]?|mandarina[s]?|granada[s]?|mango[s]?)\b",
        texto_norm,
    )
    if match_prod:
        entidades["PRODUCTO"] = match_prod.group(1).strip()

    # 3. Extracción de CANTIDAD
    match_cant = re.search(
        r"\b(\d+(?:\.\d+)?\s*(?:cajas|pallets|jabas|kg|kilos|toneladas|contenedores|bolsas|racimos|unidades|bultos|parihuelas|bins|sacos))\b",
        texto_norm,
    )
    if match_cant:
        entidades["CANTIDAD"] = match_cant.group(1).strip()

    # 4. Extracción de CÓDIGO DE LOTE / GUÍA
    match_lote = re.search(
        r"\b(?:lote|cod(?:igo)?|guia)[\s\-:#]*([a-z0-9\-]+)|\b(lt[\s\-:#]*\d+|l-\d+)\b",
        texto_norm,
    )
    if match_lote:
        codigo = (match_lote.group(1) or match_lote.group(2)).strip().upper()
        if len(codigo) >= 2:
            entidades["CODIGO_LOTE"] = codigo

    # 5. Extracción de TEMPERATURA
    match_temp = re.search(
        r"\b(-?\d+(?:\.\d+)?\s*(?:grados|grado|c\b|°c))\b",
        texto_norm,
    )
    if match_temp:
        entidades["TEMPERATURA"] = match_temp.group(1).strip()

    # 6. Extracción de EQUIPO
    match_equipo = re.search(
        r"\b(faja\s*transportadora|impresora\s*(?:de\s*etiquetas)?|compresor|balanza\s*(?:digital)?|lector\s*(?:de\s*codigo)?|montacargas|selladora|termostato|sensor\s*(?:de\s*temperatura|de\s*humedad)?|camion|furgon\s*(?:isotermico)?|contenedor)\b",
        texto_norm,
    )
    if match_equipo:
        entidades["EQUIPO"] = match_equipo.group(1).strip()

    # 7. Extracción de EMOCIÓN / REACCIÓN (cuando hay carga emocional explícita)
    match_emo = re.search(
        r"\b(estafad[ao]s?|estafa[s]?|tonteria[s]?|colmo|porqueria[s]?|basura|incompetenc\w*|harto|furios[ao]s?|enojad[ao]s?|verguenza|burla|desastre|robo|indignad[ao]s?|asco|inept\w*|pesim[ao]s?|horrible|bronca|molest[ao]s?|felicidad|feliz|felices|alegri[a]?|alegre|content[ao]s?|rebos[ao]|revos[ao]|genial|espectacular|agradecid[ao]s?|angustiad[ao]s?|desesperad[ao]s?|preocupad[ao]s?|tristeza|triste|decepcionad[ao]s?|estoy mal|me siento mal)\b",
        texto_norm,
    )
    if match_emo:
        entidades["EMOCION"] = match_emo.group(1).strip()

    return entidades


def tiene_contexto_operativo(texto_original: str, entidades: dict) -> bool:
    """Verifica si el mensaje contiene términos o entidades operativas reales del dominio agroexportador."""
    entidades_operativas = {k: v for k, v in entidades.items() if k != "EMOCION"}
    if entidades_operativas:
        return True
    texto_norm = limpiar_texto(texto_original)
    terminos_operativos = {
        "temperatura", "humedad", "pudricion", "hongos", "calibre", "empaque", "fruta",
        "falla", "detenida", "malogrado", "averiado", "fuga", "mantenimiento", "calibracion",
        "stock", "inventario", "disponible", "insumos", "etiquetas", "zunchos", "quiebre",
        "despacho", "despachar", "embarque", "guia", "remision", "salida", "programar",
        "estiba", "aduana", "exportacion", "muelle", "lote", "caja", "cajas", "pallet", "pallets",
    }
    tokens = set(texto_norm.split())
    return bool(tokens & terminos_operativos)


def extraer_palabras_clave(texto_original: str) -> list:
    """Extrae términos relevantes filtrando palabras vacías (stopwords)."""
    stopwords = {
        "el", "la", "los", "las", "de", "del", "en", "con", "por", "para",
        "un", "una", "se", "a", "y", "que", "esta", "al", "sin", "nos", "hay",
        "lo", "es", "son", "fue", "sus", "su", "como", "mas", "pero", "este",
    }
    tokens = limpiar_texto(texto_original).split()
    return [t for t in tokens if t not in stopwords and len(t) > 2]


def detectar_reaccion_emocional(texto_original: str) -> dict:
    """Detecta tono emocional, enojo, angustia o satisfacción positiva en el mensaje."""
    texto_norm = limpiar_texto(texto_original)

    patrones_enojo = [
        r"\bestafad[ao]s?\b", r"\bestafa[s]?\b", r"\btonteria[s]?\b", r"\bcolmo\b",
        r"\bporqueria[s]?\b", r"\bbasura\b", r"\bincompetenc\w*\b", r"\bharto\b",
        r"\bfurios[ao]s?\b", r"\benoj[ao]s?\b", r"\benojad[ao]s?\b", r"\bverguenza\b",
        r"\bburla\b", r"\bdesastre\b", r"\brobo\b", r"\bindigna\w*\b", r"\basco\b",
        r"\binept\w*\b", r"\bpesim[ao]s?\b", r"\bhorrible\b", r"\bbronca\b", r"\bmolest[ao]s?\b",
    ]
    palabras_enojo = [p for p in patrones_enojo if re.search(p, texto_norm)]

    patrones_satisfaccion = [
        r"\bexcelente\b", r"\bfelicitaciones\b", r"\bimpecable\b", r"\bgran trabajo\b",
        r"\bmaravilla\b", r"\bagradecid[ao]s?\b", r"\bperfecto\b", r"\bsatisfech[ao]s?\b",
        r"\brebos[ao]\b", r"\brevos[ao]\b", r"\brebosando\b", r"\brevosando\b",
        r"\bfelicidad\b", r"\bfeliz\b", r"\bfelices\b",
        r"\balegri[a]?\b", r"\balegre\b", r"\balegres\b",
        r"\bcontento\b", r"\bcontenta\b", r"\bcontentos\b",
        r"\bestoy bien\b", r"\bme siento bien\b", r"\bme siento genial\b",
        r"\bgenial\b", r"\bespectacular\b", r"\bincreible\b", r"\bsuperbien\b",
        r"\bencantad[ao]s?\b", r"\bentusiasmad[ao]s?\b", r"\bemocionad[ao]s?\b",
        r"\borgullos[ao]s?\b", r"\bcontentisim[ao]s?\b", r"\bfelicisim[ao]s?\b",
        r"\bque lindo\b", r"\bque bueno\b", r"\bque bien\b", r"\bexito\b", r"\bexitos\b",
    ]
    palabras_sat = [p for p in patrones_satisfaccion if re.search(p, texto_norm)]

    patrones_angustia = [
        r"\bestoy mal\b", r"\bme siento mal\b", r"\bme siento triste\b",
        r"\bangustiad[ao]s?\b", r"\bdesesperad[ao]s?\b",
        r"\bpreocupad[ao]s?\b", r"\btristeza\b", r"\btriste\b",
        r"\bdesilusion\w*\b", r"\bdecepcionad[ao]s?\b", r"\bdeprimid[ao]s?\b",
        r"\bme siento pesimo\b", r"\bno me siento bien\b",
    ]
    palabras_angustia = [p for p in patrones_angustia if re.search(p, texto_norm)]

    if palabras_enojo:
        return {
            "reaccion_emocional": "ENOJO_FRUSTRACION",
            "tono": "ENOJO",
            "es_emocional": True,
            "intensidad": "ALTA" if len(palabras_enojo) > 1 else "MEDIA",
        }
    elif palabras_sat:
        return {
            "reaccion_emocional": "SATISFACCION_POSITIVA",
            "tono": "POSITIVO",
            "es_emocional": True,
            "intensidad": "ALTA",
        }
    elif palabras_angustia:
        return {
            "reaccion_emocional": "ANGUSTIA_PREOCUPACION",
            "tono": "ANGUSTIA",
            "es_emocional": True,
            "intensidad": "MEDIA",
        }
    else:
        return {
            "reaccion_emocional": "NEUTRAL_OPERATIVO",
            "tono": "OPERATIVO",
            "es_emocional": False,
            "intensidad": "NORMAL",
        }
