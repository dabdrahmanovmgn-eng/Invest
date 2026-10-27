"""Локальный просмотр site/ без доступа из сети и без внешних зависимостей."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import socket


class LocalServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8341)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parents[1] / "site"
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = LocalServer(("127.0.0.1", args.port), handler)
    print(f"Dengi Market: http://127.0.0.1:{args.port}/", flush=True)
    print("Остановка: Ctrl+C", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
