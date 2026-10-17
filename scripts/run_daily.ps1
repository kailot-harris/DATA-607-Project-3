# Daily pipeline run, invoked by the "Data607-JobPipeline-DailyFetch" Scheduled Task.
# Logs to logs/pipeline_<date>.log; exit code reflects whether the whole run crashed
# (individual source failures are handled inside pipeline.py and don't fail the run).

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Program Files\Python311\python.exe"
$LogDir = Join-Path $RepoRoot "logs"
$LogFile = Join-Path $LogDir ("pipeline_{0:yyyy-MM-dd}.log" -f (Get-Date))

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Set-Location $RepoRoot
$Output = & $Python "src\pipeline.py" 2>&1
$ExitCode = $LASTEXITCODE
"=== $(Get-Date -Format o) ===" | Out-File -FilePath $LogFile -Append -Encoding utf8
$Output | Out-File -FilePath $LogFile -Append -Encoding utf8
exit $ExitCode
