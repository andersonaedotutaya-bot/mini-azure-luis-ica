# Guía de Ejecución: Integrante A (PC Servidor)

**Rol en la Práctica:** Motor NLP, Estadísticas Acumuladas y API Servidor REST  
**Responsabilidades:**
1. Dataset propio en español con jerga de Ica, errores ortográficos y ambigüedades.
2. Entrenamiento y serialización de modelos de intenciones (scikit-learn TF-IDF) y sentimiento.
3. Extracción de entidades de negocio (`AREA`, `PRODUCTO`, `CANTIDAD`, `CODIGO_LOTE`).
4. Microservicio API REST con FastAPI escuchando en `0.0.0.0:8001`.
5. Exposición de endpoints obligatorios:
   - `POST /nlp/analizar-texto` (Sentimiento y Frases clave - simulación Text Analytics).
   - `POST /nlp/entender-comando` (Intención, Confianza, Sentimiento, Entidades, Acción sugerida - simulación LUIS con regla de fallback `< 0.65`).
   - `GET /nlp/estadisticas` (Analítica acumulada).
   - `POST /nlp/estadisticas/reiniciar` (Reinicio de sesión para pruebas limpias).
6. Configuración de firewall y puerto en la PC Servidor.

---

## Paso 1: Instalación de Dependencias
Abrir una terminal en esta carpeta y ejecutar:
```bash
pip install -r requirements.txt
```

---

## Paso 2: Habilitar Puerto 8001 en el Firewall de Windows
Para que la PC Cliente (Integrante B) pueda comunicarse por la red LAN con este servidor:
1. Hacer clic derecho sobre **`configurar_firewall.bat`** y seleccionar **"Ejecutar como Administrador"**.
2. O ejecutar en PowerShell como Administrador:
   ```powershell
   New-NetFirewallRule -DisplayName "MiniAzureLUIS_8001" -Direction Inbound -LocalPort 8001 -Protocol TCP -Action Allow -Profile Any
   ```
f
---

## Paso 3: Obtener tu IP en la Red Local (LAN)
1. Abrir CMD y ejecutar:
   ```cmd
   ipconfig
   ```
2. Buscar la **Dirección IPv4** del adaptador de red conectado al router/switch del laboratorio (ejemplo: `192.168.1.45`).
3. Comparte esa IP a tu compañero (Integrante B) para que la configure en su cliente.

---

## Paso 4: (Opcional) Reentrenar el Modelo
Los modelos ya vienen preentrenados y listos en la carpeta `modelos/`. Si deseas volver a entrenarlos:
- Doble clic en **`entrenar_modelo.bat`** (o `python servidor/entrenar.py`).

---

## Paso 5: Iniciar el Servidor API REST
Doble clic en **`iniciar_servidor.bat`** (o ejecutar en consola):
```bash
python servidor/main.py
```
Verás un mensaje como:
```text
======================================================================
INICIANDO SERVIDOR MINI-AZURE LUIS - AGROEXPORTADORA ICA
IP Servidor en Red LAN : 192.168.1.XX
Puerto                 : 8001
URL de Acceso LAN      : http://192.168.1.XX:8001
Documentación Swagger  : http://192.168.1.XX:8001/docs
======================================================================
```
Mantén esta ventana abierta durante toda la demostración.

---

## Paso 6: Prueba Rápida Local
Para validar que el servidor funciona antes de conectarte con tu compañero:
- Doble clic en **`probar_localmente.bat`** (ejecuta los 6 casos de prueba directamente en el servidor).
