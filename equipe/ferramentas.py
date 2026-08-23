"""Ferramentas de codigo para Iris e Theo, com cerca.

O projeto alvo pertence a outra pessoa, entao a regra aqui e simples: nenhuma
leitura ou escrita acontece fora dos diretorios explicitamente autorizados em
`Config.diretorios_de_ui`. A cerca e aplicada por resolucao de caminho real
(`Path.resolve()`), o que tambem barra `..` e symlink apontando para fora.

Nada aqui depende do framework do projeto alvo: sao operacoes de arquivo. O que
muda por stack e quais diretorios sao passados na configuracao.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

LIMITE_DE_LEITURA = 120_000
"""Bytes. Arquivo maior que isso e truncado, para nao estourar o contexto."""

EXTENSOES_DE_UI = {
    ".css", ".scss", ".sass", ".less", ".html", ".htm", ".vue", ".svelte",
    ".js", ".jsx", ".ts", ".tsx", ".astro", ".json", ".md",
}


class ForaDaCerca(Exception):
    """Tentativa de acessar caminho fora dos diretorios autorizados."""


class Cerca:
    """Resolve e valida caminhos contra os diretorios autorizados."""

    def __init__(self, raiz: Path, permitidos: list[str]) -> None:
        self.raiz = raiz.resolve()
        self.permitidos = [(self.raiz / p).resolve() for p in permitidos]
        if not self.permitidos:
            raise ValueError(
                "Nenhum diretorio autorizado: sem cerca definida, nenhuma escrita e permitida."
            )

    def resolver(self, caminho: str) -> Path:
        alvo = (self.raiz / caminho).resolve()
        for permitido in self.permitidos:
            if alvo == permitido or alvo.is_relative_to(permitido):
                return alvo
        autorizados = ", ".join(str(p.relative_to(self.raiz)) for p in self.permitidos)
        raise ForaDaCerca(
            f"'{caminho}' esta fora dos diretorios autorizados. Voce so pode tocar em: {autorizados}"
        )

    def relativo(self, alvo: Path) -> str:
        return str(alvo.relative_to(self.raiz))

    def varrer(self) -> list[Path]:
        arquivos: list[Path] = []
        for permitido in self.permitidos:
            if not permitido.is_dir():
                continue
            for item in sorted(permitido.rglob("*")):
                if not item.is_file() or self._ignorado(item):
                    continue
                # Um symlink pode apontar para fora da cerca. Nao listamos o que
                # a leitura recusaria: listagem e leitura tem que concordar.
                if item.resolve() != item and not self._dentro(item.resolve()):
                    continue
                arquivos.append(item)
        return arquivos

    def _dentro(self, alvo: Path) -> bool:
        return any(alvo == p or alvo.is_relative_to(p) for p in self.permitidos)

    @staticmethod
    def _ignorado(caminho: Path) -> bool:
        partes = set(caminho.parts)
        return bool(
            partes & {"node_modules", ".git", "dist", "build", ".next", "__pycache__", ".venv"}
        )


class _ComCerca(BaseTool):
    """Base das ferramentas: guarda a cerca fora do schema do Pydantic."""

    _cerca: Cerca = PrivateAttr()

    def __init__(self, cerca: Cerca, **kw: Any) -> None:
        super().__init__(**kw)
        self._cerca = cerca


# --- listar -----------------------------------------------------------------


class _SemArgs(BaseModel):
    pass


class ListarArquivosDeUI(_ComCerca):
    name: str = "listar_arquivos_de_ui"
    description: str = (
        "Lista os arquivos de interface que voce pode ler e editar, com o tamanho de cada um. "
        "Use isto primeiro, antes de tentar abrir qualquer arquivo."
    )
    args_schema: Type[BaseModel] = _SemArgs

    def _run(self) -> str:
        arquivos = self._cerca.varrer()
        if not arquivos:
            return "Nenhum arquivo encontrado nos diretorios autorizados."
        linhas = [
            f"{self._cerca.relativo(a)} ({a.stat().st_size} bytes)"
            for a in arquivos
            if a.suffix.lower() in EXTENSOES_DE_UI
        ]
        if not linhas:
            linhas = [self._cerca.relativo(a) for a in arquivos]
        return f"{len(linhas)} arquivo(s) disponivel(is):\n" + "\n".join(linhas)


# --- ler --------------------------------------------------------------------


class _ArgsLer(BaseModel):
    caminho: str = Field(description="Caminho do arquivo, relativo a raiz do projeto")


class LerArquivo(_ComCerca):
    name: str = "ler_arquivo"
    description: str = (
        "Le o conteudo de um arquivo de interface. O caminho deve estar dentro dos "
        "diretorios autorizados."
    )
    args_schema: Type[BaseModel] = _ArgsLer

    def _run(self, caminho: str) -> str:
        try:
            alvo = self._cerca.resolver(caminho)
        except ForaDaCerca as erro:
            return f"RECUSADO: {erro}"
        if not alvo.is_file():
            return f"Arquivo nao encontrado: {caminho}"
        texto = alvo.read_text(encoding="utf-8", errors="replace")
        if len(texto) > LIMITE_DE_LEITURA:
            return texto[:LIMITE_DE_LEITURA] + f"\n\n[... truncado em {LIMITE_DE_LEITURA} bytes ...]"
        return texto


# --- buscar -----------------------------------------------------------------


class _ArgsBuscar(BaseModel):
    padrao: str = Field(description="Expressao regular a procurar")
    extensao: str = Field(default="", description="Filtrar por extensao, ex: '.css'. Vazio = todas")


class BuscarNoCodigo(_ComCerca):
    name: str = "buscar_no_codigo"
    description: str = (
        "Procura um padrao (regex) nos arquivos autorizados e devolve os trechos com "
        "arquivo e linha. Util para achar onde uma cor, classe ou componente e usado."
    )
    args_schema: Type[BaseModel] = _ArgsBuscar

    def _run(self, padrao: str, extensao: str = "") -> str:
        try:
            regex = re.compile(padrao, re.IGNORECASE)
        except re.error as erro:
            return f"Regex invalida: {erro}"
        achados: list[str] = []
        for arquivo in self._cerca.varrer():
            if extensao and arquivo.suffix.lower() != extensao.lower():
                continue
            try:
                texto = arquivo.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for n, linha in enumerate(texto.splitlines(), 1):
                if regex.search(linha):
                    achados.append(f"{self._cerca.relativo(arquivo)}:{n}: {linha.strip()[:160]}")
                    if len(achados) >= 200:
                        return "\n".join(achados) + "\n[... limite de 200 resultados ...]"
        return "\n".join(achados) if achados else f"Nenhuma ocorrencia de '{padrao}'."


# --- escrever ---------------------------------------------------------------


class _ArgsEscrever(BaseModel):
    caminho: str = Field(description="Caminho do arquivo, relativo a raiz do projeto")
    conteudo: str = Field(description="Conteudo completo e final do arquivo")
    motivo: str = Field(description="Qual item da pauta esta mudanca atende")


class EscreverArquivo(_ComCerca):
    name: str = "escrever_arquivo"
    description: str = (
        "Grava o conteudo completo de um arquivo dentro dos diretorios autorizados e devolve "
        "o diff do que mudou. Passe SEMPRE o arquivo inteiro, nao um trecho: o conteudo "
        "substitui o arquivo. Informe o motivo, que vai para o registro da rodada."
    )
    args_schema: Type[BaseModel] = _ArgsEscrever

    # Registro por instancia, nao por classe: Iris e Theo tem ferramentas
    # separadas, e e isso que permite saber quem tocou cada arquivo.
    _registro: list[dict[str, str]] = PrivateAttr(default_factory=list)

    def _run(self, caminho: str, conteudo: str, motivo: str) -> str:
        try:
            alvo = self._cerca.resolver(caminho)
        except ForaDaCerca as erro:
            return f"RECUSADO: {erro}"

        antes = alvo.read_text(encoding="utf-8", errors="replace") if alvo.is_file() else ""
        if antes == conteudo:
            return f"Nada a fazer: {caminho} ja esta com esse conteudo."

        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(conteudo, encoding="utf-8")

        relativo = self._cerca.relativo(alvo)
        self._registro.append({"arquivo": relativo, "motivo": motivo})

        diff = list(
            difflib.unified_diff(
                antes.splitlines(), conteudo.splitlines(),
                fromfile=f"a/{relativo}", tofile=f"b/{relativo}", lineterm="", n=2,
            )
        )
        resumo = "\n".join(diff[:120])
        if len(diff) > 120:
            resumo += f"\n[... diff truncado, {len(diff)} linhas no total ...]"
        return f"Gravado {relativo} ({len(conteudo)} bytes).\n\n{resumo or '(arquivo novo)'}"

    def arquivos_tocados(self) -> list[dict[str, str]]:
        """Verdade sobre o que foi escrito - o agente pode se enganar no relato."""
        return list(self._registro)

    def limpar_registro(self) -> None:
        self._registro.clear()


# --- fabrica ----------------------------------------------------------------


class KitDeCodigo:
    """Ferramentas cercadas de um designer, com o registro do que ele tocou.

    Com `permitir_escrita=False` (modo proposta) a ferramenta de escrita nao e
    construida. O designer continua lendo e buscando no codigo real - o que faz
    a proposta dele ser especifica em vez de generica - mas nao ha como editar
    nada, nem por engano do modelo.
    """

    def __init__(
        self,
        raiz: Path,
        diretorios: list[str],
        permitir_escrita: bool = True,
        diretorios_de_leitura: list[str] | None = None,
    ) -> None:
        # Ler e escrever tem cercas diferentes de proposito. A cerca de ESCRITA
        # e estreita: e ela que impede Iris e Theo de colidirem nos mesmos
        # arquivos. A de LEITURA e larga, porque propor mudanca em `pages/` sem
        # poder abrir `components/` e impossivel: as paginas importam de la.
        # Com uma cerca so, o designer procurava um componente que existe,
        # recebia "nenhuma ocorrencia" e repetia a busca ate saturar o contexto.
        cerca_de_escrita = Cerca(raiz, diretorios)
        cerca_de_leitura = Cerca(raiz, diretorios_de_leitura or diretorios)
        self.permitir_escrita = permitir_escrita
        self.ferramentas: list[BaseTool] = [
            ListarArquivosDeUI(cerca_de_leitura),
            LerArquivo(cerca_de_leitura),
            BuscarNoCodigo(cerca_de_leitura),
        ]
        self.escrever: EscreverArquivo | None = None
        if permitir_escrita:
            self.escrever = EscreverArquivo(cerca_de_escrita)
            self.ferramentas.append(self.escrever)

    def arquivos_tocados(self) -> list[str]:
        if self.escrever is None:
            return []
        return [r["arquivo"] for r in self.escrever.arquivos_tocados()]

    def limpar_registro(self) -> None:
        if self.escrever is not None:
            self.escrever.limpar_registro()


def ferramentas_de_codigo(
    raiz: Path | None,
    diretorios: list[str],
    permitir_escrita: bool = True,
    diretorios_de_leitura: list[str] | None = None,
) -> KitDeCodigo | None:
    """Monta um kit cercado para um designer.

    Devolve None quando nao ha repositorio ou cerca definida - o designer entao
    trabalha sem ver o codigo, que e um caminho legitimo e nao um erro.
    """
    if not raiz or not diretorios:
        return None
    return KitDeCodigo(raiz, diretorios, permitir_escrita, diretorios_de_leitura)
