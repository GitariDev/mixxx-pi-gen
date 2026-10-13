import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Song Dex — local music library cleanup"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Separate local catalog, cache and backups directory",
    )
    parser.add_argument("--port", type=int, default=8765, choices=[8765])
    args = parser.parse_args()
    if args.data_dir:
        os.environ["SONGDEX_DATA"] = str(args.data_dir.resolve())
    import fcntl

    root = (
        Path(
            os.environ.get(
                "SONGDEX_DATA", Path(__file__).resolve().parents[2] / ".data"
            )
        )
        .expanduser()
        .resolve()
    )
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / ".instance.lock").open("w")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error("Another Song Dex instance is already using this data directory")
    import uvicorn

    from .api import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
