@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0blender_path.local.cmd" call "%~dp0blender_path.local.cmd"

if not defined BLENDER_EXE (
    for /f "delims=" %%I in ('where blender 2^>nul') do (
        if not defined BLENDER_EXE set "BLENDER_EXE=%%I"
    )
)

if not defined BLENDER_EXE (
    for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender*") do (
        if exist "%%D\blender.exe" set "BLENDER_EXE=%%D\blender.exe"
    )
)

if not defined BLENDER_EXE (
    echo Blender was not found automatically.
    echo Copy blender_path.local.example.cmd to blender_path.local.cmd
    echo and set BLENDER_EXE to your blender.exe path.
    pause
    exit /b 1
)

start "" /D "%~dp0" "%BLENDER_EXE%" "section_lab.blend" --python "section_lab_blender.py"
endlocal
