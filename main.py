"""Exemplo simples de CrewAI: um pesquisador busca informacoes sobre um tema
e um redator transforma essas informacoes em um resumo de 3 paragrafos.

Requer a variavel de ambiente ANTHROPIC_API_KEY definida (ver README.md).
"""

import os
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM

load_dotenv()

if not os.getenv("ANTHROPIC_API_KEY"):
    raise RuntimeError(
        "Defina a variavel de ambiente ANTHROPIC_API_KEY antes de rodar "
        "(veja o README.md para instrucoes)."
    )

llm = LLM(model="anthropic/claude-sonnet-5")

pesquisador = Agent(
    role="Pesquisador",
    goal="Buscar e reunir informacoes relevantes e atuais sobre o tema: {tema}",
    backstory=(
        "Voce e um pesquisador experiente, meticuloso e curioso. Seu trabalho "
        "e levantar fatos, dados e pontos de vista importantes sobre um tema, "
        "organizando-os de forma clara para que outra pessoa possa escrever "
        "um resumo a partir deles."
    ),
    llm=llm,
    verbose=True,
)

redator = Agent(
    role="Redator",
    goal="Transformar as informacoes pesquisadas em um resumo claro e envolvente",
    backstory=(
        "Voce e um redator habilidoso, especializado em transformar pesquisas "
        "densas em textos curtos e faceis de entender, mantendo a precisao "
        "das informacoes originais."
    ),
    llm=llm,
    verbose=True,
)

tarefa_pesquisa = Task(
    description=(
        "Pesquise sobre o tema '{tema}'. Reuna os principais fatos, dados, "
        "contexto historico e desenvolvimentos relevantes. Organize suas "
        "descobertas em topicos claros."
    ),
    expected_output="Uma lista de topicos com os principais achados sobre o tema.",
    agent=pesquisador,
)

tarefa_redacao = Task(
    description=(
        "Usando a pesquisa fornecida, escreva um resumo sobre '{tema}' contendo "
        "exatamente 3 paragrafos: o primeiro introduzindo o tema, o segundo "
        "aprofundando os pontos mais importantes, e o terceiro concluindo com "
        "uma reflexao ou perspectiva futura."
    ),
    expected_output="Um resumo em texto corrido com exatamente 3 paragrafos.",
    agent=redator,
    context=[tarefa_pesquisa],
)

crew = Crew(
    agents=[pesquisador, redator],
    tasks=[tarefa_pesquisa, tarefa_redacao],
    process=Process.sequential,
    verbose=True,
)


def main() -> None:
    tema = sys.argv[1] if len(sys.argv) > 1 else "Inteligencia Artificial na educacao"
    resultado = crew.kickoff(inputs={"tema": tema})
    print("\n\n=== RESUMO FINAL ===\n")
    print(resultado)


if __name__ == "__main__":
    main()
