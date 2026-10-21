"""Launch the local app and its separate durable worker."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import threading
import webbrowser

from .config import DEFAULT_PORT, default_data_dir


def event_loop():
    # This service does not use asyncio subprocesses. Selector avoids Windows
    # socket-close errors when browsers abort an HTTP connection during download.
    return asyncio.SelectorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open your local Visual Learning workspace.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-worker", action="store_true", help="Use a worker started separately.")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port from 1024 to 65535.")
    import uvicorn
    from .app import create_app

    url = f"http://127.0.0.1:{args.port}"
    print(f"Visual Learning: {url}")
    print(f"Your saved library: {args.data_dir.resolve()}")
    print("Keep this process running while pages are being generated. Press Ctrl+C to stop.")
    if not args.no_browser:
        timer = threading.Timer(1.5, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    uvicorn.run(create_app(args.data_dir, auto_worker=not args.no_worker), host="127.0.0.1", port=args.port, access_log=False, loop="visual_learning.__main__:event_loop")


if __name__ == "__main__":
    main()
