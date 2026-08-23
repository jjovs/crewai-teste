"""Confirma que a ANTHROPIC_API_KEY chega de fato ao processo Python.

Existe como arquivo, e nao como `python -c`, de proposito: o Windows
PowerShell 5.1 reprocessa a linha de comando ao chamar um programa externo e
engole aspas duplas embutidas, o que quebrava o codigo antes dele rodar.

Imprime tamanho e prefixo. Nunca o valor.

Sai 0 quando a chave chegou, 1 quando nao.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    chave = os.getenv("ANTHROPIC_API_KEY") or ""
    print(f"    tamanho: {len(chave)} | prefixo sk-ant: {chave.startswith('sk-ant')}")
    if not chave:
        print("    A chave nao chegou ao processo.")
        print("    Confira se o .env tem uma linha ANTHROPIC_API_KEY=sk-ant-...")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
