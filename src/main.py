import os
import signal

import uvicorn

from api import API
from logger import logger


def _signal_handler(signum, _):
    logger.info(f"Received {signum}.")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    ip = "0.0.0.0"
    port = 6521
    api_key = os.getenv("API_KEY")

    if not api_key:
        raise RuntimeError("Environment variable API_KEY is empty.")

    logger.info(f"Starting api on {ip}:{port}")

    api = API(api_key)
    uvicorn.run(api.app, host=ip, port=port, log_config=None, access_log=False)
