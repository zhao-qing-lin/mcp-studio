# Launch MCP Studio from project root using local .venv
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$env:PIP_CACHE_DIR = Join-Path $ProjectRoot ".cache\pip"
New-Item -ItemType Directory -Force -Path $env:PIP_CACHE_DIR | Out-Null

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "未找到 .venv，请先在项目根创建虚拟环境并执行: pip install -e ."
}

& $Python -m mcp_studio @args
exit $LASTEXITCODE
