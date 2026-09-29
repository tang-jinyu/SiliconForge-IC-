@echo off
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root=(Resolve-Path '.').Path;" ^
  "$listener=Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue;" ^
  "if(-not $listener){" ^
  "  $logDir=Join-Path $root 'runs\server'; New-Item -ItemType Directory -Path $logDir -Force | Out-Null;" ^
  "  Start-Process -FilePath (Join-Path $root '.venv\Scripts\python.exe') -ArgumentList @('-m','digital_ic_agent','serve','--host','127.0.0.1','--port','8000') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'stdout.log') -RedirectStandardError (Join-Path $logDir 'stderr.log');" ^
  "  $deadline=(Get-Date).AddSeconds(60); do { Start-Sleep -Milliseconds 500; try { $ready=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/api/health' -TimeoutSec 2 } catch { $ready=$null } } until ($ready -or (Get-Date) -gt $deadline);" ^
  "  if(-not $ready){ Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('网页服务启动失败，请查看 runs\server\stderr.log。','Digital IC Agent') | Out-Null; exit 1 }" ^
  "};" ^
  "Start-Process 'http://127.0.0.1:8000'"

endlocal

