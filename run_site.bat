@echo off
echo Starting PRIVACY68 Info Website...
start http://localhost:8000
python -m http.server 8000 --directory website
pause