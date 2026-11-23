@echo off
title CONFIGURAR FIREWALL - PUERTO 8001
echo ======================================================================
echo HABILITANDO REGLA DE ENTRADA TCP 8001 EN WINDOWS FIREWALL
echo Nota: Este archivo debe ejecutarse con 'Clic derecho -> Ejecutar como Administrador'
echo ======================================================================
netsh advfirewall firewall add rule name="MiniAzureLUIS_8001" dir=in action=allow protocol=TCP localport=8001
echo.
echo Regla agregada exitosamente para permitir conexiones desde la PC Cliente.
pause
