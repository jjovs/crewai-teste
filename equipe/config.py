"""Configuracao da equipe.

Tudo que depende do projeto alvo esta concentrado aqui. Quando o repositorio da
rede social for conectado, e este arquivo (ou as variaveis de ambiente
equivalentes) que passa a apontar para ele.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

MODELO_PADRAO = "anthropic/claude-sonnet-5"


@dataclass
class Config:
    """Parametros de uma rodada de trabalho da equipe."""

    # --- projeto alvo -------------------------------------------------------
    repo_alvo: Path | None = None
    """Raiz do repositorio da rede social. Sem isso, Iris e Theo trabalham em
    modo proposta (entregam especificacao em vez de editar arquivos)."""

    diretorios_de_ui: list[str] = field(default_factory=list)
    """Caminhos relativos, dentro do repo alvo, que Iris e Theo podem tocar.
    Funciona como cerca: nenhuma escrita acontece fora daqui."""

    url_do_app: str | None = None
    """URL do app rodando localmente, ex: http://localhost:3000. Sem isso, Lila
    e Rui rodam em modo simulacao, sem tocar no app."""

    # --- comportamento da rodada -------------------------------------------
    foco: str = "melhorar a experiencia social do feed de avaliacoes"
    max_rodadas: int = 3
    """Quantas vezes a Vera pode devolver o trabalho antes de encerrar."""

    modelo: str = field(default_factory=lambda: os.getenv("CREWAI_MODELO", MODELO_PADRAO))
    verbose: bool = True

    # --- painel -------------------------------------------------------------
    porta_do_painel: int = 8777
    abrir_painel: bool = True

    @property
    def modo_codigo(self) -> bool:
        """True quando Iris e Theo podem escrever codigo de verdade."""
        return self.repo_alvo is not None and self.repo_alvo.is_dir()

    @property
    def modo_navegador(self) -> bool:
        """True quando Lila e Rui podem interagir com o app rodando."""
        return bool(self.url_do_app)

    def validar(self) -> list[str]:
        """Devolve avisos sobre o que esta faltando para a rodada ser completa."""
        avisos: list[str] = []
        if not os.getenv("ANTHROPIC_API_KEY"):
            avisos.append(
                "ANTHROPIC_API_KEY nao definida - a rodada nao vai conseguir rodar."
            )
        if self.repo_alvo is not None and not self.repo_alvo.is_dir():
            avisos.append(f"repo_alvo nao e um diretorio: {self.repo_alvo}")
        if not self.modo_codigo:
            avisos.append(
                "Sem repo alvo: Iris e Theo entregam especificacao, nao codigo."
            )
        if self.modo_codigo and not self.diretorios_de_ui:
            avisos.append(
                "diretorios_de_ui vazio: por seguranca, nenhuma escrita sera permitida."
            )
        if not self.modo_navegador:
            avisos.append(
                "Sem url_do_app: Lila e Rui simulam a sessao em vez de usar o app real."
            )
        return avisos
