@echo off
chcp 65001 >nul
set "DASHSCOPE_API_KEY=sk-8e5ea74e20a54f88a4f1d2d0d82cd71c"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
python -u backend_server.py 1>backend.log 2>&1
