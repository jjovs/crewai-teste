"""Roda uma rodada real e despeja estado + metricas em JSON, sem servidor de painel.

Existe por causa de uma limitacao do `rodar_equipe.py --sem-painel`: essa flag
passa `painel=None` para o fluxo, e o `PainelDeMetricas` e justamente o listener
do barramento do CrewAI que conta tempo e tokens por agente. Sem painel nao ha
metrica nenhuma no fim da rodada.

Como `PainelDeMetricas(ao_atualizar=...)` aceita callback opcional, da para
acoplar o coletor sem subir o servidor HTTP: metricas completas, sem porta
aberta e sem localhost. E o que este script faz.

Uso:
    python rodar_e_capturar.py --repo ../connosr --saida resultado.json

O modo e sempre proposta: `permitir_escrita=False` explicito, porque esse campo
e True por padrao no dataclass e so o CLI do rodar_equipe.py o desliga.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from equipe.config import Config
from equipe.fluxo import FluxoDaEquipe
from equipe.painel.metricas import PainelDeMetricas

# Mesma linha que main.py e rodar_equipe.py ja tinham. Sem ela, o .env que o
# README manda criar era ignorado justamente por este script, e a rodada so
# quebrava la na frente -- Config.validar() apenas avisa quando a chave falta.
load_dotenv()

FOCO_PADRAO = "fazer o feed parecer vivo no primeiro acesso"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("foco", nargs="?", default=FOCO_PADRAO)
    p.add_argument("--repo", type=Path, required=True, help="Raiz do clone do ConnoSr")
    p.add_argument("--rodadas", type=int, default=1)
    p.add_argument("--saida", type=Path, default=Path("resultado.json"))
    p.add_argument("--url-app", default=None, help="App no ar; sem isso as personas simulam")
    return p.parse_args(argv)


def serializar(valor: Any) -> Any:
    """Converte o estado do Flow (Pydantic) em algo que o json aceita."""
    if hasattr(valor, "model_dump"):
        return valor.model_dump(mode="json")
    if isinstance(valor, (list, tuple)):
        return [serializar(v) for v in valor]
    if isinstance(valor, Path):
        return str(valor)
    return valor


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    config = Config.para_connosr(
        args.repo,
        foco=args.foco,
        max_rodadas=args.rodadas,
        permitir_escrita=False,  # modo proposta: leem o codigo, nao editam nada
        verbose=True,
        **({"url_do_app": args.url_app} if args.url_app else {}),
    )
    if config.modo_codigo:
        raise SystemExit("Esperado modo proposta, mas a config veio em modo codigo.")

    print(f"Foco: {config.foco}")
    print(f"Iris e Theo: leem o repositorio, NAO editam nada (modo proposta)")
    for aviso in config.validar():
        print(f"  aviso: {aviso}")

    painel = PainelDeMetricas()  # coletor de eventos, sem servidor HTTP
    fluxo = FluxoDaEquipe(config=config, painel=painel)
    estado = fluxo.kickoff()

    dump = {
        "foco": config.foco,
        "modo": "proposta",
        "repo": str(args.repo),
        "estado": serializar(estado),
        "metricas": painel.snapshot(),
    }
    args.saida.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nEscrito: {args.saida}")


if __name__ == "__main__":
    main()
