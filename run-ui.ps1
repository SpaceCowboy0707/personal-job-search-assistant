$ErrorActionPreference = 'Stop'
$uiPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $uiPython)) {
    throw 'Create .venv and install requirements-ui.txt first. See README.md.'
}
Push-Location $PSScriptRoot
try {
    & $uiPython -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
} finally {
    Pop-Location
}
exit $LASTEXITCODE
