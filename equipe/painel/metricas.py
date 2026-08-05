"""Coleta de metricas por agente, a partir do barramento de eventos do CrewAI.

Todo evento do CrewAI carrega `agent_role`, `task_name` e `timestamp`. Como o
`role` de cada agente comeca pelo nome proprio (ver equipe/agentes.py), da para
montar um painel por pessoa sem instrumentar nada dentro dos agentes.

Os handlers do barramento rodam em thread pool, entao todo acesso ao estado
passa por lock.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from crewai.events import BaseEventListener, crewai_event_bus
from crewai.events.types.agent_events import (
    AgentExecutionCompletedEvent,
    AgentExecutionErrorEvent,
    AgentExecutionStartedEvent,
)
from crewai.events.types.flow_events import (
    MethodExecutionFinishedEvent,
    MethodExecutionStartedEvent,
)
from crewai.events.types.llm_events import LLMCallCompletedEvent
from crewai.events.types.task_events import (
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
)
from crewai.events.types.tool_usage_events import (
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)

from equipe.agentes import NOMES, nome_do_agente

OCIOSO = "ocioso"
TRABALHANDO = "trabalhando"
CONCLUIDO = "concluido"
ERRO = "erro"


@dataclass
class MetricasDoAgente:
    """O que o painel mostra de cada agente."""

    nome: str
    papel: str = ""
    estado: str = OCIOSO
    tarefa_atual: str = ""
    ferramenta_atual: str = ""
    inicio_da_tarefa: float | None = None
    segundos_trabalhados: float = 0.0
    execucoes: int = 0
    erros: int = 0
    chamadas_llm: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    ferramentas_usadas: int = 0
    # placar de qualidade, alimentado pelo fluxo (nao pelo barramento)
    entregas: int = 0
    aprovacoes_de_primeira: int = 0
    devolucoes: int = 0
    atritos_encontrados: int = 0
    ultima_atividade: str = ""

    @property
    def tokens(self) -> int:
        return self.tokens_entrada + self.tokens_saida

    @property
    def taxa_de_aprovacao(self) -> float | None:
        if not self.entregas:
            return None
        return round(100.0 * self.aprovacoes_de_primeira / self.entregas, 1)

    def snapshot(self, agora: float) -> dict[str, Any]:
        decorrido = self.segundos_trabalhados
        if self.estado == TRABALHANDO and self.inicio_da_tarefa is not None:
            decorrido += agora - self.inicio_da_tarefa
        return {
            "nome": self.nome,
            "papel": self.papel,
            "estado": self.estado,
            "tarefaAtual": self.tarefa_atual,
            "ferramentaAtual": self.ferramenta_atual,
            "segundos": round(decorrido, 1),
            "execucoes": self.execucoes,
            "erros": self.erros,
            "chamadasLlm": self.chamadas_llm,
            "tokens": self.tokens,
            "tokensEntrada": self.tokens_entrada,
            "tokensSaida": self.tokens_saida,
            "ferramentasUsadas": self.ferramentas_usadas,
            "entregas": self.entregas,
            "aprovacoesDePrimeira": self.aprovacoes_de_primeira,
            "devolucoes": self.devolucoes,
            "atritosEncontrados": self.atritos_encontrados,
            "taxaDeAprovacao": self.taxa_de_aprovacao,
            "ultimaAtividade": self.ultima_atividade,
        }


class PainelDeMetricas(BaseEventListener):
    """Escuta o barramento e mantem o estado ao vivo da equipe.

    `ao_atualizar` e chamado a cada mudanca; o servidor usa isso para empurrar
    os dados para o navegador via SSE.
    """

    def __init__(self, ao_atualizar: Callable[[dict[str, Any]], None] | None = None) -> None:
        self._lock = threading.RLock()
        self._agentes: dict[str, MetricasDoAgente] = {
            nome: MetricasDoAgente(nome=nome) for nome in NOMES
        }
        self._etapa_atual = ""
        self._rodada = 0
        self._max_rodadas = 0
        self._linha_do_tempo: list[dict[str, Any]] = []
        self._inicio = time.time()
        self._ao_atualizar = ao_atualizar
        super().__init__()

    # --- registro no barramento --------------------------------------------

    def setup_listeners(self, bus) -> None:  # noqa: ANN001 - assinatura do CrewAI
        @bus.on(AgentExecutionStartedEvent)
        def _agente_comecou(source, event):  # noqa: ANN001, ARG001
            self._atualizar(
                event.agent_role,
                estado=TRABALHANDO,
                papel=event.agent_role,
                tarefa=getattr(event, "task_name", "") or "",
                marcar_inicio=True,
                atividade="comecou a trabalhar",
            )

        @bus.on(AgentExecutionCompletedEvent)
        def _agente_terminou(source, event):  # noqa: ANN001, ARG001
            self._atualizar(
                event.agent_role,
                estado=CONCLUIDO,
                fechar_inicio=True,
                incrementar={"execucoes": 1},
                limpar_ferramenta=True,
                atividade="entregou o resultado",
            )

        @bus.on(AgentExecutionErrorEvent)
        def _agente_falhou(source, event):  # noqa: ANN001, ARG001
            self._atualizar(
                event.agent_role,
                estado=ERRO,
                fechar_inicio=True,
                incrementar={"erros": 1},
                atividade=f"erro: {str(getattr(event, 'error', ''))[:120]}",
            )

        @bus.on(TaskStartedEvent)
        def _tarefa_comecou(source, event):  # noqa: ANN001, ARG001
            self._atualizar(
                event.agent_role,
                tarefa=getattr(event, "task_name", "") or "",
                atividade="iniciou tarefa",
            )

        @bus.on(TaskCompletedEvent)
        def _tarefa_terminou(source, event):  # noqa: ANN001, ARG001
            self._atualizar(event.agent_role, atividade="concluiu tarefa")

        @bus.on(TaskFailedEvent)
        def _tarefa_falhou(source, event):  # noqa: ANN001, ARG001
            self._atualizar(
                event.agent_role,
                estado=ERRO,
                incrementar={"erros": 1},
                atividade="tarefa falhou",
            )

        @bus.on(LLMCallCompletedEvent)
        def _llm(source, event):  # noqa: ANN001, ARG001
            entrada, saida = _extrair_tokens(getattr(event, "usage", None))
            self._atualizar(
                event.agent_role,
                incrementar={
                    "chamadas_llm": 1,
                    "tokens_entrada": entrada,
                    "tokens_saida": saida,
                },
            )

        @bus.on(ToolUsageStartedEvent)
        def _ferramenta_comecou(source, event):  # noqa: ANN001, ARG001
            self._atualizar(
                event.agent_role,
                ferramenta=getattr(event, "tool_name", "") or "",
                atividade=f"usando {getattr(event, 'tool_name', 'ferramenta')}",
            )

        @bus.on(ToolUsageFinishedEvent)
        def _ferramenta_terminou(source, event):  # noqa: ANN001, ARG001
            self._atualizar(
                event.agent_role,
                limpar_ferramenta=True,
                incrementar={"ferramentas_usadas": 1},
            )

        @bus.on(MethodExecutionStartedEvent)
        def _etapa_comecou(source, event):  # noqa: ANN001, ARG001
            with self._lock:
                self._etapa_atual = getattr(event, "method_name", "") or ""
                self._registrar_linha(f"etapa: {self._etapa_atual}")
            self._emitir()

        @bus.on(MethodExecutionFinishedEvent)
        def _etapa_terminou(source, event):  # noqa: ANN001, ARG001
            with self._lock:
                self._registrar_linha(
                    f"etapa concluida: {getattr(event, 'method_name', '') or ''}"
                )
            self._emitir()

    # --- alimentado pelo fluxo ---------------------------------------------

    def marcar_rodada(self, rodada: int, max_rodadas: int) -> None:
        with self._lock:
            self._rodada = rodada
            self._max_rodadas = max_rodadas
            self._registrar_linha(f"rodada {rodada} de {max_rodadas}")
        self._emitir()

    def registrar_entrega(self, nome: str, aprovada_de_primeira: bool) -> None:
        """Placar de qualidade: so o fluxo sabe se a Vera aprovou ou devolveu."""
        with self._lock:
            agente = self._agentes.get(nome)
            if agente is None:
                return
            agente.entregas += 1
            if aprovada_de_primeira:
                agente.aprovacoes_de_primeira += 1
            else:
                agente.devolucoes += 1
        self._emitir()

    def registrar_atritos(self, nome: str, quantidade: int) -> None:
        with self._lock:
            agente = self._agentes.get(nome)
            if agente is not None:
                agente.atritos_encontrados += quantidade
        self._emitir()

    def registrar_evento(self, texto: str) -> None:
        with self._lock:
            self._registrar_linha(texto)
        self._emitir()

    # --- estado -------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        agora = time.time()
        with self._lock:
            return {
                "etapa": self._etapa_atual,
                "rodada": self._rodada,
                "maxRodadas": self._max_rodadas,
                "decorrido": round(agora - self._inicio, 1),
                "agentes": [a.snapshot(agora) for a in self._agentes.values()],
                "linhaDoTempo": self._linha_do_tempo[-40:],
            }

    # --- internos -----------------------------------------------------------

    def _registrar_linha(self, texto: str) -> None:
        """Requer lock ja adquirido."""
        self._linha_do_tempo.append(
            {"em": round(time.time() - self._inicio, 1), "texto": texto}
        )

    def _atualizar(
        self,
        role: str | None,
        *,
        estado: str | None = None,
        papel: str | None = None,
        tarefa: str | None = None,
        ferramenta: str | None = None,
        atividade: str | None = None,
        marcar_inicio: bool = False,
        fechar_inicio: bool = False,
        limpar_ferramenta: bool = False,
        incrementar: dict[str, int] | None = None,
    ) -> None:
        if not role:
            return
        nome = nome_do_agente(role)
        with self._lock:
            agente = self._agentes.get(nome)
            if agente is None:
                # agente fora da equipe nomeada (ex: ferramenta de delegacao)
                agente = MetricasDoAgente(nome=nome, papel=role)
                self._agentes[nome] = agente
            if papel:
                agente.papel = papel
            if estado:
                agente.estado = estado
            if tarefa is not None:
                agente.tarefa_atual = tarefa
            if ferramenta is not None:
                agente.ferramenta_atual = ferramenta
            if limpar_ferramenta:
                agente.ferramenta_atual = ""
            if marcar_inicio and agente.inicio_da_tarefa is None:
                agente.inicio_da_tarefa = time.time()
            if fechar_inicio and agente.inicio_da_tarefa is not None:
                agente.segundos_trabalhados += time.time() - agente.inicio_da_tarefa
                agente.inicio_da_tarefa = None
            for campo, valor in (incrementar or {}).items():
                setattr(agente, campo, getattr(agente, campo) + valor)
            if atividade:
                agente.ultima_atividade = atividade
                self._registrar_linha(f"{nome}: {atividade}")
        self._emitir()

    def _emitir(self) -> None:
        if self._ao_atualizar is None:
            return
        try:
            self._ao_atualizar(self.snapshot())
        except Exception:  # painel nunca pode derrubar a rodada
            pass


def _extrair_tokens(usage: Any) -> tuple[int, int]:
    """Le tokens de entrada/saida do campo `usage`, que varia por provedor."""
    if usage is None:
        return 0, 0
    dados = usage if isinstance(usage, dict) else getattr(usage, "__dict__", {}) or {}

    def pega(*chaves: str) -> int:
        for chave in chaves:
            valor = dados.get(chave)
            if isinstance(valor, (int, float)):
                return int(valor)
        return 0

    entrada = pega("prompt_tokens", "input_tokens", "promptTokens")
    saida = pega("completion_tokens", "output_tokens", "completionTokens")
    return entrada, saida
