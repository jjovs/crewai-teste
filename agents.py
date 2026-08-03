"""O time de agentes.

Sete papeis, cada um com uma responsabilidade unica e um criterio claro de
"trabalho bem feito". A ideia e que nenhum agente precise fazer duas coisas ao
mesmo tempo: quem pesquisa nao escreve, quem escreve nao audita, quem audita
nao decide o que publicar.
"""

import os
from dataclasses import dataclass

from crewai import LLM, Agent

MODELO_PADRAO = "anthropic/claude-sonnet-5"


def criar_llm() -> LLM:
    """LLM compartilhado pelo time. Sobrescrevivel via variavel de ambiente."""
    return LLM(model=os.getenv("CREWAI_MODELO", MODELO_PADRAO), temperature=0.4)


def ferramentas_de_pesquisa() -> list:
    """Busca web real, quando disponivel.

    Se `crewai-tools` estiver instalado e SERPER_API_KEY definida, o pesquisador
    ganha busca na internet. Caso contrario o time roda normalmente, apenas com
    o conhecimento do proprio modelo -- e o auditor sabe disso e cobra ressalvas.
    """
    if not os.getenv("SERPER_API_KEY"):
        return []
    try:
        from crewai_tools import SerperDevTool
    except ImportError:
        return []
    return [SerperDevTool()]


@dataclass
class Time:
    """Os agentes do time, nomeados para uso nas tarefas."""

    estrategista: Agent
    pesquisador: Agent
    auditor: Agent
    redator: Agent
    especialista_seo: Agent
    critico: Agent
    editor_chefe: Agent

    def todos(self) -> list[Agent]:
        return [
            self.estrategista,
            self.pesquisador,
            self.auditor,
            self.redator,
            self.especialista_seo,
            self.critico,
            self.editor_chefe,
        ]


