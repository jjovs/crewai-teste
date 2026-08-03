"""Esquemas de saida estruturada usados pelas tarefas do time.

Cada tarefa "intermediaria" devolve um objeto Pydantic em vez de texto livre.
Isso obriga cada agente a entregar informacao no formato que o proximo agente
espera, e torna o resultado de cada etapa inspecionavel pelo codigo.
"""

from typing import List, Literal

from pydantic import BaseModel, Field


# --- Etapa 1: briefing editorial -------------------------------------------


class PerguntaChave(BaseModel):
    pergunta: str = Field(description="Pergunta que o conteudo final precisa responder")
    por_que_importa: str = Field(description="Por que essa pergunta importa para o publico-alvo")


class BriefingEditorial(BaseModel):
    tema_refinado: str = Field(description="O tema reescrito de forma especifica e delimitada")
    publico_alvo: str = Field(description="Quem le, qual o nivel de conhecimento previo")
    angulo_editorial: str = Field(description="A tese ou recorte que diferencia este conteudo")
    tom_de_voz: str = Field(description="Como o texto deve soar")
    perguntas_chave: List[PerguntaChave] = Field(
        description="Entre 4 e 6 perguntas que guiam a pesquisa e a redacao"
    )
    estrutura: List[str] = Field(description="Titulos das secoes previstas, na ordem")
    criterios_de_sucesso: List[str] = Field(
        description="Criterios objetivos usados pelo editor-chefe para aprovar o texto"
    )
    fora_de_escopo: List[str] = Field(description="O que deliberadamente nao sera abordado")


# --- Etapa 2: dossie de pesquisa -------------------------------------------


class Achado(BaseModel):
    afirmacao: str = Field(description="A afirmacao em uma frase")
    detalhe: str = Field(description="Contexto, numeros e nuances que sustentam a afirmacao")
    tipo: Literal["fato", "dado", "contexto", "tendencia", "opiniao"]
    confianca: Literal["alta", "media", "baixa"] = Field(
        description="O quao seguro o pesquisador esta da afirmacao"
    )
    origem: str = Field(
        description=(
            "De onde veio a informacao: nome da fonte consultada ou "
            "'conhecimento do modelo' quando nao houve consulta externa"
        )
    )
    responde_pergunta: str = Field(description="Qual pergunta-chave do briefing este achado responde")


class DossieDePesquisa(BaseModel):
    resumo_executivo: str = Field(description="O que a pesquisa descobriu, em ate 5 linhas")
    achados: List[Achado] = Field(description="Pelo menos 8 achados, cobrindo todas as perguntas-chave")
    numeros_relevantes: List[str] = Field(
        description="Dados quantitativos com unidade e periodo, ex: '40% dos alunos em 2024'"
    )
    controversias: List[str] = Field(description="Pontos em que especialistas discordam")
    lacunas: List[str] = Field(description="O que nao foi possivel apurar e por que")


# --- Etapa 3: auditoria de fatos -------------------------------------------


class VerificacaoDeAfirmacao(BaseModel):
    afirmacao: str
    veredito: Literal["verificado", "plausivel", "duvidoso", "nao_verificavel"]
    justificativa: str = Field(description="Por que o veredito foi esse")
    acao_recomendada: Literal["publicar", "publicar_com_ressalva", "reescrever", "remover"]


class RelatorioDeAuditoria(BaseModel):
    verificacoes: List[VerificacaoDeAfirmacao] = Field(
        description="Uma entrada para cada achado do dossie"
    )
    afirmacoes_bloqueadas: List[str] = Field(
        description="Afirmacoes que nao podem aparecer no texto final sem fonte externa"
    )
    riscos_de_vies: List[str] = Field(description="Vieses ou angulos ausentes detectados no dossie")
    nota_de_confiabilidade: int = Field(ge=0, le=10, description="Nota geral do dossie, de 0 a 10")
    parecer_final: str = Field(description="Recomendacao objetiva para o redator")


# --- Etapa 5: pacote de descoberta / SEO -----------------------------------


class PacoteDeDescoberta(BaseModel):
    titulo_principal: str = Field(description="Titulo com ate 60 caracteres")
    titulos_alternativos: List[str] = Field(description="3 variacoes de titulo com angulos diferentes")
    meta_description: str = Field(description="Resumo de 150 a 160 caracteres")
    slug: str = Field(description="URL amigavel, minusculas, sem acentos, separada por hifens")
    palavras_chave_primarias: List[str]
    palavras_chave_secundarias: List[str]
    subtitulos_sugeridos: List[str] = Field(description="Subtitulos H2 alinhados a estrutura do briefing")
    resumo_para_redes: str = Field(description="Chamada de ate 280 caracteres para redes sociais")


# --- Etapa 6: critica adversarial ------------------------------------------


class Critica(BaseModel):
    trecho: str = Field(description="Trecho ou secao criticada")
    problema: str = Field(description="Qual e a fragilidade")
    gravidade: Literal["bloqueante", "alta", "media", "baixa"]
    correcao_sugerida: str = Field(description="O que fazer para resolver, de forma acionavel")


class RelatorioDeCritica(BaseModel):
    criticas: List[Critica] = Field(description="Da mais grave para a menos grave")
    contra_argumentos_ausentes: List[str] = Field(
        description="Objecoes legitimas que o texto ignora"
    )
    veredito: Literal["aprovado", "aprovado_com_ajustes", "reprovado"]
    justificativa_do_veredito: str
