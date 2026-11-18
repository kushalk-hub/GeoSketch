@echo off
title GeoSketch Cloudflare Public Tunnel
cd /d "%~dp0"
backend\.venv314\Scripts\python.exe start_public_tunnel.py
pause
