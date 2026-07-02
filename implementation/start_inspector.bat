@echo off
REM Start MCP Inspector with the SQLite Lab server
setlocal
set "SCRIPT_DIR=%~dp0"
set "NPM_CACHE=%SCRIPT_DIR%\.npm-cache"
if not exist "%NPM_CACHE%" mkdir "%NPM_CACHE%"
set "NPM_CONFIG_CACHE=%NPM_CACHE%"
npx -y @modelcontextprotocol/inspector python "%SCRIPT_DIR%mcp_server.py"
