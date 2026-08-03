"""Montagem do Crew."""

from crewai import Crew, Process

from agents import montar_time
from tasks import montar_tarefas


def montar_crew(arquivo_saida: str | None = None, verbose: bool = True) -> Crew:
    time = montar_time(verbose=verbose)
    tarefas = montar_tarefas(time, arquivo_saida=arquivo_saida)

    return Crew(
        agents=time.todos(),
        tasks=tarefas,
        process=Process.sequential,
        verbose=verbose,
    )
