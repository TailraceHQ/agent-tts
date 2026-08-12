@echo off
rem Cross-platform Python launcher (Windows side); see the POSIX `run` script.
rem cmd.exe resolves `.../scripts/run` to this file via PATHEXT. We locate a
rem Python interpreter and run it on the given arguments, exiting 0 when none
rem is found so a Stop hook never fails a turn.
setlocal
where python3 >nul 2>nul
if %errorlevel%==0 (
  python3 %*
  exit /b %errorlevel%
)
where python >nul 2>nul
if %errorlevel%==0 (
  python %*
  exit /b %errorlevel%
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 %*
  exit /b %errorlevel%
)
echo agent-tts: no python/py interpreter found on PATH 1>&2
exit /b 0
