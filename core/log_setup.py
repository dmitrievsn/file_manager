import logging
from pathlib import Path


def setup_logging() -> None:
    logs_dir = Path.cwd() / "logs"
    logs_dir.mkdir(exist_ok=True)

    log_file = logs_dir / "app.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )
