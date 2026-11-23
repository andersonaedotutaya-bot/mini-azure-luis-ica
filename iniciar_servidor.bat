@echo off
title PC SERVIDOR - MINI AZURE LUIS (INTEGRANTE A)
cd /d "%~dp0servidor"
echo ======================================================================
echo INICIANDO SERVIDOR API REST NLP (FastAPI + Uvicorn) en 0.0.0.0:8001
echo Rol: Integrante A (Motor NLP, Estadisticas y API Servidor)
echo ======================================================================
python main.py
pause
