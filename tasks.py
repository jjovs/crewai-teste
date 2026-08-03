"""As tarefas do time.

O fluxo tem sete etapas. As etapas 5 (SEO) e 6 (critica) so dependem do texto
do redator e nao dependem uma da outra, entao rodam em paralelo (`async_execution`)
antes do fechamento do editor-chefe.

    1. briefing      Estrategista
    2. pesquisa      Pesquisador          <- usa 1
    3. auditoria     Auditor de Fatos     <- usa 1, 2
    4. redacao       Redator              <- usa 1, 2, 3
    5. seo           Especialista em SEO  <- usa 1, 4      (paralelo)
    6. critica       Critico Adversarial  <- usa 1, 3, 4   (paralelo)
    7. fechamento    Editor-Chefe         <- usa tudo
"""

from crewai import Task

from agents import Time
from models import (
    BriefingEditorial,
    DossieDePesquisa,
    PacoteDeDescoberta,
    RelatorioDeAuditoria,
    RelatorioDeCritica,
)


def montar_tarefas(time: Time, arquivo_saida: str | None = None) -> list[Task]:
    briefing = Task(
        description=(
            "Analise o pedido de conteudo sobre '{tema}' e produza o briefing editorial "
            "que vai guiar todo o time.\n\n"
            "Voce precisa:\n"
            "1. Refinar o tema. '{tema}' provavelmente e amplo demais para um unico texto; "
            "delimite um recorte especifico que caiba em um artigo e que valha a pena ler.\n"
            "2. Definir o publico-alvo a partir do perfil informado ('{publico}'), incluindo "
            "o nivel de conhecimento previo que se pode assumir.\n"
            "3. Definir o angulo editorial: qual e a tese, o que este texto afirma que a "
            "cobertura generica sobre o assunto nao afirma.\n"
            "4. Formular de 4 a 6 perguntas-chave que o conteudo obrigatoriamente precisa "
            "responder, cada uma com a razao pela qual importa para esse publico.\n"
            "5. Propor a estrutura de secoes, na ordem, com titulos que ja indiquem o conteudo.\n"
            "6. Escrever criterios de sucesso objetivos e verificaveis -- coisas que o "
            "editor-chefe possa conferir item a item no fim do processo.\n"
            "7. Declarar explicitamente o que fica fora de escopo.\n\n"
            "O tom de voz alvo e '{tom}'. Nao pesquise nem escreva o conteudo agora: "
            "sua entrega e o plano, nao o texto."
        ),
        expected_output=(
            "Um briefing editorial estruturado, com tema refinado, publico, angulo, tom, "
            "perguntas-chave, estrutura de secoes, criterios de sucesso e fora de escopo."
        ),
        agent=time.estrategista,
        output_pydantic=BriefingEditorial,
    )

    pesquisa = Task(
        description=(
            "Usando o briefing como roteiro, faca a pesquisa de fundo sobre o tema refinado.\n\n"
            "Regras de trabalho:\n"
            "- Cada pergunta-chave do briefing precisa ter, no minimo, dois achados que a "
            "respondam. Nenhuma pergunta pode ficar sem resposta.\n"
            "- Classifique cada achado por tipo (fato, dado, contexto, tendencia, opiniao) e "
            "por confianca (alta, media, baixa).\n"
            "- Registre a origem de cada achado. Se voce tiver ferramenta de busca disponivel, "
            "use-a e cite a fonte consultada. Se nao tiver, escreva 'conhecimento do modelo' "
            "com honestidade -- essa marcacao e usada pela auditoria na etapa seguinte.\n"
            "- Nunca invente numeros, datas ou nomes de estudos. Numero que voce nao tem "
            "certeza vira lacuna, nao vira dado.\n"
            "- Levante ativamente as controversias: onde especialistas serios discordam e por que.\n"
            "- Liste as lacunas: o que seria necessario saber e voce nao conseguiu apurar.\n\n"
            "Produza pelo menos 8 achados no total."
        ),
        expected_output=(
            "Um dossie com resumo executivo, achados classificados por tipo/confianca/origem, "
            "numeros relevantes, controversias e lacunas assumidas."
        ),
        agent=time.pesquisador,
        context=[briefing],
        output_pydantic=DossieDePesquisa,
    )

    auditoria = Task(
        description=(
            "Audite o dossie de pesquisa antes que uma unica linha seja escrita.\n\n"
            "Para cada achado do dossie, emita um veredito:\n"
            "- verificado: sustentado por fonte externa citada ou por conhecimento "
            "consolidado e estavel;\n"
            "- plausivel: coerente e provavel, mas sem confirmacao direta;\n"
            "- duvidoso: ha sinal de imprecisao, exagero ou confusao de conceitos;\n"
            "- nao_verificavel: depende de dado que ninguem apresentou.\n\n"
            "Para cada veredito, recomende uma acao: publicar, publicar_com_ressalva, "
            "reescrever ou remover.\n\n"
            "Preste atencao especial a:\n"
            "- numeros suspeitosamente redondos ou sem periodo de referencia;\n"
            "- causalidade afirmada onde ha apenas correlacao;\n"
            "- superlativos e afirmacoes de primazia ('o primeiro', 'o maior');\n"
            "- projecoes de futuro apresentadas como fato;\n"
            "- vieses do dossie: qual perspectiva legitima ficou de fora.\n\n"
            "Liste separadamente as afirmacoes bloqueadas -- as que nao podem aparecer no "
            "texto sem fonte externa -- e de uma nota de confiabilidade de 0 a 10 ao dossie, "
            "com um parecer objetivo dirigido ao redator."
        ),
        expected_output=(
            "Um relatorio de auditoria com veredito e acao recomendada por afirmacao, lista "
            "de afirmacoes bloqueadas, riscos de vies, nota de 0 a 10 e parecer final."
        ),
        agent=time.auditor,
        context=[briefing, pesquisa],
        output_pydantic=RelatorioDeAuditoria,
    )

    redacao = Task(
        description=(
            "Escreva o artigo sobre o tema refinado, em portugues, formatado em Markdown.\n\n"
            "Restricoes que voce nao pode violar:\n"
            "- Siga a estrutura de secoes do briefing, na ordem definida.\n"
            "- Use somente material do dossie que a auditoria liberou. Afirmacao marcada como "
            "'remover' nao entra no texto. Afirmacao marcada como 'publicar_com_ressalva' entra "
            "com a ressalva escrita no proprio corpo do texto, de forma natural.\n"
            "- Nao acrescente fatos, numeros ou exemplos que nao estejam no dossie.\n"
            "- Respeite o tom '{tom}' e o nivel de conhecimento do publico '{publico}'.\n"
            "- Inclua as controversias levantadas: um texto que so mostra um lado envelhece mal.\n\n"
            "Formato: um titulo H1 provisorio, secoes em H2 seguindo o briefing, entre 700 e "
            "1100 palavras, paragrafos curtos. Feche com uma secao final que responda "
            "diretamente as perguntas-chave do briefing em formato de lista.\n\n"
            "Nao se preocupe com titulo otimizado nem com SEO -- outra pessoa cuida disso."
        ),
        expected_output=(
            "O artigo completo em Markdown, entre 700 e 1100 palavras, seguindo a estrutura "
            "do briefing e encerrando com as respostas as perguntas-chave."
        ),
        agent=time.redator,
        context=[briefing, pesquisa, auditoria],
    )

    seo = Task(
        description=(
            "A partir do artigo escrito e do briefing, monte o pacote de descoberta.\n\n"
            "Entregue:\n"
            "- um titulo principal de ate 60 caracteres, que descreva com honestidade o "
            "melhor do artigo;\n"
            "- 3 titulos alternativos com angulos diferentes entre si (um informativo, um "
            "orientado a beneficio, um provocativo mas nao enganoso);\n"
            "- uma meta description entre 150 e 160 caracteres;\n"
            "- um slug em minusculas, sem acentos, separado por hifens;\n"
            "- palavras-chave primarias e secundarias, escolhidas a partir de como o publico "
            "'{publico}' realmente buscaria por isso;\n"
            "- subtitulos H2 sugeridos, alinhados as secoes que o artigo ja tem;\n"
            "- uma chamada de ate 280 caracteres para redes sociais.\n\n"
            "Conte os caracteres antes de entregar. Titulo que estoura o limite e titulo "
            "cortado no resultado de busca. E nao prometa nada que o artigo nao entregue: "
            "se a chamada promete um numero, esse numero tem que estar no texto. "
            "Contexto adicional de palavras-chave desejadas: '{palavras_chave}'."
        ),
        expected_output=(
            "Pacote de descoberta com titulo principal, 3 alternativos, meta description, "
            "slug, palavras-chave primarias e secundarias, subtitulos e chamada para redes."
        ),
        agent=time.especialista_seo,
        context=[briefing, redacao],
        output_pydantic=PacoteDeDescoberta,
        async_execution=True,
    )

    critica = Task(
        description=(
            "Ataque o artigo. Seu trabalho e achar tudo que um leitor exigente acharia.\n\n"
            "Procure especificamente por:\n"
            "- conclusoes que nao decorrem das evidencias apresentadas;\n"
            "- generalizacoes ('todos', 'sempre', 'nunca') sem sustentacao;\n"
            "- entusiasmo ou pessimismo desproporcional ao que o dossie mostra;\n"
            "- ressalvas da auditoria que o redator ignorou ou suavizou demais;\n"
            "- perguntas-chave do briefing respondidas de forma vaga ou nao respondidas;\n"
            "- objecoes obvias que o texto finge nao existirem;\n"
            "- trechos onde o texto explica o obvio ou repete o que ja disse.\n\n"
            "Para cada critica, informe o trecho, o problema, a gravidade (bloqueante, alta, "
            "media, baixa) e uma correcao concreta e acionavel. Critica sem correcao proposta "
            "nao serve para nada.\n\n"
            "Liste tambem os contra-argumentos legitimos que o artigo deixou de fora, e feche "
            "com um veredito: aprovado, aprovado_com_ajustes ou reprovado."
        ),
        expected_output=(
            "Relatorio de critica ordenado por gravidade, com correcao sugerida em cada item, "
            "contra-argumentos ausentes e veredito final justificado."
        ),
        agent=time.critico,
        context=[briefing, auditoria, redacao],
        output_pydantic=RelatorioDeCritica,
        async_execution=True,
    )

    fechamento = Task(
        description=(
            "Feche a edicao. Voce recebeu o briefing, o dossie, a auditoria, o artigo, o "
            "pacote de SEO e o relatorio de critica. Produza a versao publicavel.\n\n"
            "Como decidir:\n"
            "- Toda critica de gravidade bloqueante ou alta deve ser resolvida no texto.\n"
            "- Criticas media e baixa: aplique as que melhoram o texto, descarte as que so "
            "adicionam ruido, e diga quais voce descartou e por que.\n"
            "- Adote o titulo do pacote de SEO se ele for honesto em relacao ao conteudo. Se "
            "nao for, escolha um dos alternativos ou escreva um melhor, e registre a troca.\n"
            "- Confira o texto final contra cada criterio de sucesso do briefing, um por um.\n\n"
            "Entregue um unico documento Markdown com, nesta ordem:\n"
            "1. um bloco de metadados no topo (titulo, slug, meta description, palavras-chave, "
            "publico-alvo, tom, contagem aproximada de palavras);\n"
            "2. o artigo final completo, ja com as correcoes aplicadas;\n"
            "3. uma secao 'Notas do editor' com: criterios de sucesso e se cada um foi "
            "atendido, criticas aplicadas, criticas descartadas com a justificativa, "
            "afirmacoes que seguem precisando de fonte externa, e as lacunas de pesquisa "
            "que continuam abertas.\n\n"
            "O artigo final e o produto; as notas do editor sao a prestacao de contas. "
            "Nao omita nada desconfortavel das notas."
        ),
        expected_output=(
            "Documento Markdown unico contendo bloco de metadados, artigo final revisado e "
            "secao 'Notas do editor' com a prestacao de contas do processo."
        ),
        agent=time.editor_chefe,
        context=[briefing, pesquisa, auditoria, redacao, seo, critica],
        output_file=arquivo_saida,
    )

    return [briefing, pesquisa, auditoria, redacao, seo, critica, fechamento]
