#!/bin/bash
# Preparo da sessao para o time de agentes.
#
# O container do Claude Code na web e novo a cada sessao: o clone do ConnoSr e
# o .venv se perdem. Este hook refaz os dois, para a rodada poder comecar sem
# quatro minutos de preparo manual.
#
# Roda so no ambiente remoto; na maquina local nao mexe em nada.
#
# Modo assincrono: a sessao abre na hora e o preparo continua ao fundo. Em
# troca existe uma janela em que o .venv ainda nao esta pronto -- veja o
# marcador de conclusao no fim do arquivo.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Precisa ser a primeira linha do stdout: e o que solta a sessao.
echo '{"async": true, "asyncTimeout": 900000}'

PROJETO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
CONNOSR="${CONNOSR_REPO:-/home/user/connosr}"
VENV="$PROJETO/.venv"
PRONTO="$VENV/.preparo-ok"

# Derruba o marcador antes de qualquer coisa: enquanto ele nao voltar, o
# preparo esta em andamento ou falhou.
rm -f "$PRONTO"

# Estado da chave primeiro, porque e a informacao que decide se vale a pena
# rodar. Config.validar() apenas avisa quando ela falta, entao uma rodada sem
# chave so quebraria la na frente, na primeira chamada da API.
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "[preparo] ANTHROPIC_API_KEY presente no ambiente - a rodada real pode ser executada."
elif [ -f "$PROJETO/.env" ] && grep -q '^[[:space:]]*ANTHROPIC_API_KEY=..' "$PROJETO/.env"; then
  echo "[preparo] ANTHROPIC_API_KEY vem do .env - a rodada real pode ser executada."
else
  echo "[preparo] ATENCAO: ANTHROPIC_API_KEY ausente do ambiente e do .env."
  echo "[preparo] Config.validar() apenas avisa em vez de abortar, entao a rodada"
  echo "[preparo] so quebraria na primeira chamada da API. Avise o usuario e pare."
  echo "[preparo] Saida rapida sem depender do environment: criar $PROJETO/.env com"
  echo "[preparo] ANTHROPIC_API_KEY=... (o .gitignore ja cobre esse arquivo)."
  # Diagnostico de injecao, so nomes, nunca valores. Se o usuario definir um
  # sentinela no environment e nem ele aparecer aqui, o problema nao e o nome
  # da variavel: nada esta sendo injetado.
  visiveis="$(env | grep -o '^[A-Za-z_][A-Za-z_0-9]*' | grep -E 'ANTHROPIC|TESTE_INJECAO' | sort | tr '\n' ' ')"
  echo "[preparo] variaveis visiveis com esse nome: ${visiveis:-nenhuma}"
fi

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

# 3. Caminho do alvo para o resto da sessao. Em modo assincrono a sessao pode
#    ja ter comecado quando isto e escrito, entao trate como conveniencia e
#    nao como garantia: o padrao /home/user/connosr continua valendo.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export CONNOSR_REPO=\"$CONNOSR\"" >> "$CLAUDE_ENV_FILE"
fi

# 4. Marcador de conclusao. Assincrono significa que a sessao abre antes daqui,
#    entao quem for rodar a equipe espera por este arquivo:
#      until [ -f .venv/.preparo-ok ]; do sleep 5; done
date -u +%Y-%m-%dT%H:%M:%SZ > "$PRONTO"

echo "[preparo] pronto. Interpretador: $VENV/bin/python"
