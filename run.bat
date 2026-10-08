@echo off
setlocal
cd /d "%~dp0"

echo ================================================================
echo                     SENTINELTRACK
echo ================================================================
echo Starting from: %CD%
echo.

where conda >nul 2>&1
if %ERRORLEVEL%==0 (
    call conda activate PY312 >nul 2>&1
) else if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" (
    call "%USERPROFILE%\miniconda3\condabin\conda.bat" activate PY312 >nul 2>&1
) else if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" (
    call "%USERPROFILE%\anaconda3\condabin\conda.bat" activate PY312 >nul 2>&1
)

where python >nul 2>&1
if not %ERRORLEVEL%==0 (
    echo [ERROR] Python was not found on PATH.
    echo         Activate the PY312 environment and run this file again.
    pause
    exit /b 1
)

echo Using Python:
python -c "import sys; print(sys.executable)"
echo.

python main.py %*
set EXIT_CODE=%ERRORLEVEL%

if not "%EXIT_CODE%"=="0" (
    echo.
    echo SentinelTrack exited with code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
