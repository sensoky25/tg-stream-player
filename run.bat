@echo off
title Telegram Stream Player Server
echo ========================================================
echo       Starting Telegram Stream Player Server...
echo ========================================================
cd /d "%~dp0"

python server.py
pause
