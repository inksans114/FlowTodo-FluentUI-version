@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem One-click Nuitka build for FlowTodo RinUI.
set "ROOT=%~dp0"
cd /d "%ROOT%"
if errorlevel 1 exit /b 1
set "PYTHONPATH=%ROOT%vendor;%PYTHONPATH%"
set "CHECK_ONLY=0"
set "NO_RUN=0"
if /i "%~1"=="--check" set "CHECK_ONLY=1"
if /i "%~2"=="--check" set "CHECK_ONLY=1"
if /i "%~1"=="--no-run" set "NO_RUN=1"
if /i "%~2"=="--no-run" set "NO_RUN=1"

rem Honor an explicit PYTHON_EXE override, then prefer existing virtual environments.
if not defined PYTHON_EXE if exist "%ROOT%.venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%ROOT%venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%ROOT%..\FlowTodo\.venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT%..\FlowTodo\.venv\Scripts\python.exe"

if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
)
if not defined PYTHON_EXE (
    echo [ERROR] Python was not found. Create .venv or set PYTHON_EXE to Python 3.12 x64.
    goto :build_failed
)

echo [INFO] Python: %PYTHON_EXE%
"%PYTHON_EXE%" --version
if errorlevel 1 goto :build_failed
if "%CHECK_ONLY%"=="1" goto :check_only

rem Make sure the application dependencies are present in this environment.
echo [INFO] Checking application dependencies...
"%PYTHON_EXE%" -m pip install --disable-pip-version-check --no-cache-dir -r "%ROOT%requirements.txt"
if errorlevel 1 goto :build_failed

rem Notifications and rain use Qt Multimedia; playsound is not required.
echo [INFO] Preparing local supervision models...
"%PYTHON_EXE%" "%ROOT%tools\prepare_supervision_models.py"
if errorlevel 1 goto :build_failed

rem Install Nuitka into the selected environment when it is missing.
"%PYTHON_EXE%" -c "import nuitka" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Nuitka is missing. Installing it...
    "%PYTHON_EXE%" -m pip install --disable-pip-version-check --no-cache-dir --upgrade --index-url https://pypi.org/simple nuitka
    if errorlevel 1 goto :build_failed
)

"%PYTHON_EXE%" "%ROOT%tools\build_check.py"
if errorlevel 1 goto :build_failed

rem Keep previous builds and ZIPs. Each run gets its own output directory.
set "BUILD_OUTPUT="
for /f "delims=" %%D in ('""%PYTHON_EXE%" "%ROOT%tools\build_check.py" --prepare-output"') do set "BUILD_OUTPUT=%%D"
if not defined BUILD_OUTPUT goto :build_failed
if not exist "%BUILD_OUTPUT%\" goto :build_failed
echo [INFO] Build directory: %BUILD_OUTPUT%

