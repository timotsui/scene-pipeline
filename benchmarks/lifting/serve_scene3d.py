"""Serve the interactive 3D lifting report and stream its trained splats.

The 100+ MB Gaussian PLY files stay in the machine-local benchmark output;
this server exposes them to the otherwise static report without copying them
into git.
"""

from __future__ import annotations

import argparse
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


REPO = Path(__file__).resolve().parents[2]
SPLAT_ROUTE = re.compile(
    r"^/benchmarks/lifting/reports/scene3d/splat/(ai_\d{3}_\d{3})\.ply$")


class Handler(SimpleHTTPRequestHandler):
    benchmark_root: Path

    def do_GET(self) -> None:
        route = unquote(urlparse(self.path).path)
        match = SPLAT_ROUTE.fullmatch(route)
        if match:
            return self._serve_splat(match.group(1))
        super().do_GET()

    def _serve_splat(self, scene_id: str) -> None:
        path = (self.benchmark_root / "training" /
                f"{scene_id}_gsplat5000" / "ply" / "point_cloud_4999.ply")
        if not path.is_file():
            self.send_error(404, f"No trained splat for {scene_id}")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Cache-Control", "max-age=300")
        self.end_headers()
        try:
            with path.open("rb") as stream:
                while chunk := stream.read(1 << 20):
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    Handler.benchmark_root = args.benchmark_root.resolve()
    if not Handler.benchmark_root.is_dir():
        parser.error(f"benchmark root does not exist: {Handler.benchmark_root}")
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port), partial(Handler, directory=str(REPO)))
    url = (f"http://127.0.0.1:{args.port}/benchmarks/lifting/reports/"
           "scene3d/")
    print(f"Serving {url}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
