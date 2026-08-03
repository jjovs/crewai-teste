"""Time de agentes de IA (CrewAI) para producao de conteudo editorial.

Sete agentes trabalham em cadeia: o Estrategista transforma o pedido em um
briefing, o Pesquisador levanta o material, o Auditor de Fatos decide o que
pode ser publicado, o Redator escreve, o Especialista em SEO e o Critico
Adversarial atacam o texto em paralelo, e o Editor-Chefe fecha a edicao e
presta contas do processo.

Requer a variavel de ambiente ANTHROPIC_API_KEY definida (ver README.md).

    python main.py "Inteligencia Artificial na educacao"
    python main.py "Reforma tributaria" --publico "contadores" --tom "tecnico"
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

from crew import montar_crew

load_dotenv()

TEMA_PADRAO = "Inteligencia Artificial na educacao"
DIRETORIO_SAIDA = Path("saida")


def _slug(texto: str) -> str:
    limpo = "".join(c if c.isalnum() else "-" for c in texto.lower())
    return "-".join(p for p in limpo.split("-") if p)[:60] or "conteudo"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Roda o time de agentes de IA sobre um tema.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "tema",
        nargs="?",
        default=TEMA_PADRAO,
        help="Tema a ser trabalhado pelo time",
    )
    parser.add_argument(
        "--publico",
        default="publico geral interessado no assunto, sem formacao tecnica na area",
        help="Perfil do publico-alvo do conteudo",
    )
    parser.add_argument(
        "--tom",
        default="informativo, direto e acessivel",
        help="Tom de voz desejado para o texto",
    )
    parser.add_argument(
        "--palavras-chave",
        default="nenhuma palavra-chave obrigatoria",
        help="Palavras-chave que o especialista em SEO deve considerar",
    )
    parser.add_argument(
        "--saida",
        default=None,
        help="Caminho do arquivo Markdown final (padrao: saida/<slug>-<data>.md)",
    )
    parser.add_argument(
        "--silencioso",
        action="store_true",
        help="Esconde o passo a passo dos agentes e imprime apenas o resultado",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "Defina a variavel de ambiente ANTHROPIC_API_KEY antes de rodar "
            "(veja o README.md para instrucoes)."
        )

    args = parse_args(argv)

    if args.saida:
        arquivo_saida = Path(args.saida)
    else:
        carimbo = datetime.now().strftime("%Y%m%d-%H%M")
        arquivo_saida = DIRETORIO_SAIDA / f"{_slug(args.tema)}-{carimbo}.md"
    arquivo_saida.parent.mkdir(parents=True, exist_ok=True)

    crew = montar_crew(arquivo_saida=str(arquivo_saida), verbose=not args.silencioso)

    resultado = crew.kickoff(
        inputs={
            "tema": args.tema,
            "publico": args.publico,
            "tom": args.tom,
            "palavras_chave": args.palavras_chave,
        }
    )

    print("\n\n=== CONTEUDO FINAL ===\n")
    print(resultado)
    print(f"\n\nArquivo salvo em: {arquivo_saida}")

    uso = getattr(resultado, "token_usage", None)
    if uso is not None:
        print(f"Consumo de tokens: {uso}")


if __name__ == "__main__":
    main()
