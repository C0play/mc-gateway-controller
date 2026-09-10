import os
from typing import Any

import yaml
from python_on_whales import DockerClient

from logger import logger
from models import ContainerConfig


class Controller:
    CONTAINERS_DIR = "/app/containers"
    COMPOSE_FILENAME_T = "%d_compose.yml"
    CONTAINER_NAME_T = "mc_%d"

    @classmethod
    def deploy(cls, config: ContainerConfig):
        """In the /containers directory creates a {config.mc_port}_compose.yml file."""

        filename = Controller.COMPOSE_FILENAME_T % config.mc_port
        logger.info(f"Deploying config to {filename}")

        with open(os.path.join(Controller.CONTAINERS_DIR, filename), "w") as file:
            yaml.dump(
                cls.__generate_yaml(config),
                file,
                default_flow_style=False,
                sort_keys=False,
            )

    @classmethod
    def start(cls, mc_port: int):
        """Starts the container."""

        path = os.path.join(
            Controller.CONTAINERS_DIR, Controller.COMPOSE_FILENAME_T % mc_port
        )
        container_name = Controller.CONTAINER_NAME_T % mc_port
        docker = DockerClient(compose_files=[path])

        logger.info(f"Starting container {container_name}")

        docker.compose.up(
            detach=True,
            quiet=True,
        )

    @classmethod
    def stop(cls, mc_port: int):
        """Stops the container."""

        path = os.path.join(
            Controller.CONTAINERS_DIR, Controller.COMPOSE_FILENAME_T % mc_port
        )
        container_name = Controller.CONTAINER_NAME_T % mc_port
        docker = DockerClient(compose_files=[path])

        logger.info(f"Stopping container {container_name}")
        docker.compose.down(
            quiet=True,
        )

    @classmethod
    def __generate_yaml(cls, config: ContainerConfig) -> dict:
        """Generates a compose.yml file from a pydantic model."""

        environment = {
            "UID": config.uid,
            "GID": config.gid,
            "RCON_PASSWORD": config.rcon_password,
            "EULA": "TRUE",
            "TYPE": config.type,
            "INIT_MEMORY": config.init_memory,
            "MAX_MEMORY": config.max_memory,
            "TZ": str(config.timezone),
            "VIEW_DISTANCE": str(config.view_distance),
            "VERSION": config.version,
            "MODRINTH_ALLOWED_VERSION_TYPE": config.mod_version_type,
            "PAUSE_WHEN_EMPTY_SECONDS": "300",
            "PLAYER_IDLE_TIMEOUT": "10",
            "ENABLE_ROLLING_LOGS": "true",
            "LOG_TIMESTAMP": "true",
        }
        if config.modrinth_projects:
            environment["MODRINTH_PROJECTS"] = ",".join(config.modrinth_projects)
        if config.custom_server_properties:
            environment["CUSTOM_SERVER_PROPERTIES"] = ",".join(
                config.custom_server_properties
            )

        compose_content: dict[str, Any] = {
            "services": {
                "mc": {
                    "image": "itzg/minecraft-server:latest",
                    "container_name": f"mc_{config.mc_port}",
                    "cpu_count": config.cpu_count,
                    "tty": True,
                    "stdin_open": True,
                    "stop_grace_period": "60s",
                    "ports": [
                        f"{config.mc_port}:25565",
                        f"{config.rcon_port}:25575",
                    ],
                    "environment": environment,
                    "volumes": [f"mc_{config.mc_port}_data:/data"],
                }
            },
            "volumes": {
                f"mc_{config.mc_port}_data": {"name": f"mc_{config.mc_port}_data"}
            },
        }

        return compose_content
