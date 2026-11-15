@echo off
REM Sincroniza o Open Finance. Usado pelo Agendador de Tarefas do Windows.
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
python -m financas sincronizar >> sincronizacao.log 2>&1
