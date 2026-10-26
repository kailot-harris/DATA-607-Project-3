# Daily pipeline run, invoked by the "Data607-JobPipeline-DailyFetch" Scheduled Task.
# Logs to logs/pipeline_<date>.log; exit code reflects whether the whole run crashed
# (individual source failures are handled inside pipeline.py and don't fail the run).

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
$LogFile = Join-Path $LogDir ("pipeline_{0:yyyy-MM-dd}.log" -f (Get-Date))

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Resolve the interpreter instead of hardcoding a path, so the pipeline runs on a
# teammate's machine too. Order: $env:DATA607_PYTHON override, then python/py on
# PATH. A candidate has to actually report "Python 3" to count -- on Windows a bare
# "python" often resolves to the Microsoft Store stub, which exits without running.
function Resolve-Python {
    $candidates = @()
    if ($env:DATA607_PYTHON) { $candidates += $env:DATA607_PYTHON }
    foreach ($name in @("python", "py")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source) { $candidates += $cmd.Source }
    }
    foreach ($candidate in $candidates) {
        try { $version = & $candidate --version 2>&1 } catch { continue }
        if ($LASTEXITCODE -eq 0 -and $version -match "Python 3") { return $candidate }
    }
    return $null
}

$Python = Resolve-Python
if (-not $Python) {
    $message = "=== $(Get-Date -Format o) ===`nERROR: no working Python 3 found. " +
               "Install Python 3 and put it on PATH, or set DATA607_PYTHON to its full path."
    $message | Out-File -FilePath $LogFile -Append -Encoding utf8
    Write-Error $message
    exit 1
}

Set-Location $RepoRoot

# Storage guard: the shared Neon project caps at 512 MB, and the Barousse 2023
# dataset leaves limited headroom. Skip the fetch if a pre-flight check shows
# less than MIN_FREE_MB free (exit 1). Any other failure of the guard itself
# is logged and does NOT block the run (fail open).
$Guard = & $Python (Join-Path $PSScriptRoot "db_size_guard.py") 2>&1
$GuardExit = $LASTEXITCODE
"$(Get-Date -Format o) db-size-guard output: $Guard" | Out-File -FilePath $LogFile -Append -Encoding utf8
if ($GuardExit -eq 1) {
    "$(Get-Date -Format o) SKIPPED fetch: DB within 20 MB of the 512 MB cap." |
        Out-File -FilePath $LogFile -Append -Encoding utf8
    Write-Output "Fetch skipped: DB near storage cap (see guard's log above)."
    exit 0
}

$Output = & $Python "src\pipeline.py" --backend postgres 2>&1
$ExitCode = $LASTEXITCODE
"=== $(Get-Date -Format o) === (python: $Python)" | Out-File -FilePath $LogFile -Append -Encoding utf8
$Output | Out-File -FilePath $LogFile -Append -Encoding utf8
exit $ExitCode
