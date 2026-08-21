"""Serve the interactive 3D lifting report and stream its trained splats.

The 100+ MB Gaussian PLY files stay in the machine-local benchmark output;
this server exposes them to the otherwise static report without copying them
into git.
"""

from __future__ import annotations

import argparse
import mimetypes
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


REPO = Path(__file__).resolve().parents[2]
SPLAT_ROUTE = re.compile(
    r"^/benchmarks/lifting/reports/scene3d/splat/(ai_\d{3}_\d{3})\.ply$")
ARTIFACT_PREFIX = "/benchmark-artifacts/"
ACTIVE_ROUTE = re.compile(r"^/active-artifacts/(ai_\d{3}_\d{3})/(.+)$")
ARTIFACT_SUFFIXES = {
    ".csv", ".html", ".json", ".jsonl", ".jpg", ".jpeg", ".npy",
    ".npz", ".png", ".txt",
}


class Handler(SimpleHTTPRequestHandler):
    benchmark_root: Path
    active_root: Path

    def do_GET(self) -> None:
        route = unquote(urlparse(self.path).path)
        match = SPLAT_ROUTE.fullmatch(route)
        if match:
            return self._serve_splat(match.group(1))
        if route.startswith(ARTIFACT_PREFIX):
            return self._serve_artifact(route.removeprefix(ARTIFACT_PREFIX))
        active_match = ACTIVE_ROUTE.fullmatch(route)
        if active_match:
            return self._serve_active_artifact(
                active_match.group(1), active_match.group(2))
        super().do_GET()

    def _serve_artifact(self, relative_path: str) -> None:
        """Serve a safe, browser-readable artifact from the benchmark output."""
        path = (self.benchmark_root / relative_path).resolve()
        return self._serve_browser_file(path, self.benchmark_root)

    def _serve_active_artifact(self, scene_id: str, relative_path: str) -> None:
        root = (self.active_root / f"hypersim_{scene_id}_active").resolve()
        path = (root / relative_path).resolve()
        return self._serve_browser_file(path, root)

    def _serve_browser_file(self, path: Path, allowed_root: Path) -> None:
        try:
            path.relative_to(allowed_root)
        except ValueError:
            self.send_error(403, "Artifact path escapes the benchmark root")
            return
        if path.suffix.lower() not in ARTIFACT_SUFFIXES:
            self.send_error(403, "Artifact type is not browser-readable")
            return
        if not path.is_file():
            self.send_error(404, "Benchmark artifact not found")
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Cache-Control", "max-age=60")
        self.end_headers()
        try:
            with path.open("rb") as stream:
                while chunk := stream.read(1 << 20):
                    self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

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
    Handler.active_root = Handler.benchmark_root.parents[1]
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port), partial(Handler, directory=str(REPO)))
    base = f"http://127.0.0.1:{args.port}/benchmarks/lifting/reports/"
    print(f"Serving 3D viewer: {base}scene3d/", flush=True)
    print(f"Serving walkthrough: {base}pipeline_walkthrough/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
