"""Entry point for the background worker: ``python -m app.workers.runner``."""

import logging

from app.core.logging import configure_logging
from app.services.job_service import poll_forever


def main() -> None:
    configure_logging()
    logging.getLogger("nexus.worker").info("worker process starting")
    poll_forever()


if __name__ == "__main__":
    main()
