"""O fluxo de trabalho da equipe, com loop de revisao.

    Caio (ideias) -> Vera (pauta) -> Iris + Theo (design) -> Lila + Rui (sessao)
                                          ^                        |
                                          |                        v
                                          +---- Vera devolve <-- Vera revisa
                                                                   |
                                                              Vera aprova -> entrega

O loop existe porque a Vera pode devolver o trabalho. Ele e implementado com
`@router` emitindo "refazer" e a etapa de design escutando `or_(pauta, "refazer")`.
Atencao ao mexer nisso: se mais de um metodo escutar "refazer", a etapa dispara
duas vezes por rodada.
"""

from __future__ import annotations

from typing import Any

from crewai import Crew, Process, Task
from crewai.flow.flow import Flow, listen, or_, router, start

from equipe.agentes import Equipe, montar_equipe
from equipe.config import Config
from equipe.ferramentas import ferramentas_de_codigo
from equipe.navegador import (
    CREDENCIAIS_CONNOSR,
    ROTA_CONNOSR,
    sessoes_de_navegador,
)
from equipe.modelos import (
    CacaDeIdeias,
    EntregaDeDesign,
    EstadoDaRodada,
    ParecerDaVera,
    PautaDaRodada,
    RelatorioDeSessao,
)

REFERENCIAS = "BeReal, Instagram e Letterboxd"


