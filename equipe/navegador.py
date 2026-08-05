"""Ferramentas de navegador para Lila e Rui.

Cada persona recebe a SUA propria sessao de navegador, com login proprio. E isso
que permite que as duas interajam de verdade dentro do app: a Lila publica, o Rui
ve o post dela no feed dele e comenta.

O Playwright e opcional. Sem ele instalado, `sessoes_de_navegador` devolve None e
as personas caem em modo simulacao, que e um caminho legitimo.

    pip install playwright && playwright install chromium
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

ESPERA_PADRAO = 10_000
"""ms. Tempo maximo esperando um elemento aparecer."""

LIMITE_DE_TEXTO = 4_000


def playwright_disponivel() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass
class Credencial:
    email: str
    senha: str


@dataclass
class RotaDeLogin:
    """Como fazer login no app alvo. Ajuste por projeto, nao por persona."""

    caminho: str = "/login"
    campo_email: str = "email"
    campo_senha: str = "senha"
    botao: str = "Entrar"
    rota_apos_login: str = "/"


class Navegador:
    """Um unico Chromium, compartilhado por todas as personas.

    Existe por necessidade tecnica: `sync_playwright().start()` nao pode ser
    chamado duas vezes no mesmo processo - a segunda chamada morre com
    'Sync API inside the asyncio loop'. Uma instancia, varios contextos.

    Contexto do Playwright ja isola cookies e storage, entao cada persona tem a
    sua sessao de login de verdade, que e o que precisamos.
    """

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self._playwright: Any = None
        self._browser: Any = None

    def _garantir(self) -> Any:
        if self._browser is None:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
            # PLAYWRIGHT_EXECUTABLE_PATH permite usar um Chromium ja instalado,
            # em vez de exigir que a versao do pacote pip bata com a do binario.
            opcoes: dict[str, Any] = {"headless": self.headless}
            executavel = os.getenv("PLAYWRIGHT_EXECUTABLE_PATH")
            if executavel:
                opcoes["executable_path"] = executavel
            self._browser = self._playwright.chromium.launch(**opcoes)
        return self._browser

    def nova_pagina(self, nome: str) -> Any:
        contexto = self._garantir().new_context(
            viewport={"width": 390, "height": 844},  # celular: e assim que se usa
            user_agent=f"persona-{nome}",
        )
        pagina = contexto.new_page()
        pagina.set_default_timeout(ESPERA_PADRAO)
        return pagina

    def fechar(self) -> None:
        for alvo, metodo in ((self._browser, "close"), (self._playwright, "stop")):
            if alvo is not None:
                try:
                    getattr(alvo, metodo)()
                except Exception:
                    pass
        self._browser = self._playwright = None


class SessaoDeNavegador:
    """A sessao de uma persona: contexto proprio, login proprio."""

    def __init__(
        self,
        nome: str,
        url_base: str,
        credencial: Credencial,
        rota: RotaDeLogin | None = None,
        navegador: Navegador | None = None,
    ) -> None:
        self.nome = nome
        self.url_base = url_base.rstrip("/")
        self.credencial = credencial
        self.rota = rota or RotaDeLogin()
        self.navegador = navegador or Navegador()
        self._pagina: Any = None
        self.logada = False

    # --- ciclo de vida ------------------------------------------------------

    def pagina(self) -> Any:
        if self._pagina is None:
            self._pagina = self.navegador.nova_pagina(self.nome)
        return self._pagina

    def fechar(self) -> None:
        if self._pagina is not None:
            try:
                self._pagina.context.close()
            except Exception:
                pass
        self._pagina = None
        self.logada = False

    # --- login --------------------------------------------------------------

    def entrar(self) -> str:
        """Faz login. Idempotente: chamar de novo nao faz nada."""
        if self.logada:
            return f"{self.nome} ja esta logada."
        pagina = self.pagina()
        try:
            pagina.goto(f"{self.url_base}{self.rota.caminho}", wait_until="domcontentloaded")
            self._preencher(pagina, self.rota.campo_email, self.credencial.email)
            self._preencher(pagina, self.rota.campo_senha, self.credencial.senha)
            pagina.get_by_role("button", name=self.rota.botao).click()
            pagina.wait_for_load_state("networkidle", timeout=ESPERA_PADRAO)
        except Exception as erro:
            return f"FALHA no login de {self.nome}: {type(erro).__name__}: {erro}"
        self.logada = True
        return f"{self.nome} entrou como {self.credencial.email}. Agora em {pagina.url}"

    @staticmethod
    def _preencher(pagina: Any, campo: str, valor: str) -> None:
        """Tenta label, placeholder e name - apps variam."""
        tentativas = (
            lambda: pagina.get_by_label(campo, exact=False),
            lambda: pagina.get_by_placeholder(campo),
            lambda: pagina.locator(f"input[name='{campo}']"),
            lambda: pagina.locator(f"input[type='{campo}']"),
        )
        for tentativa in tentativas:
            try:
                alvo = tentativa()
                if alvo.count() > 0:
                    alvo.first.fill(valor)
                    return
            except Exception:
                continue
        raise RuntimeError(f"campo '{campo}' nao encontrado na tela")

    # --- leitura da tela ----------------------------------------------------

    def descrever(self) -> str:
        """O que a persona esta vendo agora, em texto."""
        pagina = self.pagina()
        partes = [f"URL: {pagina.url}", f"Titulo: {pagina.title()}"]

        def coletar(seletor: str, rotulo: str, limite: int = 25) -> None:
            try:
                itens = pagina.locator(seletor)
                textos = []
                for i in range(min(itens.count(), limite)):
                    texto = (itens.nth(i).inner_text() or "").strip().replace("\n", " ")
                    if texto:
                        textos.append(texto[:80])
                if textos:
                    partes.append(f"{rotulo}: " + " | ".join(textos))
            except Exception:
                pass

        coletar("h1, h2, h3", "Titulos")
        coletar("button, [role=button]", "Botoes")
        coletar("a[href]", "Links")
        try:
            campos = pagina.locator("input, textarea")
            descricoes = []
            for i in range(min(campos.count(), 15)):
                campo = campos.nth(i)
                marca = (
                    campo.get_attribute("placeholder")
                    or campo.get_attribute("name")
                    or campo.get_attribute("type")
                    or "campo"
                )
                descricoes.append(marca)
            if descricoes:
                partes.append("Campos: " + " | ".join(descricoes))
        except Exception:
            pass

        try:
            corpo = (pagina.locator("body").inner_text() or "").strip()
            partes.append("Texto visivel:\n" + corpo[:LIMITE_DE_TEXTO])
        except Exception:
            pass
        return "\n".join(partes)


# --- ferramentas ------------------------------------------------------------


class _ComSessao(BaseTool):
    _sessao: SessaoDeNavegador = PrivateAttr()

    def __init__(self, sessao: SessaoDeNavegador, **kw: Any) -> None:
        super().__init__(**kw)
        self._sessao = sessao

    def _garantir_login(self) -> str | None:
        if not self._sessao.logada:
            resultado = self._sessao.entrar()
            if resultado.startswith("FALHA"):
                return resultado
        return None


class _ArgsAbrir(BaseModel):
    caminho: str = Field(default="/", description="Caminho dentro do app, ex: '/create' ou '/profile'")


class AbrirPagina(_ComSessao):
    name: str = "abrir_pagina"
    description: str = (
        "Navega para uma tela do app e descreve o que aparece. Faz login sozinha na "
        "primeira vez. Use '/' para o feed."
    )
    args_schema: Type[BaseModel] = _ArgsAbrir

    def _run(self, caminho: str = "/") -> str:
        erro = self._garantir_login()
        if erro:
            return erro
        pagina = self._sessao.pagina()
        try:
            pagina.goto(f"{self._sessao.url_base}{caminho}", wait_until="networkidle")
        except Exception as e:
            return f"Nao consegui abrir {caminho}: {type(e).__name__}: {e}"
        return self._sessao.descrever()


class _SemArgs(BaseModel):
    pass


class VerTela(_ComSessao):
    name: str = "ver_tela"
    description: str = "Descreve o que esta visivel na tela atual, sem navegar para lugar nenhum."
    args_schema: Type[BaseModel] = _SemArgs

    def _run(self) -> str:
        erro = self._garantir_login()
        return erro or self._sessao.descrever()


class _ArgsClicar(BaseModel):
    alvo: str = Field(description="Texto visivel do botao ou link a clicar")


class Clicar(_ComSessao):
    name: str = "clicar"
    description: str = (
        "Clica em um botao ou link pelo texto visivel, e descreve a tela depois do clique."
    )
    args_schema: Type[BaseModel] = _ArgsClicar

    def _run(self, alvo: str) -> str:
        erro = self._garantir_login()
        if erro:
            return erro
        pagina = self._sessao.pagina()
        tentativas = (
            lambda: pagina.get_by_role("button", name=alvo),
            lambda: pagina.get_by_role("link", name=alvo),
            lambda: pagina.get_by_text(alvo, exact=False),
            lambda: pagina.locator(f"[aria-label='{alvo}']"),
        )
        for tentativa in tentativas:
            try:
                elemento = tentativa()
                if elemento.count() > 0:
                    elemento.first.click(timeout=ESPERA_PADRAO)
                    pagina.wait_for_load_state("networkidle", timeout=ESPERA_PADRAO)
                    return f"Cliquei em '{alvo}'.\n\n{self._sessao.descrever()}"
            except Exception:
                continue
        return (
            f"Nao achei nada clicavel com o texto '{alvo}'. "
            f"Use ver_tela para conferir o que esta disponivel."
        )


class _ArgsPreencher(BaseModel):
    campo: str = Field(description="Label, placeholder ou name do campo")
    valor: str = Field(description="O que digitar")


class Preencher(_ComSessao):
    name: str = "preencher"
    description: str = "Digita um valor em um campo do formulario, identificado por label ou placeholder."
    args_schema: Type[BaseModel] = _ArgsPreencher

    def _run(self, campo: str, valor: str) -> str:
        erro = self._garantir_login()
        if erro:
            return erro
        try:
            self._sessao._preencher(self._sessao.pagina(), campo, valor)
        except Exception as e:
            return f"Nao consegui preencher '{campo}': {e}"
        return f"Preenchi '{campo}'."


class _ArgsRolar(BaseModel):
    direcao: str = Field(default="baixo", description="'baixo' ou 'cima'")


class Rolar(_ComSessao):
    name: str = "rolar"
    description: str = "Rola a tela e descreve o que apareceu. Use para ver mais do feed."
    args_schema: Type[BaseModel] = _ArgsRolar

    def _run(self, direcao: str = "baixo") -> str:
        erro = self._garantir_login()
        if erro:
            return erro
        pagina = self._sessao.pagina()
        delta = 700 if direcao == "baixo" else -700
        try:
            pagina.mouse.wheel(0, delta)
            pagina.wait_for_timeout(600)
        except Exception as e:
            return f"Nao consegui rolar: {e}"
        return self._sessao.descrever()


# --- fabrica ----------------------------------------------------------------


@dataclass
class KitDeNavegador:
    sessao: SessaoDeNavegador
    ferramentas: list[BaseTool] = field(default_factory=list)


@dataclass
class KitsDeNavegador:
    """Os kits das personas mais o navegador que todas compartilham."""

    navegador: Navegador
    por_persona: dict[str, KitDeNavegador]

    def __getitem__(self, nome: str) -> KitDeNavegador:
        return self.por_persona[nome]

    def get(self, nome: str) -> KitDeNavegador | None:
        return self.por_persona.get(nome)

    def fechar(self) -> None:
        for kit in self.por_persona.values():
            kit.sessao.fechar()
        self.navegador.fechar()


def sessoes_de_navegador(
    url_base: str | None,
    credenciais: dict[str, Credencial],
    rota: RotaDeLogin | None = None,
    headless: bool = True,
) -> KitsDeNavegador | None:
    """Um kit por persona, todos sobre o mesmo Chromium.

    None quando nao da para usar navegador - sem app rodando ou sem Playwright
    instalado, as personas caem em modo simulacao.
    """
    if not url_base or not playwright_disponivel():
        return None
    navegador = Navegador(headless=headless)
    kits: dict[str, KitDeNavegador] = {}
    for nome, credencial in credenciais.items():
        sessao = SessaoDeNavegador(nome, url_base, credencial, rota, navegador)
        kits[nome] = KitDeNavegador(
            sessao=sessao,
            ferramentas=[
                AbrirPagina(sessao), VerTela(sessao), Clicar(sessao),
                Preencher(sessao), Rolar(sessao),
            ],
        )
    return KitsDeNavegador(navegador=navegador, por_persona=kits)


CREDENCIAIS_CONNOSR = {
    "Lila": Credencial("alice@example.com", "password123"),
    "Rui": Credencial("bruno@example.com", "password123"),
}
"""Usuarios de seed do ConnoSr, documentados no README do projeto."""

ROTA_CONNOSR = RotaDeLogin(
    caminho="/login",
    campo_email="Email",   # placeholder real em apps/web/src/pages/LoginPage.tsx
    campo_senha="Senha",
    botao="Entrar",
    rota_apos_login="/",
)
