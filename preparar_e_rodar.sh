#!/usr/bin/env bash
# Prepara o ambiente e roda uma rodada real da equipe, do zero, no Linux/macOS.
#
# Equivalente do preparar_e_rodar.ps1. Faz na ordem: atualiza o repo, garante a
# ANTHROPIC_API_KEY no .env, cria o .venv e instala as dependencias, clona o
# ConnoSr, confirma que o python-dotenv le a chave, e so entao dispara a rodada.
#
# Cada etapa e idempotente: rodar de novo nao refaz o que ja esta pronto.
#
# Uso:
#   ./preparar_e_rodar.sh
#   ./preparar_e_rodar.sh --rodadas 2 --saida resultado-2.json
#   ./preparar_e_rodar.sh --so-preparar     # prepara sem gastar API

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

REPO="../connosr"
RODADAS=1
SAIDA="resultado.json"
FOCO="fazer o feed parecer vivo no primeiro acesso"
SEM_PULL=0
SO_PREPARAR=0

while [ $# -gt 0 ]; do
    case "$1" in
        --repo)        REPO="$2"; shift 2 ;;
        --rodadas)     RODADAS="$2"; shift 2 ;;
        --saida)       SAIDA="$2"; shift 2 ;;
        --foco)        FOCO="$2"; shift 2 ;;
        --sem-pull)    SEM_PULL=1; shift ;;
        --so-preparar) SO_PREPARAR=1; shift ;;
        -h|--help)     sed -n '2,14p' "$0"; exit 0 ;;
        *) echo "opcao desconhecida: $1" >&2; exit 2 ;;
    esac
done

if [ -t 1 ]; then
    AZUL=$'\033[36m'; VERDE=$'\033[32m'; AMARELO=$'\033[33m'; FIM=$'\033[0m'
else
    AZUL=""; VERDE=""; AMARELO=""; FIM=""
fi
etapa() { printf '\n%s[%s] %s%s\n' "$AZUL" "$1" "$2" "$FIM"; }
ok()    { printf '    %sok: %s%s\n' "$VERDE" "$1" "$FIM"; }
aviso() { printf '    %saviso: %s%s\n' "$AMARELO" "$1" "$FIM"; }
erro()  { printf '\nerro: %s\n' "$1" >&2; exit 1; }

# --- 1. Python -------------------------------------------------------------
etapa 1 "Procurando Python 3.10+"
PY=""
for cand in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1 &&
       "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        PY="$cand"; break
    fi
done
[ -n "$PY" ] || erro "nenhum Python 3.10+ encontrado. Instale python3 e o pacote python3-venv."
ok "$("$PY" --version) em $(command -v "$PY")"

# --- 2. Codigo atualizado --------------------------------------------------
etapa 2 "Atualizando o repositorio"
if [ "$SEM_PULL" = 1 ]; then
    aviso "--sem-pull: pulando o git pull"
else
    branch="$(git rev-parse --abbrev-ref HEAD)"
    if git pull; then ok "em dia com origin/$branch"
    else aviso "git pull falhou; seguindo com o codigo local"; fi
fi
# Carimba a versao que vai rodar: uma saida colada fora de contexto nao diz,
# sozinha, se ja inclui o ultimo conserto.
ok "commit: $(git log --oneline -1)"

# --- 3. A chave ------------------------------------------------------------
# O .env esta no .gitignore: fica so nesta maquina, nunca vai para o GitHub.
etapa 3 "Conferindo a ANTHROPIC_API_KEY no .env"
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    ok "ANTHROPIC_API_KEY ja esta no ambiente"
elif [ -f .env ] && grep -qE '^[[:space:]]*ANTHROPIC_API_KEY[[:space:]]*=[[:space:]]*\S' .env; then
    ok ".env ja tem ANTHROPIC_API_KEY"
elif [ -t 0 ]; then
    echo "    .env sem a chave. Cole a chave da Anthropic (comeca com sk-ant-)."
    printf '    ANTHROPIC_API_KEY: '
    read -rs chave; echo

    # Terminais com bracketed paste mal resolvido entregam \e[200~ e \e[201~
    # junto com o texto colado. `read -rs` nao passa por readline, entao recebe
    # os bytes crus e eles acabam gravados dentro da chave -- que passa em
    # qualquer teste de "nao esta vazia" e so falha na API, com um 401.
    esc=$'\033'
    chave="${chave//${esc}\[200~/}"
    chave="${chave//${esc}\[201~/}"
    chave="${chave//[$'\r\n\t ']/}"
    chave="${chave%\~}"

    [ -n "$chave" ] || erro "nenhuma chave informada."

    # A leitura e silenciosa, entao quem cola nao ve nada acontecer e tende a
    # colar de novo -- as copias grudam em um valor so. Barramos isso e damos
    # o retorno visual que faltava.
    copias="$(printf '%s' "$chave" | grep -o 'sk-ant-' | wc -l)"
    if [ "$copias" -gt 1 ]; then
        erro "a chave foi colada $copias vezes e as copias grudaram.