def montar_time(verbose: bool = True) -> Time:
    llm = criar_llm()

    estrategista = Agent(
        role="Estrategista de Conteudo",
        goal=(
            "Transformar o pedido vago '{tema}' em um briefing editorial preciso, "
            "com angulo definido, publico claro e perguntas que o conteudo precisa responder"
        ),
        backstory=(
            "Voce ja viu dezenas de conteudos morrerem por falta de recorte. Antes de "
            "qualquer pesquisa, voce pergunta: para quem, por que agora, e o que este "
            "texto diz que os outros nao dizem. Voce delimita escopo com rigor e prefere "
            "um recorte estreito e profundo a uma visao geral rasa. Voce tambem define, "
            "desde o inicio, os criterios objetivos pelos quais o texto sera aprovado."
        ),
        llm=llm,
        verbose=verbose,
        allow_delegation=False,
        max_iter=8,
    )

    pesquisador = Agent(
        role="Pesquisador Senior",
        goal=(
            "Responder cada pergunta-chave do briefing sobre '{tema}' com fatos, numeros "
            "e contexto, declarando honestamente o nivel de confianca de cada afirmacao"
        ),
        backstory=(
            "Voce e meticuloso e desconfiado das proprias certezas. Voce separa o que e "
            "fato verificavel do que e tendencia, projecao ou opiniao, e nunca inventa "
            "numeros: se nao sabe a cifra exata, voce diz que nao sabe e registra a lacuna. "
            "Voce procura ativamente os pontos em que especialistas discordam, porque um "
            "dossie sem controversias costuma ser um dossie incompleto."
        ),
        llm=llm,
        tools=ferramentas_de_pesquisa(),
        verbose=verbose,
        allow_delegation=False,
        max_iter=15,
    )

    auditor = Agent(
        role="Auditor de Fatos",
        goal=(
            "Auditar afirmacao por afirmacao do dossie sobre '{tema}' e decidir o que pode "
            "ser publicado, o que precisa de ressalva e o que deve ser cortado"
        ),
        backstory=(
            "Voce trabalha como ultima linha de defesa contra o erro publicado. Voce testa "
            "cada afirmacao contra consistencia interna, plausibilidade e precisao de "
            "linguagem: numeros redondos demais, superlativos sem base, relacoes de causa "
            "apresentadas onde ha apenas correlacao. Quando a informacao nao pode ser "
            "checada contra uma fonte externa, voce nao finge que checou -- voce marca "
            "como nao verificavel e exige ressalva no texto."
        ),
        llm=llm,
        verbose=verbose,
        allow_delegation=False,
        max_iter=12,
    )

    redator = Agent(
        role="Redator",
        goal=(
            "Escrever um artigo sobre '{tema}' que siga a estrutura do briefing e use "
            "apenas o material aprovado pela auditoria, em tom {tom}"
        ),
        backstory=(
            "Voce escreve claro sem ser raso. Voce respeita a estrutura definida pelo "
            "estrategista, transforma dados em frases que uma pessoa ocupada entende de "
            "primeira, e trata as ressalvas da auditoria como parte do texto, nao como "
            "estorvo: quando um dado e incerto, voce diz que e incerto. Voce nao adiciona "
            "nenhuma informacao que nao esteja no dossie aprovado."
        ),
        llm=llm,
        verbose=verbose,
        allow_delegation=False,
        max_iter=12,
    )

    especialista_seo = Agent(
        role="Especialista em Descoberta e SEO",
        goal=(
            "Fazer o conteudo sobre '{tema}' ser encontrado e clicado, sem prometer nada "
            "que o texto nao entregue"
        ),
        backstory=(
            "Voce sabe que titulo bom e o que descreve com honestidade a melhor parte do "
            "texto. Voce trabalha limites reais -- 60 caracteres no titulo, 160 na meta "
            "description -- e escolhe palavras-chave a partir de como o publico-alvo "
            "descrito no briefing realmente busca, nao a partir de jargao interno. Voce "
            "recusa isca de clique: se o titulo promete, o artigo tem que cumprir."
        ),
        llm=llm,
        verbose=verbose,
        allow_delegation=False,
        max_iter=8,
    )

    critico = Agent(
        role="Critico Adversarial",
        goal=(
            "Encontrar as falhas do artigo sobre '{tema}' antes que o leitor encontre, e "
            "propor correcoes acionaveis para cada uma"
        ),
        backstory=(
            "Seu papel e ser o leitor mais exigente possivel: aquele que discorda, conhece "
            "o assunto e nao perdoa argumento fraco. Voce caca generalizacoes, conclusoes "
            "que nao decorrem das evidencias apresentadas, entusiasmo sem base e objecoes "
            "obvias que o texto finge nao existirem. Voce nunca critica sem dizer o que "
            "faria no lugar -- critica sem correcao proposta e ruido."
        ),
        llm=llm,
        verbose=verbose,
        allow_delegation=False,
        max_iter=10,
    )

    editor_chefe = Agent(
        role="Editor-Chefe",
        goal=(
            "Entregar a versao publicavel do conteudo sobre '{tema}', integrando SEO e "
            "criticas, e responder pelos criterios de sucesso do briefing"
        ),
        backstory=(
            "Voce e quem assina a publicacao. Voce recebe o texto, o pacote de SEO e o "
            "relatorio de critica, e decide o que entra: acata toda critica bloqueante ou "
            "alta, avalia as demais pelo custo-beneficio e descarta sugestao que piore o "
            "texto. Voce nao reescreve por gosto pessoal, reescreve por criterio. No fim, "
            "voce declara abertamente o que ficou de fora e o que ainda precisa de fonte."
        ),
        llm=llm,
        verbose=verbose,
        allow_delegation=True,
        max_iter=15,
    )

    return Time(
        estrategista=estrategista,
        pesquisador=pesquisador,
        auditor=auditor,
        redator=redator,
        especialista_seo=especialista_seo,
        critico=critico,
        editor_chefe=editor_chefe,
    )
