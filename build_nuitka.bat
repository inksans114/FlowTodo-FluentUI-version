@echo off
setlocal EnableExtensions

rem One-click Nuitka build for FlowTodo RinUI.
set "ROOT=%~dp0"
cd /d "%ROOT%"
set "PYTHONPATH=%ROOT%vendor;%PYTHONPATH%"

rem Prefer the project's existing virtual environments.
set "PYTHON_EXE="
if exist "%ROOT%.venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%ROOT%venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%ROOT%..\FlowTodo\.venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%..\FlowTodo\.venv\Scripts\python.exe"

if not defined PYTHON_EXE (
    echo [ERROR] Could not find a Python virtual environment.
    echo Create .venv or venv in this project, or update PYTHON_EXE in this file.
    pause
    exit /b 1
)

echo [INFO] Python: %PYTHON_EXE%

rem Make sure the application dependencies are present in this environment.
echo [INFO] Checking application dependencies...
"%PYTHON_EXE%" -m pip install --disable-pip-version-check --no-cache-dir -r "%ROOT%requirements.txt"
if errorlevel 1 goto :build_failed

rem Audio is optional. island.py has a safe no-op fallback when playsound is
rem unavailable, so a broken audio wheel cannot block the application build.
"%PYTHON_EXE%" -c "import playsound" >nul 2>&1
if errorlevel 1 echo [WARN] playsound is not installed; notifications will be silent.

rem Install Nuitka into the selected environment when it is missing.
"%PYTHON_EXE%" -c "import nuitka" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Nuitka is missing. Installing it...
    "%PYTHON_EXE%" -m pip install --disable-pip-version-check --no-cache-dir --upgrade --index-url https://pypi.org/simple nuitka
    if errorlevel 1 goto :build_failed
)

rem Remove only generated Nuitka output from previous builds.
if exist "%ROOT%dist" rmdir /s /q "%ROOT%dist"
if exist "%ROOT%build" rmdir /s /q "%ROOT%build"
mkdir "%ROOT%dist"

echo [INFO] Building FlowTodo...
"%PYTHON_EXE%" -m nuitka app.py ^
    --mingw64 ^
    --standalone ^
    --enable-plugin=pyside6 ^
    --include-qt-plugins=qml ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico="%ROOT%logopromax.ico" ^
    --output-dir="%ROOT%dist" ^
    --output-filename=FlowTodo.exe ^
    --include-package=RinUI ^
    --include-package-data=RinUI ^
    --include-data-dir="%ROOT%qml=qml" ^
    --include-data-dir="%ROOT%vendor=vendor" ^
    --include-data-files="%ROOT%logopromax.ico=logopromax.ico" ^
    --include-data-files="%ROOT%audio.mp3=audio.mp3" ^
    --nofollow-import-to=PySide6.QtWebEngineCore ^
    --nofollow-import-to=PySide6.QtWebEngineWidgets ^
    --nofollow-import-to=PySide6.QtWebChannel ^
    --nofollow-import-to=playsound ^
    --assume-yes-for-downloads

if errorlevel 1 goto :build_failed

echo.
echo [OK] Build completed.
set "BUILT_EXE="
if exist "%ROOT%dist\app.dist\FlowTodo.exe" set "BUILT_EXE=%ROOT%dist\app.dist\FlowTodo.exe"
if not defined BUILT_EXE if exist "%ROOT%dist\FlowTodo.dist\FlowTodo.exe" set "BUILT_EXE=%ROOT%dist\FlowTodo.dist\FlowTodo.exe"
if not defined BUILT_EXE (
    echo [ERROR] Build finished but FlowTodo.exe was not found under dist.
    pause
    exit /b 1
)
echo [OK] Output: %BUILT_EXE%
echo [INFO] Creating updater release archive...
"%PYTHON_EXE%" "%ROOT%package_release.py" "%BUILT_EXE%"
if errorlevel 1 (
    echo [ERROR] Failed to create the updater ZIP.
    pause
    exit /b 1
)
echo [OK] Release asset created under %ROOT%dist
echo.
if /i "%~1"=="--no-run" exit /b 0
start "" "%BUILT_EXE%"
pause
exit /b 0

:build_failed
echo.
echo [ERROR] Nuitka build failed. Scroll up to see the first error.
pause
exit /b 1
