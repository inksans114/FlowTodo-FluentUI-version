@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 exit /b 1
if not exist "%~dp0FlowTodo.exe" (
    echo Put this file next to FlowTodo.exe in the fully extracted application folder.
    pause
    exit /b 1
)
rem These switches affect only this launch, not saved settings or user data.
set "QT_QUICK_BACKEND=software"
set "QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu --disable-gpu-compositing"
echo Starting FlowTodo with software rendering.
echo Runtime logs: %%LOCALAPPDATA%%\FlowTodo\logs
start "" /wait "%~dp0FlowTodo.exe"
set "FLOWTODO_EXIT_CODE=%ERRORLEVEL%"
echo FlowTodo exited with code %FLOWTODO_EXIT_CODE%.
pause
exit /b %FLOWTODO_EXIT_CODE%
