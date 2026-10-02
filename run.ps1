# Prefer normal Python; use the bundled local runtime when Python is not on PATH.
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    & $pythonCommand.Source (Join-Path $PSScriptRoot 'main.py') @args
} else {
    $bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (-not (Test-Path -LiteralPath $bundledPython)) {
        throw 'Python 3.10+ is required. Install Python or provide its full executable path.'
    }
    & $bundledPython (Join-Path $PSScriptRoot 'main.py') @args
}
exit $LASTEXITCODE
