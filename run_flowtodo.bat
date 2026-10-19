@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 exit /b 1

rem Use an already prepared environment. This launcher never installs or builds.
if defined PYTHON_EXE goto :selected
if exist "%~dp0..\FlowTodo\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\FlowTodo\.venv\Scripts\python.exe"
    goto :selected
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :selected
)
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
    goto :selected
)
echo [ERROR] Set PYTHON_EXE to the Python used to run FlowTodo.
pause
exit /b 1

:selected
echo [INFO] Python: %PYTHON_EXE%
"%PYTHON_EXE%" "%~dp0tools\check_supervision_environment.py"
if errorlevel 1 (
    pause
    exit /b 1
)
"%PYTHON_EXE%" "%~dp0app.py"
if errorlevel 1 pause
