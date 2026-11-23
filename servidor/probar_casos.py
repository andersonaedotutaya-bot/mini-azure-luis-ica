import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from main import entender_comando, analizar_texto, MensajeRequest, obtener_estadisticas

casos = [
    "La camara de frio 2 subio a 9 grados con 120 cajas de uva red globe",
    "Se malogro la faja transp de la linea 1 urge tecnico",
    "Cuantas jabas de esparrago verde tenemos en stock hoy",
    "Programar salida de camion con 20 pallets lote L-804 al puerto",
    "Humdad alta en packing 3 revisen las cajas de esparrago verde",
    "Oe revisa eso rapido antes q vengan",
    "Me siento estafado esto es una tonteria",
    "Esto es el colmo que incompetencia con este despacho",
    "Me siento estafado con este lote L-501 la uva esta podrida y en mal estado"
]

print("="*65)
print("TEST DE ENDPOINT /nlp/entender-comando CON CASOS OPERATIVOS Y EMOCIONALES")
print("="*65)

for idx, texto in enumerate(casos, 1):
    req = MensajeRequest(texto=texto)
    res = entender_comando(req)
    print(f"\n--- CASO #{idx} ---")
    print(f"Texto original      : {res['texto_original']}")
    print(f"Intención           : {res['intencion']} (confianza: {res['confianza_intencion']})")
    print(f"Sentimiento         : {res['sentimiento']}")
    print(f"Reacción Emocional  : {res.get('reaccion_emocional')} (Tono: {res.get('tono')})")
    print(f"Entidades           : {res['entidades']}")
    print(f"Acción sugerida     : {res['accion_sugerida']}")

print("\n" + "="*65)
print("TEST DE ENDPOINT /nlp/analizar-texto CON QUEJA EMOCIONAL")
print("="*65)
res_analisis = analizar_texto(MensajeRequest(texto="Me siento estafado esto es una tonteria una porqueria de atencion"))
print(res_analisis)