A leitura nao mostra nada na tela de proposito -- cole UMA vez e de Enter."
    fi

    case "$chave" in
        sk-ant-*) ;;
        *) erro "a chave nao comeca com 'sk-ant-'. A colagem provavelmente veio
truncada ou com lixo do terminal. Tente de novo, ou grave o .env a mao:
  printf 'ANTHROPIC_API_KEY=sk-ant-...\\n' > .env" ;;
    esac

    printf 'ANTHROPIC_API_KEY=%s\n' "$chave" >> .env
    chmod 600 .env
    # Confirmacao visivel sem expor o valor: tamanho e as ultimas 4 letras.
    ok "chave gravada em .env: ${#chave} caracteres, terminando em ...${chave: -4} (permissao 600)"
else
    erro "sem ANTHROPIC_API_KEY e sem terminal para perguntar.
Crie o .env manualmente:  echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env"
fi

# --- 4. Ambiente virtual ---------------------------------------------------
etapa 4 "Preparando o .venv"
if [ ! -x .venv/bin/python ]; then
    "$PY" -m venv .venv || erro "falha ao criar o .venv. No Debian/Ubuntu: apt install python3-venv"
    ok ".venv criado"
else
    ok ".venv ja existe"
fi
VENV_PY=".venv/bin/python"

# Um .venv pode existir sem pip. No Debian/Ubuntu o ensurepip vem no pacote
# python3-venv; sem ele o venv nasce vazio e a primeira chamada ao pip morre
# com "No module named pip". Um .venv quebrado de uma tentativa anterior da no
# mesmo. Tratamos os dois casos aqui, do reparo barato ao caro.
if ! "$VENV_PY" -m pip --version >/dev/null 2>&1; then
    aviso ".venv sem pip; tentando reparar com ensurepip"
    if "$VENV_PY" -m ensurepip --upgrade >/dev/null 2>&1; then
        ok "pip instalado pelo ensurepip"
    else
        aviso "ensurepip indisponivel; recriando o .venv do zero"
        rm -rf .venv
        "$PY" -m venv .venv >/dev/null 2>&1 || true
        if ! "$VENV_PY" -m pip --version >/dev/null 2>&1; then
            versao="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
            erro "o .venv nao tem pip e o ensurepip nao esta disponivel.
Instale o pacote de venv da sua distro e rode de novo:
  Debian/Ubuntu:  sudo apt install python${versao}-venv
  Fedora/RHEL:    sudo dnf install python3-devel
  Arch:           ja vem junto do pacote python"
        fi
        ok ".venv recriado com pip"
    fi
fi

"$VENV_PY" -m pip install --upgrade pip --quiet
"$VENV_PY" -m pip install -r requirements.txt --quiet
ok "dependencias instaladas"

# --- 5. Repositorio alvo ---------------------------------------------------
etapa 5 "Garantindo o clone do ConnoSr em $REPO"
if [ -d "$REPO" ]; then
    ok "ja clonado"
else
    git clone --depth 1 https://github.com/Matheus-Cahu/ConnoSr.git "$REPO"
    ok "clonado"
fi

# --- 6. A chave chega mesmo ao processo? -----------------------------------
etapa 6 "Verificando que o python enxerga a chave"
"$VENV_PY" verificar_chave.py || erro "python-dotenv nao carregou a ANTHROPIC_API_KEY do .env."
ok "chave visivel para o processo"

if [ "$SO_PREPARAR" = 1 ]; then
    printf '\n%s--so-preparar: ambiente pronto, rodada nao disparada.%s\n' "$AZUL" "$FIM"
    echo "Para rodar:  ./preparar_e_rodar.sh"
    exit 0
fi

# --- 7. A rodada -----------------------------------------------------------
# Telemetria do crewai so adiciona timeouts; nao muda o resultado.
export CREWAI_TELEMETRY_OPT_OUT=true
etapa 7 "Rodando a equipe (modo proposta, $RODADAS rodada(s))"
"$VENV_PY" rodar_e_capturar.py "$FOCO" --repo "$REPO" --rodadas "$RODADAS" --saida "$SAIDA" \
    || erro "a rodada terminou com erro."

printf '\n%sPronto. Resultado em: %s%s\n' "$VERDE" "$SAIDA" "$FIM"
