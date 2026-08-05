"""Servidor do painel: HTTP + SSE, sem dependencia externa.

Usa apenas a biblioteca padrao de proposito: o painel nao deve arrastar FastAPI,
uvicorn e afins para dentro do projeto so para mostrar seis cartoes na tela.

    servidor = ServidorDoPainel(porta=8777)
    painel = PainelDeMetricas(ao_atualizar=servidor.publicar)
    servidor.iniciar()
"""

from __future__ import annotations

import json
import queue
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ARQUIVO_HTML = Path(__file__).parent / "painel.html"
_LIMITE_DA_FILA = 100


class ServidorDoPainel:
    def __init__(self, porta: int = 8777, host: str = "127.0.0.1") -> None:
        self.porta = porta
        self.host = host
        self._assinantes: list[queue.Queue[str]] = []
        self._lock = threading.Lock()
        self._ultimo: dict[str, Any] = {}
        self._servidor: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # --- ciclo de vida ------------------------------------------------------

    def iniciar(self, abrir_navegador: bool = False) -> str:
        handler = _fabricar_handler(self)
        self._servidor = ThreadingHTTPServer((self.host, self.porta), handler)
        self._servidor.daemon_threads = True
        self.porta = self._servidor.server_address[1]
        self._thread = threading.Thread(
            target=self._servidor.serve_forever, name="painel", daemon=True
        )
        self._thread.start()
        url = self.url
        if abrir_navegador:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        return url

    def parar(self) -> None:
        if self._servidor is not None:
            self._servidor.shutdown()
            self._servidor.server_close()
            self._servidor = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.porta}"

    # --- publicacao ---------------------------------------------------------

    def publicar(self, snapshot: dict[str, Any]) -> None:
        """Callback do PainelDeMetricas. Nunca bloqueia a rodada."""
        dados = json.dumps(snapshot, ensure_ascii=False)
        with self._lock:
            self._ultimo = snapshot
            mortos = []
            for fila in self._assinantes:
                try:
                    fila.put_nowait(dados)
                except queue.Full:
                    mortos.append(fila)
            for fila in mortos:
                self._assinantes.remove(fila)

    def _assinar(self) -> queue.Queue[str]:
        fila: queue.Queue[str] = queue.Queue(maxsize=_LIMITE_DA_FILA)
        with self._lock:
            if self._ultimo:
                fila.put_nowait(json.dumps(self._ultimo, ensure_ascii=False))
            self._assinantes.append(fila)
        return fila

    def _desassinar(self, fila: queue.Queue[str]) -> None:
        with self._lock:
            if fila in self._assinantes:
                self._assinantes.remove(fila)

    def _snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._ultimo


def _fabricar_handler(servidor: ServidorDoPainel):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args) -> None:  # noqa: ANN002 - silencia o log padrao
            pass

        def do_GET(self) -> None:  # noqa: N802 - assinatura da stdlib
            if self.path.startswith("/eventos"):
                self._stream()
            elif self.path.startswith("/estado"):
                self._json(servidor._snapshot())
            elif self.path in ("/", "/index.html"):
                self._html()
            else:
                self.send_error(404)

        def _html(self) -> None:
            corpo = ARQUIVO_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def _json(self, dados: dict[str, Any]) -> None:
            corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def _stream(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            fila = servidor._assinar()
            try:
                while True:
                    try:
                        dados = fila.get(timeout=15)
                        bloco = f"data: {dados}\n\n"
                    except queue.Empty:
                        bloco = ": ping\n\n"  # mantem a conexao viva
                    self.wfile.write(bloco.encode("utf-8"))
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                servidor._desassinar(fila)

    return Handler
