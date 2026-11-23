@echo off
title PRUEBA LOCAL DE CASOS - INTEGRANTE A
cd /d "%~dp0servidor"
echo ======================================================================
echo EJECUTANDO PRUEBA LOCAL DE LOS 6 CASOS DE EVALUACION
echo ======================================================================
python probar_casos.py
pause
