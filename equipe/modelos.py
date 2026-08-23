"""Contratos de dados entre os agentes.

Cada etapa entrega um objeto Pydantic, nao texto livre. Isso e o que permite ao
painel medir desempenho de verdade: da para contar criticas por gravidade,
atritos por severidade e aprovacoes de primeira porque tudo chega tipado.

Regra sobre listas: a lista que E a entrega de uma etapa (ideias, itens da
pauta, mudancas, interacoes) e obrigatoria -- sem ela a etapa nao aconteceu. As
listas de apoio (pendencias, adiadas, correcoes, atritos...) tem default vazio,
porque vazio e uma resposta legitima e porque um campo omitido nao pode derrubar
uma rodada inteira de varios minutos. `ParecerDaVera.correcoes` e o caso obvio:
a propria descricao diz "vazio quando aprovado".
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

Gravidade = Literal["bloqueante", "alta", "media", "baixa"]
Referencia = Literal["BeReal", "Instagram", "Letterboxd", "outro"]


# --- Caio: cacador de ideias -----------------------------------------------


class Ideia(BaseModel):
    titulo: str = Field(description="Nome curto da ideia")
    referencia: Referencia = Field(description="De qual app veio o padrao")
    o_que_e: str = Field(description="O padrao observado no app de referencia, em 1-2 frases")
    por_que_aqui: str = Field(
        description="Por que isso faz sentido numa rede de avaliacao de experiencias"
    )
    aplicacao: str = Field(description="Como ficaria concretamente neste produto")
    impacto_esperado: Gravidade = Field(description="Peso da ideia para a experiencia social")
    esforco: Literal["baixo", "medio", "alto"]
    risco: str = Field(description="O que pode dar errado ou irritar o usuario")


class CacaDeIdeias(BaseModel):
    ideias: list[Ideia] = Field(description="Entre 6 e 10 ideias, cobrindo as tres referencias")
    padrao_dominante: str = Field(
        description="O fio condutor que conecta as melhores ideias desta leva"
    )
    o_que_nao_copiar: list[str] = Field(
        default_factory=list,
        description="Padroes das referencias que seriam ruins aqui, e por que"
    )


# --- Vera: pauta da rodada --------------------------------------------------


class ItemDaPauta(BaseModel):
    ideia: str = Field(description="Titulo da ideia aprovada")
    dono: Literal["Iris", "Theo"] = Field(description="Quem executa: Iris (estrutura) ou Theo (visual)")
    entregavel: str = Field(description="O que precisa existir ao fim da rodada")
    criterio_de_aceite: str = Field(description="Como a Vera vai verificar objetivamente")


class PautaDaRodada(BaseModel):
    tema: str = Field(description="O foco desta rodada, em uma frase")
    itens: list[ItemDaPauta] = Field(description="Entre 2 e 5 itens, distribuidos entre Iris e Theo")
    adiadas: list[str] = Field(default_factory=list, description="Ideias boas que ficam para a proxima rodada, com o motivo")
    recusadas: list[str] = Field(default_factory=list, description="Ideias descartadas, com o motivo")


# --- Iris e Theo: entrega de design ----------------------------------------


class MudancaProposta(BaseModel):
    alvo: str = Field(description="Tela, componente ou arquivo afetado")
    mudanca: str = Field(description="O que muda, de forma especifica")
    justificativa: str = Field(description="Qual item da pauta isso atende e por que assim")
    antes_depois: str = Field(description="Como era e como fica, do ponto de vista de quem usa")


class EntregaDeDesign(BaseModel):
    autor: Literal["Iris", "Theo"]
    escopo: str = Field(description="O recorte que este agente assumiu nesta rodada")
    mudancas: list[MudancaProposta]
    arquivos_tocados: list[str] = Field(
        default_factory=list,
        description="Caminhos efetivamente editados; vazio quando em modo proposta"
    )
    decisoes_de_design: list[str] = Field(default_factory=list, description="Escolhas feitas e alternativas descartadas")
    pendencias: list[str] = Field(default_factory=list, description="O que ficou por fazer e por que")


# --- Lila e Rui: sessao simulada -------------------------------------------


class Interacao(BaseModel):
    autor: Literal["Lila", "Rui"]
    acao: str = Field(description="O que a persona fez, ex: 'publicou avaliacao de um restaurante'")
    tela: str = Field(description="Onde isso aconteceu")
    reacao: str = Field(description="O que a persona pensou ou sentiu ao fazer isso")


class Atrito(BaseModel):
    quem: Literal["Lila", "Rui", "ambos"]
    onde: str = Field(description="Tela ou fluxo onde o atrito apareceu")
    problema: str = Field(description="O que travou, confundiu ou desmotivou")
    gravidade: Gravidade
    hipotese_de_causa: str = Field(description="Qual decisao de design provavelmente causou isso")


class RelatorioDeSessao(BaseModel):
    modo: Literal["app_real", "simulacao"] = Field(
        description="Se as personas usaram o app rodando ou simularam a sessao"
    )
    interacoes: list[Interacao] = Field(description="A sessao em ordem cronologica")
    atritos: list[Atrito] = Field(default_factory=list, description="Do mais grave para o menos grave")
    momentos_bons: list[str] = Field(default_factory=list, description="O que funcionou e deve ser preservado")
    veredito_das_personas: str = Field(
        description="As duas personas voltariam ao app amanha? Por que?"
    )


# --- Vera: parecer final ----------------------------------------------------


class Correcao(BaseModel):
    para: Literal["Iris", "Theo"]
    o_que: str = Field(description="A correcao, de forma acionavel")
    gravidade: Gravidade
    origem: str = Field(description="De onde veio: criterio de aceite, atrito da sessao, ou analise propria")


class ParecerDaVera(BaseModel):
    veredito: Literal["aprovado", "refazer"]
    itens_atendidos: list[str] = Field(default_factory=list, description="Itens da pauta cujo criterio de aceite foi cumprido")
    itens_nao_atendidos: list[str] = Field(default_factory=list, description="Itens que falharam, com o que faltou")
    correcoes: list[Correcao] = Field(default_factory=list, description="Vazio quando aprovado")
    nota_da_rodada: int = Field(ge=0, le=10, description="Qualidade geral do trabalho desta rodada")
    justificativa: str


# --- Estado do fluxo --------------------------------------------------------


class EstadoDaRodada(BaseModel):
    """Estado compartilhado entre as etapas do Flow.

    O campo `id` e exigido pelo CrewAI para todo estado estruturado de Flow.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    foco: str = ""
    rodada: int = 0
    max_rodadas: int = 3
    modo_codigo: bool = False
    modo_navegador: bool = False

    caca: CacaDeIdeias | None = None
    pauta: PautaDaRodada | None = None
    entregas: list[EntregaDeDesign] = Field(default_factory=list)
    sessao: RelatorioDeSessao | None = None
    parecer: ParecerDaVera | None = None

    correcoes_pendentes: list[Correcao] = Field(default_factory=list)
    historico: list[str] = Field(default_factory=list)
    encerrada_por: str = ""

    def registrar(self, evento: str) -> None:
        self.historico.append(f"[rodada {self.rodada}] {evento}")
