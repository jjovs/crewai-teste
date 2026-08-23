<#
.SYNOPSIS
    Prepara o ambiente e roda uma rodada real da equipe, do zero, no Windows.

.DESCRIPTION
    Faz na ordem: atualiza o repo, garante a ANTHROPIC_API_KEY no .env, cria o
    .venv e instala as dependencias, clona o ConnoSr, confirma que a chave e
    lida de verdade pelo python-dotenv e so entao dispara a rodada.

    Cada etapa e idempotente: rodar de novo nao refaz o que ja esta pronto.

    A rodada e sempre em modo proposta (permitir_escrita=False): Iris e Theo
    leem o ConnoSr, nao editam nada.

.EXAMPLE
    .\preparar_e_rodar.ps1

.EXAMPLE
    .\preparar_e_rodar.ps1 -Rodadas 2 -Saida resultado-2.json

.EXAMPLE
    # So preparar o ambiente, sem gastar API:
    .\preparar_e_rodar.ps1 -SoPreparar
#>

[CmdletBinding()]
param(
    [string]$Repo = "..\connosr",
    [int]$Rodadas = 1,
    [string]$Saida = "resultado.json",
    [string]$Foco = "fazer o feed parecer vivo no primeiro acesso",
    [switch]$SemPull,
    [switch]$SoPreparar
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Etapa($n, $texto) { Write-Host "`n[$n] $texto" -ForegroundColor Cyan }
function Ok($texto)        { Write-Host "    ok: $texto" -ForegroundColor Green }
function Aviso($texto)     { Write-Host "    aviso: $texto" -ForegroundColor Yellow }

# --- 1. Python -------------------------------------------------------------
Etapa 1 "Procurando Python 3.10+"
$pyCmd = "py"; $pyArgs = @("-3")
try { & py -3 --version | Out-Null } catch { $pyCmd = "python"; $pyArgs = @() }
$versao = (& $pyCmd @pyArgs --version) -join ""
Ok $versao

# --- 2. Codigo atualizado --------------------------------------------------
Etapa 2 "Atualizando o repositorio"
if ($SemPull) {
    Aviso "-SemPull: pulando o git pull"
} else {
    git pull origin main
    Ok "em dia com origin/main"
}

# --- 3. A chave ------------------------------------------------------------
# O .env esta no .gitignore: fica so nesta maquina, nunca vai para o GitHub.
Etapa 3 "Conferindo a ANTHROPIC_API_KEY no .env"
$envPath = Join-Path $PSScriptRoot ".env"
$temChave = $false
if (Test-Path $envPath) {
    $temChave = @(Get-Content $envPath | Where-Object { $_ -match '^\s*ANTHROPIC_API_KEY\s*=\s*\S' }).Count -gt 0
}
if ($temChave) {
    Ok ".env ja tem ANTHROPIC_API_KEY"
} else {
    Write-Host "    .env sem a chave. Cole a chave da Anthropic (comeca com sk-ant-)."
    $chave = Read-Host "    ANTHROPIC_API_KEY"
    if ([string]::IsNullOrWhiteSpace($chave)) { throw "Nenhuma chave informada." }
    Add-Content -Path $envPath -Value "ANTHROPIC_API_KEY=$($chave.Trim())"
    Ok "chave gravada em .env"
}

# --- 4. Ambiente virtual ---------------------------------------------------
Etapa 4 "Preparando o .venv"
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    & $pyCmd @pyArgs -m venv .venv
    Ok ".venv criado"
} else {
    Ok ".venv ja existe"
}
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -r requirements.txt --quiet
Ok "dependencias instaladas"

# --- 5. Repositorio alvo ---------------------------------------------------
Etapa 5 "Garantindo o clone do ConnoSr em $Repo"
if (Test-Path $Repo) {
    Ok "ja clonado"
} else {
    git clone --depth 1 https://github.com/Matheus-Cahu/ConnoSr.git $Repo
    Ok "clonado"
}

# --- 6. A chave chega mesmo ao processo? -----------------------------------
# Este e o teste que separa "chave escrita no arquivo" de "chave carregada pelo
# python-dotenv". Imprime tamanho e prefixo, nunca o valor.
Etapa 6 "Verificando que o python enxerga a chave"
& $venvPy -c 'from dotenv import load_dotenv; import os, sys; load_dotenv(); k = os.getenv("ANTHROPIC_API_KEY") or ""; print("    tamanho: %d | prefixo sk-ant: %s" % (len(k), k.startswith("sk-ant"))); sys.exit(0 if k else 1)'
if ($LASTEXITCODE -ne 0) { throw "python-dotenv nao carregou a ANTHROPIC_API_KEY do .env." }
Ok "chave visivel para o processo"

if ($SoPreparar) {
    Write-Host "`n-SoPreparar: ambiente pronto, rodada nao disparada." -ForegroundColor Cyan
    Write-Host "Para rodar:  .\preparar_e_rodar.ps1"
    exit 0
}

# --- 7. A rodada -----------------------------------------------------------
# Telemetria do crewai so adiciona timeouts; nao muda o resultado.
$env:CREWAI_TELEMETRY_OPT_OUT = "true"
Etapa 7 "Rodando a equipe (modo proposta, $Rodadas rodada(s))"
& $venvPy rodar_e_capturar.py $Foco --repo $Repo --rodadas $Rodadas --saida $Saida
if ($LASTEXITCODE -ne 0) { throw "A rodada terminou com erro (codigo $LASTEXITCODE)." }

Write-Host "`nPronto. Resultado em: $Saida" -ForegroundColor Green
