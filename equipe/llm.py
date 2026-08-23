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


def criar_llm(modelo: str, temperatura: float) -> LLM:
    """LLM do CrewAI, com a temperatura omitida quando o modelo nao a aceita."""
    if aceita_temperatura(modelo):
        return LLM(model=modelo, temperature=temperatura)
    return LLM(model=modelo)
