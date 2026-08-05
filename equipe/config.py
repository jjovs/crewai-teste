"""Configuracao da equipe.

Tudo que depende do projeto alvo esta concentrado aqui. Quando o repositorio da
rede social for conectado, e este arquivo (ou as variaveis de ambiente
equivalentes) que passa a apontar para ele.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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

    diretorios_de_iris: list[str] = field(default_factory=list)
    diretorios_de_theo: list[str] = field(default_factory=list)
    """Cercas por designer. Quando preenchidos, a separacao de escopo deixa de
    ser so instrucao no prompt e vira regra tecnica: Iris nao alcanca os
    arquivos do Theo e vice-versa. Vazios, os dois usam `diretorios_de_ui`."""

    url_do_app: str | None = None
    """URL do app rodando localmente, ex: http://localhost:5173. Sem isso, Lila
    e Rui rodam em modo simulacao, sem tocar no app."""

    credenciais: dict[str, Any] = field(default_factory=dict)
    """Login por persona: {"Lila": Credencial(...), "Rui": Credencial(...)}.
    Vazio usa os usuarios de seed do ConnoSr."""

    rota_de_login: Any = None
    """Como logar no app (RotaDeLogin). None usa o preset do ConnoSr."""

    headless: bool = True
    """False abre o navegador na tela - util para assistir as personas usando o app."""

    # --- comportamento da rodada -------------------------------------------
    permitir_escrita: bool = True
    """False = modo proposta: Iris e Theo leem o repositorio mas nao editam nada.
    A ferramenta de escrita nao e sequer construida, entao nao ha o que dar errado."""

    foco: str = "melhorar a experiencia social do feed de avaliacoes"
    max_rodadas: int = 3
    """Quantas vezes a Vera pode devolver o trabalho antes de encerrar."""

    modelo: str = field(default_factory=lambda: os.getenv("CREWAI_MODELO", MODELO_PADRAO))
    verbose: bool = True

    # --- painel -------------------------------------------------------------
    porta_do_painel: int = 8777
    abrir_painel: bool = True

    @property
    def pode_ler_codigo(self) -> bool:
        """True quando o repo alvo esta acessivel para leitura."""
        return self.repo_alvo is not None and self.repo_alvo.is_dir()

    @property
    def modo_codigo(self) -> bool:
        """True quando Iris e Theo podem ESCREVER codigo.

        Em modo proposta eles continuam lendo o repositorio - proposta ancorada
        no codigo real e muito melhor que proposta baseada em suposicao - mas a
        ferramenta de escrita nem chega a ser criada.
        """
        return self.pode_ler_codigo and self.permitir_escrita

    def cerca_de(self, nome: str) -> list[str]:
        """Diretorios que um designer pode tocar, com fallback para a cerca comum."""
        especifica = {
            "Iris": self.diretorios_de_iris,
            "Theo": self.diretorios_de_theo,
        }.get(nome, [])
        return especifica or self.diretorios_de_ui

    @property
    def modo_navegador(self) -> bool:
        """True quando Lila e Rui podem interagir com o app rodando."""
        return bool(self.url_do_app)

    @classmethod
    def para_connosr(cls, repo: Path, **kw: Any) -> "Config":
        """Preset do projeto ConnoSr (monorepo pnpm: web em Vite, API em Fastify).

        A divisao de cercas segue como o codigo esta organizado hoje: os estilos
        sao objetos inline dentro dos componentes, entao nao da para separar
        'estrutura' de 'visual' por arquivo. Separamos por pasta:

            Theo -> componentes reutilizaveis + design tokens
            Iris -> paginas e layouts (fluxo, navegacao, estados de tela)
        """
        return cls(
            repo_alvo=repo,
            diretorios_de_theo=["apps/web/src/components", "packages/ui/src"],
            diretorios_de_iris=["apps/web/src/pages", "apps/web/src/layouts"],
            url_do_app=kw.pop("url_do_app", "http://localhost:5173"),
            **kw,
        )

    def validar(self) -> list[str]:
        """Devolve avisos sobre o que esta faltando para a rodada ser completa."""
        avisos: list[str] = []
        if not os.getenv("ANTHROPIC_API_KEY"):
            avisos.append(
                "ANTHROPIC_API_KEY nao definida - a rodada nao vai conseguir rodar."
            )
        if self.repo_alvo is not None and not self.repo_alvo.is_dir():
            avisos.append(f"repo_alvo nao e um diretorio: {self.repo_alvo}")
        if not self.pode_ler_codigo:
            avisos.append(
                "Sem repo alvo: Iris e Theo propoem no escuro, sem ver o codigo atual."
            )
        if self.modo_codigo:
            sem_cerca = [n for n in ("Iris", "Theo") if not self.cerca_de(n)]
            if sem_cerca:
                avisos.append(
                    f"sem diretorio autorizado para {', '.join(sem_cerca)}: "
                    "por seguranca, nenhuma escrita sera permitida."
                )
        if not self.modo_navegador:
            avisos.append(
                "Sem url_do_app: Lila e Rui simulam a sessao em vez de usar o app real."
            )
        return avisos