echo [INFO] Building FlowTodo...
echo [INFO] Compiling with two parallel jobs. Close unused apps to leave memory for GCC.
"%PYTHON_EXE%" -m nuitka app.py ^
    --mingw64 ^
    --jobs=2 ^
    --standalone ^
    --enable-plugin=pyside6 ^
    --user-package-configuration-file="%ROOT%tools\supervision.nuitka-package.config.yml" ^
    --include-qt-plugins=qml,multimedia ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico="%ROOT%logopromax.ico" ^
    --output-dir="%BUILD_OUTPUT%" ^
    --output-filename=FlowTodo.exe ^
    --include-module=main ^
    --include-module=backend ^
    --include-module=app_paths ^
    --include-module=runtime_diagnostics ^
    --include-module=startup_manager ^
    --include-module=compat_backend ^
    --include-module=island ^
    --include-module=notes ^
    --include-module=ai_library ^
    --include-module=ai_planning ^
    --include-module=ai_output_language ^
    --include-module=ai_service_settings ^
    --include-module=account_state ^
    --include-module=cloud_client ^
    --include-module=cloud_controller ^
    --include-module=cloud_records ^
    --include-module=cloud_sync ^
    --include-module=win32crypt ^
    --include-module=guided_focus ^
    --include-module=focus_journey ^
    --include-module=focus_rhythm ^
    --include-module=focus_weather ^
    --include-module=focus_studio_window ^
    --include-module=quick_capture ^
    --include-module=task_archive ^
    --include-module=task_relations ^
    --include-module=speech_input ^
    --include-module=system_dictation ^
    --include-module=supervision ^
    --include-module=supervision_policy ^
    --include-module=supervision_vision ^
    --include-module=supervision_calibration ^
    --include-module=supervision_environment ^
    --include-module=phone_camera ^
    --include-module=phone_camera_server ^
    --include-module=phone_network ^
    --include-module=dpi_utils ^
    --include-module=i18n_runtime ^
    --include-module=notification_audio ^
    --include-module=updater ^
    --include-module=update_installer ^
    --include-module=update_files ^
    --include-module=version ^
    --include-package=RinUI ^
    --include-package=PySide6.QtWebEngineWidgets ^
    --include-package=PySide6.QtWebEngineCore ^
    --include-package=PySide6.QtWebChannel ^
    --include-package=PySide6.QtNetwork ^
    --include-package=PySide6.QtMultimedia ^
    --include-package=mediapipe ^
    --include-package=rapidocr_onnxruntime ^
    --include-package=onnxruntime ^
    --include-package=PIL ^
    --include-package=cryptography ^
    --include-package=qrcode ^
    --include-package=win32com.client ^
    --include-package-data=mediapipe ^
    --include-package-data=RinUI ^
    --include-data-dir="%ROOT%qml=qml" ^
    --include-data-dir="%ROOT%focus-studio=focus-studio" ^
    --include-data-dir="%ROOT%supervision-models=supervision-models" ^
    --include-data-dir="%ROOT%supervision-web=supervision-web" ^
    --include-data-files="%ROOT%tools\allow_phone_camera.ps1=tools/allow_phone_camera.ps1" ^
    --include-data-dir="%ROOT%i18n=i18n" ^
    --include-data-dir="%ROOT%vendor=vendor" ^
    --include-data-files="%ROOT%logopromax.ico=logopromax.ico" ^
    --include-data-files="%ROOT%audio.mp3=audio.mp3" ^
    --include-data-files="%ROOT%start_compatibility.bat=start_compatibility.bat" ^
    --report="%BUILD_OUTPUT%\compilation-report.xml" ^
    --nofollow-import-to=playsound ^
    --nofollow-import-to=mediapipe.tasks.python.test ^
    --nofollow-import-to=PIL.ImageTk ^
    --nofollow-import-to=PIL.ImageQt ^
    --assume-yes-for-downloads

if errorlevel 1 goto :build_failed

echo.
echo [OK] Build completed.
set "BUILT_EXE="
if exist "%BUILD_OUTPUT%\app.dist\FlowTodo.exe" set "BUILT_EXE=%BUILD_OUTPUT%\app.dist\FlowTodo.exe"
if not defined BUILT_EXE if exist "%BUILD_OUTPUT%\FlowTodo.dist\FlowTodo.exe" set "BUILT_EXE=%BUILD_OUTPUT%\FlowTodo.dist\FlowTodo.exe"
if not defined BUILT_EXE (
    echo [ERROR] Build finished but FlowTodo.exe was not found in this build directory.
    goto :build_failed
)
echo [OK] Output: %BUILT_EXE%
for %%E in ("%BUILT_EXE%") do set "PACKAGE_DIR=%%~dpE"
"%PYTHON_EXE%" "%ROOT%tools\build_check.py" --package-root "%PACKAGE_DIR%."
if errorlevel 1 goto :build_failed
echo [INFO] Creating updater release archive...
"%PYTHON_EXE%" "%ROOT%package_release.py" "%BUILT_EXE%"
if errorlevel 1 (
    echo [ERROR] Failed to create the updater ZIP.
    goto :build_failed
)
echo [OK] Send the complete FlowTodo-Windows-x64-*.zip from %BUILD_OUTPUT%
echo [INFO] Do not send FlowTodo.exe alone; QML, WebEngine and audio files are required.
echo.
if "%NO_RUN%"=="1" exit /b 0
start "" "%BUILT_EXE%"
pause
exit /b 0

:check_only
rem No pip install, compilation, cleanup or application startup in check mode.
"%PYTHON_EXE%" "%ROOT%tools\build_check.py"
if errorlevel 1 goto :build_failed
echo [OK] Preflight passed. No build was started.
exit /b 0

:build_failed
echo.
echo [ERROR] Build or preflight failed. Scroll up to see the first error.
if "%CHECK_ONLY%"=="0" if "%NO_RUN%"=="0" pause
exit /b 1
