#!/bin/bash
# Preparo da sessao para o time de agentes.
#
# O container do Claude Code na web e novo a cada sessao: o clone do ConnoSr e
# o .venv se perdem. Este hook refaz os dois, para a rodada poder comecar sem
# quatro minutos de preparo manual.
#
# Roda so no ambiente remoto; na maquina local nao mexe em nada.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJETO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
CONNOSR="${CONNOSR_REPO:-/home/user/connosr}"
VENV="$PROJETO/.venv"

# 1. Clone do alvo. Iris e Theo leem esse codigo para propor com arquivo e
#    trecho exatos; sem ele a rodada degrada para proposta no escuro.
if [ -d "$CONNOSR/.git" ]; then
  echo "[preparo] ConnoSr ja clonado em $CONNOSR"
else
  echo "[preparo] clonando ConnoSr em $CONNOSR"
  rm -rf "$CONNOSR"
  git clone --depth 1 https://github.com/Matheus-Cahu/ConnoSr.git "$CONNOSR"
fi

# 2. Venv proprio. O pip do sistema quebra num PyYAML instalado pelo Debian,
#    que ele nao consegue desinstalar para satisfazer o crewai.
if [ -x "$VENV/bin/python" ]; then
  echo "[preparo] venv ja existe em $VENV"
else
  echo "[preparo] criando venv em $VENV"
  python3 -m venv "$VENV"
fi

echo "[preparo] instalando dependencias (leva alguns minutos na primeira vez)"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$PROJETO/requirements.txt"

# 3. Deixa o caminho do alvo pronto para o resto da sessao.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export CONNOSR_REPO=\"$CONNOSR\"" >> "$CLAUDE_ENV_FILE"
fi

# 4. Estado da chave. Config.validar() apenas avisa quando ela falta, entao uma
#    rodada sem chave so quebra la na frente, na primeira chamada da API.
#    Dizer isso aqui, no inicio, evita gastar o preparo inteiro a toa.
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "[preparo] ANTHROPIC_API_KEY presente - a rodada real pode ser executada."
else
  echo "[preparo] ATENCAO: ANTHROPIC_API_KEY ausente do ambiente."
  echo "[preparo] Nao execute rodar_e_capturar.py: ele nao carrega .env (so main.py"
  echo "[preparo] e rodar_equipe.py chamam load_dotenv), e Config.validar() apenas"
  echo "[preparo] avisa em vez de abortar. Avise o usuario e pare."
fi

echo "[preparo] pronto. Interpretador: $VENV/bin/python"
