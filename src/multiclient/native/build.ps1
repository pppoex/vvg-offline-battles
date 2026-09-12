# Build x64 native multiclient artifacts for WoT 2.3.1.2.
# Outputs under native/out/ and dist/multiclient/.

$ErrorActionPreference = 'Stop'

$NativeDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = [System.IO.Path]::GetFullPath((Join-Path $NativeDir '..\..\..'))
$OutDir = Join-Path $NativeDir 'out'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$VsDevCmd = 'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat'
if (-not (Test-Path $VsDevCmd)) {
    throw "VsDevCmd.bat not found: $VsDevCmd"
}

$guardSrc = Join-Path $NativeDir 'instance_guard.c'
$starterSrc = Join-Path $NativeDir 'worker_starter.c'
$guardOut = Join-Path $OutDir 'vvg_instance_guard_native.pyd'
$starterOut = Join-Path $OutDir 'vvg_worker_starter.exe'

$batch = Join-Path $OutDir 'build_native.bat'
$batchBody = @'
@echo off
setlocal
call "%VSDEVCMD%" -arch=amd64 -host_arch=amd64 >nul
if errorlevel 1 exit /b 10

set OUTDIR=%~dp0
set SRC=%~dp0..\instance_guard.c
set STARTER=%~dp0..\worker_starter.c
set MSVCDIR=C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Tools\MSVC\14.51.36231
set SDKDIR=C:\Program Files (x86)\Windows Kits\10\Include\10.0.26100.0
set SDKLIB=C:\Program Files (x86)\Windows Kits\10\Lib\10.0.26100.0

cl /nologo /LD /O2 /W3 /D_CRT_SECURE_NO_WARNINGS /D_WIN32_WINNT=0x0601 ^
  /I"%MSVCDIR%\include" /I"%SDKDIR%\ucrt" /I"%SDKDIR%\um" /I"%SDKDIR%\shared" ^
  "%SRC%" ^
  /Fe"%OUTDIR%vvg_instance_guard_native.pyd" ^
  /Fo"%OUTDIR%instance_guard.obj" ^
  /link /DLL /NOIMPLIB /SUBSYSTEM:WINDOWS ^
  /LIBPATH:"%MSVCDIR%\lib\x64" ^
  /LIBPATH:"%SDKLIB%\ucrt\x64" ^
  /LIBPATH:"%SDKLIB%\um\x64" ^
  kernel32.lib user32.lib advapi32.lib
if errorlevel 1 exit /b 11

if exist "%OUTDIR%vvg_instance_guard_native.dll" (
  move /Y "%OUTDIR%vvg_instance_guard_native.dll" "%OUTDIR%vvg_instance_guard_native.pyd" >nul
)

cl /nologo /O2 /W3 /D_CRT_SECURE_NO_WARNINGS /DUNICODE /D_UNICODE /D_WIN32_WINNT=0x0601 ^
  /I"%MSVCDIR%\include" /I"%SDKDIR%\ucrt" /I"%SDKDIR%\um" /I"%SDKDIR%\shared" ^
  "%STARTER%" ^
  /Fe"%OUTDIR%vvg_worker_starter.exe" ^
  /Fo"%OUTDIR%worker_starter.obj" ^
  /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup ^
  /LIBPATH:"%MSVCDIR%\lib\x64" ^
  /LIBPATH:"%SDKLIB%\ucrt\x64" ^
  /LIBPATH:"%SDKLIB%\um\x64" ^
  kernel32.lib user32.lib advapi32.lib
if errorlevel 1 exit /b 12

exit /b 0
'@

# VSDEVCMD must expand inside the bat, not PowerShell.
$batchBody = $batchBody.Replace('%VSDEVCMD%', $VsDevCmd)
Set-Content -Path $batch -Value $batchBody -Encoding ASCII

Write-Host "Running $batch"
cmd /c "`"$batch`""
if ($LASTEXITCODE -ne 0) {
    throw "native build failed with exit $LASTEXITCODE"
}

if (-not (Test-Path $guardOut)) {
    throw "missing $guardOut"
}
if (-not (Test-Path $starterOut)) {
    throw "missing $starterOut"
}

$dropDir = Join-Path $Root 'dist\multiclient'
New-Item -ItemType Directory -Force -Path $dropDir | Out-Null
Copy-Item -Force $guardOut (Join-Path $dropDir 'vvg_instance_guard_native.pyd')
Copy-Item -Force $starterOut (Join-Path $dropDir 'vvg_worker_starter.exe')

Write-Host "Built:"
Write-Host "  $guardOut"
Write-Host "  $starterOut"
Write-Host "  $dropDir"
