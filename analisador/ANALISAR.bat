@echo off
chcp 65001 >nul
title Analisador Profissional de Acoes - B3
cd /d "%~dp0"

REM ----------------------------------------------------------------------------
REM  Execucao simplificada: duplo-clique abre o menu.
REM  Na primeira vez instala as dependencias que faltarem (uma unica vez).
REM ----------------------------------------------------------------------------

set PY=python
where py >nul 2>nul && set PY=py

if not exist ".deps_ok" (
    echo.
    echo === Primeira execucao: preparando dependencias (pode demorar alguns minutos) ===
    %PY% -m pip install --upgrade pip >nul 2>nul
    %PY% -m pip install -r requirements.txt
    REM hmmlearn e opcional; se falhar no Python 3.14, o programa usa o fallback.
    %PY% -m pip install hmmlearn >nul 2>nul
    echo ok> ".deps_ok"
    echo === Dependencias prontas ===
    echo.
)

%PY% analisar.py %*

echo.
pause
