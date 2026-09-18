import os
import signal

from api import API
from logger import logger
from task import TaskManager

if __name__ == "__main__":
    api_key = os.getenv("API_KEY")
    if not api_key:
        logger.warning("Environment variable API_KEY is empty. Accepting any request.")

    mc_gateway_url = os.getenv("MC-GATEWAY-URL")
    if not mc_gateway_url:
        raise RuntimeError("Environment variable MC-GATEWAY-URL is empty.")

    manager = TaskManager()
    api = API(api_key, mc_gateway_url, manager)

    def _signal_handler(signum, _):
        logger.info(f"Received {signum}. Shutting down.")
        manager.stop()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    ip = "0.0.0.0"
    port = 6521
    api.run(ip, port)
