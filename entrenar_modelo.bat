@echo off
title ENTRENAR MODELO NLP - INTEGRANTE A
cd /d "%~dp0servidor"
echo ======================================================================
echo ENTRENANDO MODELO DE INTENCIONES Y SENTIMIENTO (SCIKIT-LEARN)
echo Dataset: dataset/corpus_agro_ica.csv (160 ejemplos balanceados)
echo ======================================================================
python entrenar.py
echo.
echo Entrenamiento finalizado. Los modelos se guardaron en la carpeta modelos/
pause
