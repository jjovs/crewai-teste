"""Confirma que a ANTHROPIC_API_KEY chega ao processo E tem forma valida.

Existe como arquivo, e nao como `python -c`, de proposito: o Windows
PowerShell 5.1 reprocessa a linha de comando ao chamar um programa externo e
engole aspas duplas embutidas, o que quebrava o codigo antes dele rodar.

Checar so a presenca nao basta. Um terminal com bracketed paste mal resolvido
gruda os marcadores da colagem no valor -- a chave vira "\x1b[200~sk-ant-...~",
passa por qualquer teste de "nao esta vazia", e so a API reclama, com um 401
depois de a rodada ja ter comecado. Aqui isso e barrado antes.

Imprime tamanho e diagnostico. Nunca o valor.

Sai 0 quando a chave esta utilizavel, 1 quando nao.
"""

from __future__ import annotations

import os
import re
import sys

from dotenv import load_dotenv

PREFIXO = "sk-ant-"
# Depois do prefixo a Anthropic usa apenas estes caracteres.
CORPO_VALIDO = re.compile(r"^[A-Za-z0-9_-]+$")
COMPRIMENTO_MINIMO = 40
# Uma chave da Anthropic fica na casa dos 100 caracteres. Bem acima disso
# significa colagem repetida ou lixo grudado, nao uma chave maior.
COMPRIMENTO_MAXIMO = 250


def diagnosticar(chave: str) -> list[str]:
    """Lista o que ha de errado com a chave. Vazio = utilizavel."""
    problemas: list[str] = []

    if not chave:
        return ["A chave nao chegou ao processo.",
                "Confira se o .env tem uma linha ANTHROPIC_API_KEY=sk-ant-..."]

    if chave != chave.strip():
        problemas.append("Ha espaco ou quebra de linha nas pontas.")

    invisiveis = [c for c in chave if ord(c) < 32 or ord(c) == 127]
    if invisiveis:
        codigos = ", ".join(sorted({f"\\x{ord(c):02x}" for c in invisiveis}))
        problemas.append(
            f"Ha caractere de controle no valor ({codigos}). Sinal classico de "
            "colagem com bracketed paste: o terminal gravou \\x1b[200~ e ~ junto."
        )

    limpa = chave.strip()
    if not limpa.startswith(PREFIXO):
        inicio = "".join(c if c.isprintable() else "?" for c in limpa[:8])
        problemas.append(f"Nao comeca com '{PREFIXO}' (comeca com '{inicio}').")
    elif not CORPO_VALIDO.match(limpa[len(PREFIXO):]):
        estranhos = sorted({
            c for c in limpa[len(PREFIXO):] if not re.match(r"[A-Za-z0-9_-]", c)
        })
        visiveis = ", ".join(repr(c) for c in estranhos[:5])
        problemas.append(f"Ha caractere invalido depois do prefixo: {visiveis}.")

    if len(limpa) < COMPRIMENTO_MINIMO:
        problemas.append(
            f"Curta demais ({len(limpa)} caracteres; o esperado passa de "
            f"{COMPRIMENTO_MINIMO}). A colagem pode ter vindo cortada."
        )

    repeticoes = limpa.count(PREFIXO)
    if repeticoes > 1:
        problemas.append(
            f"O prefixo '{PREFIXO}' aparece {repeticoes} vezes: a chave foi "
            "colada mais de uma vez e as copias grudaram em um valor so. "
            "A leitura da chave e silenciosa por seguranca -- cole UMA vez e "
            "de Enter, mesmo sem ver nada na tela."
        )
    elif len(limpa) > COMPRIMENTO_MAXIMO:
        problemas.append(
            f"Longa demais ({len(limpa)} caracteres; o esperado fica perto de "
            f"100). Provavelmente ha texto extra grudado no valor."
        )

    return problemas


def main() -> int:
    load_dotenv()
    chave = os.getenv("ANTHROPIC_API_KEY") or ""

    print(f"    tamanho: {len(chave)} | prefixo sk-ant: {chave.startswith(PREFIXO)}")

    problemas = diagnosticar(chave)
    if not problemas:
        return 0

    for p in problemas:
        print(f"    problema: {p}")
    print("    Para regravar a chave:  rm .env && ./preparar_e_rodar.sh")
    return 1


if __name__ == "__main__":
    sys.exit(main())
