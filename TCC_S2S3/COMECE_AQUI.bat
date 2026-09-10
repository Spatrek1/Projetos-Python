@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ================================================================
echo  VERIFICACAO DO PROJETO - TCC S2/S3
echo  Pasta: %CD%
echo ================================================================
echo.

echo [1/3] Verificando bibliotecas instaladas...
echo.
python -c "import sys; sys.path.insert(0,'src'); import fraude_s2s3; fraude_s2s3.verificar_ambiente()"
if errorlevel 1 goto erro

echo.
echo [2/3] Rodando os testes do pipeline (leva 1-2 minutos)...
echo.
python testes\test_pipeline.py
if errorlevel 1 goto erro

echo.
echo [3/3] Diagnosticando acesso ao IF.data / Banco Central...
echo.
python testes\diagnostico_rede.py

echo.
echo ================================================================
echo  Fim. Envie a saida acima para analise.
echo ================================================================
goto fim

:erro
echo.
echo ----------------------------------------------------------------
echo  Uma etapa falhou. A mensagem acima indica o que corrigir.
echo  Se faltar biblioteca:  python -m pip install -r requirements.txt
echo ----------------------------------------------------------------

:fim
echo.
pause
