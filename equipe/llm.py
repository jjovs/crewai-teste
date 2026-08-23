"""Construcao do LLM, com um detalhe de compatibilidade.

Os modelos da familia Claude 5 nao aceitam mais `temperature`. A API responde:

    400 invalid_request_error: `temperature` is deprecated for this model.

O provider Anthropic do CrewAI so inclui o parametro quando ele nao e None
(`llms/providers/anthropic/completion.py`), entao a correcao e simplesmente nao
passar. Nos modelos que ainda aceitam, a temperatura continua valendo -- e ela
que separa o agente criativo do preciso.
"""

from __future__ import annotations

import os
import re

from crewai import LLM

# O nome chega como "anthropic/claude-sonnet-5" ou "claude-haiku-4-5". O que
# decide e o numero da familia logo apos o nome do modelo.
_FAMILIA = re.compile(r"claude-(?:sonnet|opus|haiku|fable)-(\d+)")

PRIMEIRA_FAMILIA_SEM_TEMPERATURA = 5

# O provider Anthropic do CrewAI usa max_tokens=4096 por padrao. Isso basta para
# Caio e Vera, mas nao para Iris e Theo: eles gastam parte do orcamento nas
# rodadas de ferramenta e ainda precisam escrever a entrega inteira. Estourando
# o limite, a resposta volta truncada e o CrewAI a le como vazia --
# "Invalid response from LLM call - None or empty".
#
# 16000 e o padrao recomendado para requisicoes sem streaming (o CrewAI usa
# messages.create direto). O teto do modelo e bem maior, mas valores altos sem
# streaming arriscam estourar o timeout HTTP do SDK.
MAX_TOKENS_PADRAO = 16_000


def aceita_temperatura(modelo: str) -> bool:
    """False quando a API rejeita `temperature` para este modelo.

    A deteccao e pelo nome, entao um modelo desconhecido mantem o comportamento
    antigo em vez de perder a temperatura em silencio. `CREWAI_TEMPERATURA`
    forca o resultado: "0" nunca envia, "1" sempre envia.
    """
    forcado = os.getenv("CREWAI_TEMPERATURA")
    if forcado in {"0", "1"}:
        return forcado == "1"
    achado = _FAMILIA.search(modelo)
    if achado is None:
        return True
    return int(achado.group(1)) < PRIMEIRA_FAMILIA_SEM_TEMPERATURA


def max_tokens() -> int:
    """Teto de saida por resposta. `CREWAI_MAX_TOKENS` sobrescreve."""
    bruto = os.getenv("CREWAI_MAX_TOKENS", "")
    if bruto.isdigit() and int(bruto) > 0:
        return int(bruto)
    return MAX_TOKENS_PADRAO


def criar_llm(modelo: str, temperatura: float) -> LLM:
    """LLM do CrewAI, com a temperatura omitida quando o modelo nao a aceita."""
    extras: dict[str, object] = {"max_tokens": max_tokens()}
    if aceita_temperatura(modelo):
        extras["temperature"] = temperatura
    return LLM(model=modelo, **extras)