class FluxoDaEquipe(Flow[EstadoDaRodada]):
    """Uma rodada completa de evolucao de interface."""

    initial_state = EstadoDaRodada

    def __init__(self, config: Config, equipe: Equipe | None = None, painel=None, **kw: Any) -> None:
        super().__init__(**kw)
        self._config = config
        self._painel = painel
        self._kit_iris = ferramentas_de_codigo(
            config.repo_alvo, config.cerca_de("Iris"), config.permitir_escrita
        )
        self._kit_theo = ferramentas_de_codigo(
            config.repo_alvo, config.cerca_de("Theo"), config.permitir_escrita
        )
        self._kits_app = sessoes_de_navegador(
            config.url_do_app,
            config.credenciais or CREDENCIAIS_CONNOSR,
            config.rota_de_login or ROTA_CONNOSR,
            headless=config.headless,
        )
        lila = self._kits_app.get("Lila") if self._kits_app else None
        rui = self._kits_app.get("Rui") if self._kits_app else None
        self._equipe = equipe or montar_equipe(
            config,
            ferramentas_de_iris=self._kit_iris.ferramentas if self._kit_iris else None,
            ferramentas_de_theo=self._kit_theo.ferramentas if self._kit_theo else None,
            ferramentas_de_lila=lila.ferramentas if lila else None,
            ferramentas_de_rui=rui.ferramentas if rui else None,
        )

    # --- 1. Caio cacar ideias ----------------------------------------------

    @start()
    def cacar_ideias(self) -> None:
        cfg = self._config
        self.state.foco = cfg.foco
        self.state.max_rodadas = cfg.max_rodadas
        self.state.modo_codigo = cfg.modo_codigo
        self.state.modo_navegador = self._kits_app is not None

        tarefa = Task(
            description=(
                f"O produto e uma rede social onde as pessoas avaliam experiencias que "
                f"viveram - lugares, servicos, eventos. O foco desta rodada e: {cfg.foco}.\n\n"
                f"Levante de 6 a 10 ideias de interface social inspiradas em {REFERENCIAS}, "
                "cobrindo as tres referencias. Para cada ideia diga qual principio voce "
                "extraiu do app original, por que ele faz sentido numa rede de avaliacao de "
                "experiencias, como ficaria concretamente aqui, o impacto esperado, o esforco "
                "e o risco de irritar o usuario.\n\n"
                "Nao proponha copiar telas. Extraia o principio - o incentivo que a tela cria - "
                "e proponha como ele viraria outra coisa neste produto.\n\n"
                "Feche com o padrao dominante que conecta as melhores ideias, e com uma lista "
                "honesta do que dessas referencias seria ruim aqui."
            ),
            expected_output="Lista estruturada de ideias com referencia, aplicacao, impacto, esforco e risco.",
            agent=self._equipe.caio,
            output_pydantic=CacaDeIdeias,
        )
        resultado = self._rodar(self._equipe.caio, tarefa)
        self.state.caca = resultado
        self.state.registrar(f"Caio trouxe {len(resultado.ideias)} ideias")

    # --- 2. Vera define a pauta --------------------------------------------

    @listen(cacar_ideias)
    def definir_pauta(self) -> None:
        tarefa = Task(
            description=(
                "Voce recebeu as ideias do Caio. Monte a pauta desta rodada.\n\n"
                "Escolha de 2 a 5 itens e distribua entre os dois designers, respeitando o "
                "escopo de cada um:\n"
                "- Iris cuida de estrutura, navegacao, hierarquia de informacao e estados de "
                "tela (vazio, carregando, erro, primeiro acesso).\n"
                "- Theo cuida de cor, tipografia, espacamento, ritmo e micro-interacoes.\n\n"
                "Um item que exija os dois deve ser quebrado em dois itens, um para cada, "
                "porque eles trabalham em arquivos diferentes e nao podem colidir.\n\n"
                "Para cada item escreva um criterio de aceite verificavel - algo que voce "
                "consiga conferir olhando o resultado, nao uma questao de gosto.\n\n"
                "Diga tambem o que fica adiado e o que voce recusa, sempre com o motivo."
            ),
            expected_output="Pauta com itens distribuidos entre Iris e Theo, cada um com criterio de aceite.",
            agent=self._equipe.vera,
            output_pydantic=PautaDaRodada,
        )
        pauta = self._rodar(self._equipe.vera, tarefa, contexto=self._contexto_ideias())
        self.state.pauta = pauta
        self.state.registrar(f"Vera fechou a pauta com {len(pauta.itens)} itens")

    # --- 3. Iris e Theo desenham (loop volta aqui) -------------------------

    @listen(or_(definir_pauta, "refazer"))
    def desenhar(self) -> None:
        self.state.rodada += 1
        if self._painel:
            self._painel.marcar_rodada(self.state.rodada, self.state.max_rodadas)
        for kit in (self._kit_iris, self._kit_theo):
            if kit:
                kit.limpar_registro()

        correcoes = self._texto_das_correcoes()
        if self.state.modo_codigo:
            modo = (
                "Voce PODE editar arquivos do projeto. Leia antes de escrever, e faca as "
                "mudancas de verdade. O campo `arquivos_tocados` e preenchido "
                "automaticamente pelo registro da ferramenta, nao pelo seu relato."
            )
        elif self._kit_iris is not None:
            modo = (
                "MODO PROPOSTA. Voce tem ferramentas de LEITURA do projeto (listar, ler e "
                "buscar), mas NAO pode editar nada - e isso e intencional nesta rodada.\n"
                "Use a leitura a fundo: antes de propor qualquer coisa, veja como o codigo "
                "esta hoje. Nao invente nome de arquivo, de componente ou de token: confira. "
                "Uma proposta que cita o arquivo exato e o trecho exato a mudar vale dez "
                "vezes mais que uma proposta generica.\n"
                "Entregue a especificacao detalhada, indicando em `alvo` o caminho real do "
                "arquivo que precisaria mudar. Deixe `arquivos_tocados` vazio."
            )
        else:
            modo = (
                "Voce NAO tem acesso ao codigo nesta rodada. Entregue a especificacao "
                "detalhada da mudanca e deixe `arquivos_tocados` vazio."
            )

        tarefas = []
        for agente, nome, escopo in (
            (
                self._equipe.iris,
                "Iris",
                "estrutura, navegacao, hierarquia de informacao e estados de tela",
            ),
            (
                self._equipe.theo,
                "Theo",
                "cor, tipografia, espacamento, ritmo e micro-interacoes",
            ),
        ):
            tarefas.append(
                Task(
                    description=(
                        f"Execute os itens da pauta que sao seus (dono = {nome}). Seu escopo "
                        f"e {escopo}.\n\n{modo}\n\n"
                        "Nao invada o escopo do outro designer: se precisar de algo que e dele, "
                        "registre como pendencia em vez de fazer.\n\n"
                        "Para cada mudanca explique o alvo, o que muda, qual item da pauta isso "
                        "atende e como fica do ponto de vista de quem usa o app.\n\n"
                        f"{correcoes}"
                    ),
                    expected_output=f"Entrega de design assinada por {nome}, com mudancas e pendencias.",
                    agent=agente,
                    output_pydantic=EntregaDeDesign,
                )
            )

        saidas = self._rodar_varias(
            [self._equipe.iris, self._equipe.theo], tarefas, contexto=self._contexto_pauta()
        )
        self.state.entregas = [s for s in saidas if isinstance(s, EntregaDeDesign)]

        # O agente pode se enganar ao relatar o que editou; o registro da
        # ferramenta e a verdade. Sobrescrevemos o auto-relato.
        registros = {"Iris": self._kit_iris, "Theo": self._kit_theo}
        for entrega in self.state.entregas:
            kit = registros.get(entrega.autor)
            if kit is not None:
                entrega.arquivos_tocados = kit.arquivos_tocados()

        tocados = sum(len(e.arquivos_tocados) for e in self.state.entregas)
        self.state.registrar(
            f"Iris e Theo entregaram (rodada {self.state.rodada}, {tocados} arquivo(s) editado(s))"
        )

    # --- 4. Lila e Rui usam o produto --------------------------------------

    @listen(desenhar)
    def simular_uso(self) -> None:
        modo = (
            "O app esta rodando e voce tem ferramentas para usa-lo de verdade. Use-o."
            if self.state.modo_navegador
            else "O app nao esta acessivel nesta rodada. Simule a sessao a partir do desenho "
            "descrito pelos designers, sendo realista sobre o que voce conseguiria ou nao fazer."
        )
        contexto = self._contexto_entregas()

        explorar_lila = Task(
            description=(
                f"{modo}\n\nVoce e a Lila. Entre no produto com o desenho novo e faca o que "
                "voce faria num dia comum: veja o feed, publique uma avaliacao de algo que "
                "voce viveu, reaja ao que os outros postaram. Narre cada acao e o que voce "
                "sentiu ao fazer - inclusive impaciencia, duvida e tedio."
            ),
            expected_output="Narrativa das acoes da Lila, com reacao honesta a cada passo.",
            agent=self._equipe.lila,
        )
        reagir_rui = Task(
            description=(
                f"{modo}\n\nVoce e o Rui. Entre no produto, leia o feed - incluindo o que a "
                "Lila acabou de publicar - e decida se vale responder. Comente algo dela se "
                "fizer sentido. Diga em que momento exato voce fecharia o app e por que."
            ),
            expected_output="Narrativa das acoes do Rui, com o ponto de desistencia identificado.",
            agent=self._equipe.rui,
            context=[explorar_lila],
        )
        responder_lila = Task(
            description=(
                "Voce e a Lila. O Rui interagiu com voce. Responda como responderia de verdade "
                "e diga se essa troca te daria vontade de voltar amanha."
            ),
            expected_output="Resposta da Lila ao Rui e avaliacao do valor da interacao.",
            agent=self._equipe.lila,
            context=[reagir_rui],
        )
        relatorio = Task(
            description=(
                "Voce e o Rui, e agora escreve o relatorio da sessao para a Vera.\n\n"
                "Consolide o que voce e a Lila viveram: a sequencia de interacoes, os pontos "
                "de atrito ordenados por gravidade, o que funcionou e deve ser preservado, e "
                "o veredito honesto sobre se voces voltariam amanha.\n\n"
                "Para cada atrito, levante a hipotese de qual decisao de design o causou - "
                "isso e o que a Vera vai usar para devolver o trabalho ao designer certo.\n\n"
                f"Registre o modo da sessao como "
                f"'{'app_real' if self.state.modo_navegador else 'simulacao'}'."
            ),
            expected_output="Relatorio da sessao com interacoes, atritos por gravidade e veredito.",
            agent=self._equipe.rui,
            context=[explorar_lila, reagir_rui, responder_lila],
            output_pydantic=RelatorioDeSessao,
        )

        saidas = self._rodar_varias(
            [self._equipe.lila, self._equipe.rui],
            [explorar_lila, reagir_rui, responder_lila, relatorio],
            contexto=contexto,
        )
        sessao = next((s for s in reversed(saidas) if isinstance(s, RelatorioDeSessao)), None)
        self.state.sessao = sessao
        if sessao and self._painel:
            self._painel.registrar_atritos("Rui", len(sessao.atritos))
            self._painel.registrar_atritos("Lila", sum(1 for a in sessao.atritos if a.quem in ("Lila", "ambos")))
        self.state.registrar(
            f"Sessao gerou {len(sessao.atritos) if sessao else 0} atritos"
        )

    # --- 5. Vera revisa -----------------------------------------------------

    @listen(simular_uso)
    def revisar(self) -> None:
        ultima = self.state.rodada >= self.state.max_rodadas
        tarefa = Task(
            description=(
                "Revise o trabalho da rodada. Voce tem a pauta que voce mesma escreveu, as "
                "entregas da Iris e do Theo, e o relatorio da sessao de Lila e Rui.\n\n"
                "Confira nesta ordem:\n"
                "1. Cada item da pauta cumpriu o criterio de aceite que voce definiu?\n"
                "2. O trabalho da Iris contradiz o do Theo em algum ponto?\n"
                "3. Os atritos que as personas encontraram apontam para alguma decisao de "
                "design desta rodada?\n\n"
                "Se algo falhou, o veredito e 'refazer' e voce escreve correcoes especificas, "
                "cada uma endereçada a Iris ou ao Theo, com gravidade e origem. Se esta tudo "
                "de pe, o veredito e 'aprovado' e a lista de correcoes fica vazia.\n\n"
                + (
                    "ATENCAO: esta e a ultima rodada permitida. Aprove o que estiver aceitavel "
                    "e registre o que ficou pendente em itens_nao_atendidos, em vez de pedir "
                    "outra rodada que nao vai acontecer."
                    if ultima
                    else "Seja exigente: ainda ha rodadas disponiveis para corrigir."
                )
            ),
            expected_output="Parecer com veredito, itens atendidos e nao atendidos, correcoes e nota.",
            agent=self._equipe.vera,
            output_pydantic=ParecerDaVera,
        )
        parecer = self._rodar(self._equipe.vera, tarefa, contexto=self._contexto_revisao())
        self.state.parecer = parecer
        self.state.correcoes_pendentes = list(parecer.correcoes)

        if self._painel:
            aprovado = parecer.veredito == "aprovado"
            for entrega in self.state.entregas:
                self._painel.registrar_entrega(
                    entrega.autor,
                    aprovada_de_primeira=aprovado and self.state.rodada == 1,
                )
            self._painel.registrar_evento(
                f"Vera: {parecer.veredito} (nota {parecer.nota_da_rodada}/10)"
            )
        self.state.registrar(f"Vera deu veredito '{parecer.veredito}'")

    # --- 6. roteamento ------------------------------------------------------

    @router(revisar)
    def decidir(self) -> str:
        parecer = self.state.parecer
        if parecer is not None and parecer.veredito == "aprovado":
            self.state.encerrada_por = "aprovacao da Vera"
            return "aprovado"
        if self.state.rodada >= self.state.max_rodadas:
            self.state.encerrada_por = f"limite de {self.state.max_rodadas} rodadas"
            return "aprovado"
        self.state.registrar("Vera devolveu o trabalho - nova rodada")
        return "refazer"

    @listen("aprovado")
    def entregar(self) -> EstadoDaRodada:
        if self._kits_app is not None:
            self._kits_app.fechar()
        self.state.registrar(f"Rodada encerrada por {self.state.encerrada_por}")
        if self._painel:
            self._painel.registrar_evento(f"encerrado: {self.state.encerrada_por}")
        return self.state

    # --- auxiliares ---------------------------------------------------------

    def _rodar(self, agente, tarefa: Task, contexto: str = "") -> Any:
        if contexto:
            tarefa.description = f"{contexto}\n\n---\n\n{tarefa.description}"
        crew = Crew(
            agents=[agente],
            tasks=[tarefa],
            process=Process.sequential,
            verbose=self._config.verbose,
        )
        saida = crew.kickoff()
        return saida.pydantic if saida.pydantic is not None else saida.raw

    def _rodar_varias(self, agentes: list, tarefas: list[Task], contexto: str = "") -> list[Any]:
        if contexto:
            tarefas[0].description = f"{contexto}\n\n---\n\n{tarefas[0].description}"
        crew = Crew(
            agents=agentes,
            tasks=tarefas,
            process=Process.sequential,
            verbose=self._config.verbose,
        )
        saida = crew.kickoff()
        return [t.pydantic if t.pydantic is not None else t.raw for t in saida.tasks_output]

    def _contexto_ideias(self) -> str:
        caca = self.state.caca
        if caca is None:
            return ""
        linhas = [
            f"- {i.titulo} (ref: {i.referencia}, impacto {i.impacto_esperado}, esforco {i.esforco})"
            f"\n    aplicacao: {i.aplicacao}\n    risco: {i.risco}"
            for i in caca.ideias
        ]
        return (
            "IDEIAS TRAZIDAS PELO CAIO:\n"
            + "\n".join(linhas)
            + f"\n\nPadrao dominante: {caca.padrao_dominante}"
            + "\nNao copiar: "
            + "; ".join(caca.o_que_nao_copiar)
        )

    def _contexto_pauta(self) -> str:
        pauta = self.state.pauta
        if pauta is None:
            return ""
        itens = [
            f"- [{i.dono}] {i.ideia}\n    entregavel: {i.entregavel}\n    aceite: {i.criterio_de_aceite}"
            for i in pauta.itens
        ]
        return f"PAUTA DA RODADA - {pauta.tema}\n" + "\n".join(itens)

    def _contexto_entregas(self) -> str:
        if not self.state.entregas:
            return ""
        blocos = []
        for e in self.state.entregas:
            mudancas = "\n".join(
                f"    - {m.alvo}: {m.mudanca} (antes/depois: {m.antes_depois})" for m in e.mudancas
            )
            blocos.append(f"ENTREGA DE {e.autor.upper()} - escopo: {e.escopo}\n{mudancas}")
        return "O DESENHO QUE VOCES VAO USAR:\n\n" + "\n\n".join(blocos)

    def _contexto_revisao(self) -> str:
        partes = [self._contexto_pauta(), self._contexto_entregas()]
        sessao = self.state.sessao
        if sessao is not None:
            atritos = "\n".join(
                f"    - [{a.gravidade}] ({a.quem}) {a.onde}: {a.problema}"
                f"\n      hipotese: {a.hipotese_de_causa}"
                for a in sessao.atritos
            )
            partes.append(
                f"RELATORIO DA SESSAO (modo {sessao.modo}):\n{atritos}"
                f"\n  Veredito das personas: {sessao.veredito_das_personas}"
            )
        return "\n\n".join(p for p in partes if p)

    def _texto_das_correcoes(self) -> str:
        if not self.state.correcoes_pendentes:
            return ""
        linhas = "\n".join(
            f"    - [{c.gravidade}] para {c.para}: {c.o_que} (origem: {c.origem})"
            for c in self.state.correcoes_pendentes
        )
        return (
            "A VERA DEVOLVEU O TRABALHO DA RODADA ANTERIOR. Aplique as correcoes que sao "
            f"suas antes de qualquer outra coisa:\n{linhas}"
        )
