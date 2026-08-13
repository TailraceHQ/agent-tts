@echo off
rem Windows counterpart of scripts/tts. See scripts/install-cli.sh.
setlocal
set HERE=%~dp0
call "%HERE%run.cmd" "%HERE%tts_reader\cli.py" %*
exit /b %errorlevel%
