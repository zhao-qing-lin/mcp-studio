# Launch examples/echo_server.py via local .venv (stdio MCP echo server)
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$env:PIP_CACHE_DIR = Join-Path $ProjectRoot ".cache\pip"
New-Item -ItemType Directory -Force -Path $env:PIP_CACHE_DIR | Out-Null

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EchoServer = Join-Path $ProjectRoot "examples\echo_server.py"

if (-not (Test-Path $Python)) {
    Write-Error "未找到 .venv，请先在项目根创建虚拟环境并执行: pip install -e ."
}
if (-not (Test-Path $EchoServer)) {
    Write-Error "未找到 examples\echo_server.py"
}

& $Python $EchoServer @args
exit $LASTEXITCODE
