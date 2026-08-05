"""Executa uma rodada da equipe de agentes, com painel ao vivo.

    # ver o painel funcionando sem gastar API
    python rodar_equipe.py --demo

    # rodada real, modo proposta (sem repo alvo)
    python rodar_equipe.py "melhorar a descoberta de avaliacoes no feed"

    # rodada real com edicao de codigo e app rodando
    python rodar_equipe.py "onboarding do primeiro post" \\
        --repo ../rede-social --ui src/components src/styles \\
        --url-app http://localhost:3000
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Roda a equipe de agentes sobre o projeto da rede social.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("foco", nargs="?", default="melhorar a experiencia social do feed de avaliacoes")
    p.add_argument("--repo", type=Path, default=None, help="Raiz do repositorio da rede social")
    p.add_argument(
        "--projeto",
        choices=["connosr"],
        default=None,
        help="Usa o preset do projeto (cercas, URL e login ja configurados)",
    )
    p.add_argument(
        "--modo",
        choices=["proposta", "codigo"],
        default="proposta",
        help="proposta: Iris e Theo leem o codigo mas nao editam. codigo: editam de verdade",
    )
    p.add_argument("--ui", nargs="*", default=[], help="Diretorios de UI que Iris e Theo podem editar")
    p.add_argument("--ui-iris", nargs="*", default=[], help="Cerca so da Iris (sobrepoe --ui para ela)")
    p.add_argument("--ui-theo", nargs="*", default=[], help="Cerca so do Theo (sobrepoe --ui para ele)")
    p.add_argument("--url-app", default=None, help="URL do app rodando, ex: http://localhost:3000")
    p.add_argument("--rodadas", type=int, default=3, help="Maximo de rodadas antes de encerrar")
    p.add_argument("--porta", type=int, default=8777, help="Porta do painel")
    p.add_argument("--sem-painel", action="store_true")
    p.add_argument("--sem-navegador", action="store_true", help="Nao abrir o navegador sozinho")
    p.add_argument("--silencioso", action="store_true")
    p.add_argument("--demo", action="store_true", help="Aciona o painel com dados falsos, sem chamar a API")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    from equipe.config import Config
    from equipe.painel.metricas import PainelDeMetricas
    from equipe.painel.servidor import ServidorDoPainel

    comuns = dict(
        foco=args.foco,
        max_rodadas=args.rodadas,
        permitir_escrita=args.modo == "codigo",
        verbose=not args.silencioso,
        porta_do_painel=args.porta,
    )
    if args.projeto == "connosr":
        if not args.repo:
            raise SystemExit("--projeto connosr precisa de --repo apontando para o clone do ConnoSr.")
        config = Config.para_connosr(
            args.repo, **({"url_do_app": args.url_app} if args.url_app else {}), **comuns
        )
    else:
        config = Config(
            repo_alvo=args.repo,
            diretorios_de_ui=list(args.ui),
            diretorios_de_iris=list(args.ui_iris),
            diretorios_de_theo=list(args.ui_theo),
            url_do_app=args.url_app,
            **comuns,
        )

    servidor = None
    painel = None
    if not args.sem_painel:
        servidor = ServidorDoPainel(porta=config.porta_do_painel)
        url = servidor.iniciar(abrir_navegador=not args.sem_navegador)
        painel = PainelDeMetricas(ao_atualizar=servidor.publicar)
        print(f"Painel ao vivo em {url}\n")

    try:
        if args.demo:
            _demo(painel)
            return

        escrita = "EDITAM os arquivos" if config.modo_codigo else "NAO editam nada (modo proposta)"
        leitura = "leem o repositorio" if config.pode_ler_codigo else "sem acesso ao codigo"
        print(f"Foco: {config.foco}")
        print(f"Iris e Theo: {leitura}, {escrita}")
        print(
            "Lila e Rui: "
            + (f"usam o app em {config.url_do_app}" if config.modo_navegador else "simulam a sessao")
        )
        for aviso in config.validar():
            print(f"  aviso: {aviso}")
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise SystemExit("\nDefina ANTHROPIC_API_KEY para rodar de verdade (ou use --demo).")
        print()

        from equipe.fluxo import FluxoDaEquipe

        fluxo = FluxoDaEquipe(config=config, painel=painel)
        estado = fluxo.kickoff()
        _resumir(estado)
    finally:
        if servidor is not None and not args.demo:
            servidor.parar()


def _resumir(estado) -> None:
    print("\n\n=== RESULTADO DA RODADA ===\n")
    parecer = getattr(estado, "parecer", None)
    if parecer is not None:
        print(f"Veredito da Vera: {parecer.veredito} (nota {parecer.nota_da_rodada}/10)")
        print(f"Justificativa: {parecer.justificativa}\n")
        if parecer.itens_nao_atendidos:
            print("Ficou pendente:")
            for item in parecer.itens_nao_atendidos:
                print(f"  - {item}")
    print(f"\nRodadas: {getattr(estado, 'rodada', '?')}")
    print(f"Encerrada por: {getattr(estado, 'encerrada_por', '?')}\n")
    for linha in getattr(estado, "historico", []):
        print(f"  {linha}")


def _demo(painel) -> None:
    """Aciona o painel com uma rodada falsa, para conferir a interface."""
    if painel is None:
        raise SystemExit("--demo precisa do painel ligado (remova --sem-painel).")

    roteiro = [
        ("Caio - Cacador de Ideias", "pesquisando padroes do Letterboxd", 2.0, 5200),
        ("Vera - Chefe e Revisora", "montando a pauta da rodada", 1.5, 3100),
        ("Iris - Diretora de Interface", "reordenando a hierarquia do feed", 3.0, 8400),
        ("Theo - Diretor Visual", "ajustando escala tipografica", 2.5, 6700),
        ("Lila - Persona ativa", "publicando avaliacao de um cafe", 2.0, 4300),
        ("Rui - Persona lurker", "lendo o feed sem interagir", 2.0, 3900),
        ("Vera - Chefe e Revisora", "revisando as entregas", 2.0, 5600),
    ]
    painel.marcar_rodada(1, 3)
    print("Rodando demo do painel (Ctrl+C para sair)...\n")

    for role, atividade, duracao, tokens in roteiro:
        painel._atualizar(role, estado="trabalhando", papel=role, tarefa=atividade,
                          marcar_inicio=True, atividade=atividade)
        print(f"  {role.split('-')[0].strip():6} {atividade}")
        time.sleep(duracao)
        painel._atualizar(role, incrementar={"chamadas_llm": 3, "tokens_entrada": int(tokens * 0.7),
                                             "tokens_saida": int(tokens * 0.3)})
        painel._atualizar(role, estado="concluido", fechar_inicio=True,
                          incrementar={"execucoes": 1}, atividade="entregou o resultado")

    painel.registrar_entrega("Iris", aprovada_de_primeira=True)
    painel.registrar_entrega("Theo", aprovada_de_primeira=False)
    painel.registrar_atritos("Rui", 4)
    painel.registrar_atritos("Lila", 2)
    painel.registrar_evento("Vera: refazer (nota 6/10)")
    print("\nDemo concluida. O painel segue no ar - Ctrl+C para encerrar.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nencerrado.")


if __name__ == "__main__":
    main()
