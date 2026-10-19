@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem PyInstaller onedir comparison build. Never use Nuitka's dist directory.
set "ROOT=%~dp0"
cd /d "%ROOT%"
if errorlevel 1 exit /b 1
set "PYTHONPATH=%ROOT%vendor;%PYTHONPATH%"
set "CHECK_ONLY=0"
set "NO_PAUSE=0"
set "NO_ZIP=0"
for %%A in (%*) do (
    if /i "%%~A"=="--check" set "CHECK_ONLY=1"
    if /i "%%~A"=="--no-run" set "NO_PAUSE=1"
    if /i "%%~A"=="--no-zip" set "NO_ZIP=1"
)

if not defined PYTHON_EXE if exist "%ROOT%.venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%ROOT%venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%ROOT%..\FlowTodo\.venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%..\FlowTodo\.venv\Scripts\python.exe"
if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
)
if not defined PYTHON_EXE (
    echo [ERROR] Python was not found. Set PYTHON_EXE to Python 3.12 x64.
    goto :build_failed
)
echo [INFO] Python: %PYTHON_EXE%
"%PYTHON_EXE%" --version
if errorlevel 1 goto :build_failed
if "%CHECK_ONLY%"=="1" goto :check_only

echo [INFO] Checking application dependencies...
"%PYTHON_EXE%" -m pip install --disable-pip-version-check --no-cache-dir -r "%ROOT%requirements.txt"
if errorlevel 1 goto :build_failed
echo [INFO] Checking PyInstaller 6...
"%PYTHON_EXE%" -m pip install --disable-pip-version-check "PyInstaller>=6,<7"
if errorlevel 1 goto :build_failed
"%PYTHON_EXE%" "%ROOT%tools\prepare_supervision_models.py"
if errorlevel 1 goto :build_failed
"%PYTHON_EXE%" "%ROOT%tools\build_check.py" --builder pyinstaller
if errorlevel 1 goto :build_failed

set "BUILD_OUTPUT="
for /f "delims=" %%D in ('""%PYTHON_EXE%" "%ROOT%tools\build_check.py" --builder pyinstaller --prepare-output"') do set "BUILD_OUTPUT=%%D"
if not defined BUILD_OUTPUT goto :build_failed
if not exist "%BUILD_OUTPUT%\" goto :build_failed
echo [INFO] Separate build directory: %BUILD_OUTPUT%

rem Keep data beside the exe to match the application's __file__ resource paths.
rem Standard PyInstaller Qt hooks collect WebEngine resources and multimedia DLLs.
"%PYTHON_EXE%" -m PyInstaller "%ROOT%app.py" ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --noupx ^
    --contents-directory . ^
    --name FlowTodo ^
    --icon "%ROOT%logopromax.ico" ^
    --paths "%ROOT%vendor" ^
    --distpath "%BUILD_OUTPUT%" ^
    --workpath "%BUILD_OUTPUT%\work" ^
    --specpath "%BUILD_OUTPUT%\spec" ^
    --additional-hooks-dir "%ROOT%vendor\RinUI\hooks" ^
    --hidden-import ai_service_settings ^
    --hidden-import cloud_client ^
    --hidden-import cloud_controller ^
    --hidden-import cloud_records ^
    --hidden-import cloud_sync ^
    --hidden-import win32crypt ^
    --hidden-import startup_manager ^
    --hidden-import win32com.client ^
    --hidden-import PySide6.QtWebEngineWidgets ^
    --hidden-import PySide6.QtWebEngineCore ^
    --hidden-import PySide6.QtWebChannel ^
    --hidden-import PySide6.QtNetwork ^
    --hidden-import PySide6.QtMultimedia ^
    --hidden-import PIL.ImageGrab ^
    --hidden-import mediapipe ^
    --hidden-import rapidocr_onnxruntime ^
    --collect-submodules mediapipe.tasks.python.vision ^
    --collect-data mediapipe ^
    --collect-binaries mediapipe ^
    --collect-data rapidocr_onnxruntime ^
    --collect-binaries onnxruntime ^
    --collect-data RinUI ^
    --copy-metadata mediapipe ^
    --exclude-module playsound ^
    --exclude-module mediapipe.tasks.python.test ^
    --exclude-module PIL.ImageTk ^
    --exclude-module PIL.ImageQt ^
    --exclude-module PyQt5 ^
    --exclude-module PyQt6 ^
    --exclude-module PySide2 ^
    --add-data "%ROOT%qml:qml" ^
    --add-data "%ROOT%focus-studio:focus-studio" ^
    --add-data "%ROOT%supervision-models:supervision-models" ^
    --add-data "%ROOT%supervision-web:supervision-web" ^
    --add-data "%ROOT%tools\allow_phone_camera.ps1:tools" ^
    --add-data "%ROOT%i18n:i18n" ^
    --add-data "%ROOT%vendor\RinUI:vendor/RinUI" ^
    --add-data "%ROOT%logopromax.ico:." ^
    --add-data "%ROOT%audio.mp3:."
if errorlevel 1 goto :build_failed

set "BUILT_EXE=%BUILD_OUTPUT%\FlowTodo\FlowTodo.exe"
if not exist "%BUILT_EXE%" goto :build_failed
"%PYTHON_EXE%" "%ROOT%tools\build_check.py" --builder pyinstaller --package-root "%BUILD_OUTPUT%\FlowTodo"
if errorlevel 1 goto :build_failed
if "%NO_ZIP%"=="1" goto :build_done
echo [INFO] Creating release ZIP; this is separate from packaging time.
"%PYTHON_EXE%" "%ROOT%package_release.py" "%BUILT_EXE%"
if errorlevel 1 goto :build_failed
:build_done
echo.
echo [OK] Output: %BUILT_EXE%
echo [INFO] Run the exe manually to compare startup speed. Keep its complete folder.
if "%NO_PAUSE%"=="0" pause
exit /b 0

:check_only
rem Read-only: no installation, model download, output creation or app startup.
"%PYTHON_EXE%" "%ROOT%tools\build_check.py" --builder pyinstaller
if errorlevel 1 goto :build_failed
echo [OK] Preflight passed. No build was started.
exit /b 0

:build_failed
echo.
echo [ERROR] PyInstaller build or preflight failed. See the first error above.
if "%CHECK_ONLY%"=="0" if "%NO_PAUSE%"=="0" pause
exit /b 1
