import os
import threading
from collections.abc import Callable
from typing import Any

import yaml
from fastapi import HTTPException, status
from python_on_whales import DockerClient
from python_on_whales.exceptions import DockerException, NoSuchContainer

from logger import logger
from models import ContainerConfig


class Controller:
    CONTAINERS_DIR = "/app/containers"
    COMPOSE_FILENAME_T = "%d_compose.yml"
    CONTAINER_NAME_T = "mc_%d"

    @classmethod
    def deploy(cls, config: ContainerConfig) -> str:
        """In the /containers directory creates a {config.mc_port}_compose.yml file."""

        path = os.path.join(
            Controller.CONTAINERS_DIR, Controller.COMPOSE_FILENAME_T % config.mc_port
        )

        def _write_file():
            logger.info(f"Writing compose file to {path}")
            with open(path, "w") as file:
                yaml.dump(
                    cls.__generate_yaml(config),
                    file,
                    default_flow_style=False,
                    sort_keys=False,
                )

        def _stop_and_write():
            cls.stop(config.mc_port, wait=True)
            _write_file()

        try:
            if Controller.is_online(config.mc_port):
                Controller.run_task(
                    task=_stop_and_write,
                    on_complete=lambda: logger.info(
                        f"Completed deployment of {Controller.CONTAINER_NAME_T % config.mc_port}"
                    ),
                )
                return "processing"

            _write_file()
            return "completed"
        except OSError as e:
            logger.error(f"Failed to write file {path}: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)

    @classmethod
    def start(cls, mc_port: int, wait: bool = False) -> str:
        """Starts the container."""

        path = os.path.join(
            Controller.CONTAINERS_DIR, Controller.COMPOSE_FILENAME_T % mc_port
        )
        if not os.path.exists(path):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"file {path} does not exist"
            )

        logger.info(f"Starting container {Controller.CONTAINER_NAME_T % mc_port}")

        try:
            docker = DockerClient(compose_files=[path])
            Controller.run_task(
                task=docker.compose.up,
                on_complete=lambda: logger.info(
                    f"Completed docker.compose.up of {Controller.CONTAINER_NAME_T % mc_port}"
                ),
                task_kwargs={"quiet": True, "wait": True, "detach": True},
                wait=wait,
            )
            return "processing"
        except DockerException as e:
            logger.error(f"Command {e.docker_command} exited with {e.return_code}: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)

    @classmethod
    def stop(cls, mc_port: int, wait: bool = False) -> str:
        """Stops the container."""

        path = os.path.join(
            Controller.CONTAINERS_DIR, Controller.COMPOSE_FILENAME_T % mc_port
        )
        if not os.path.exists(path):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"file {path} does not exist"
            )
        logger.info(f"Stopping container {Controller.CONTAINER_NAME_T % mc_port}")

        try:
            docker = DockerClient(compose_files=[path])
            Controller.run_task(
                task=docker.compose.down,
                on_complete=lambda: logger.info(
                    f"Completed docker.compose.down of {Controller.CONTAINER_NAME_T % mc_port}"
                ),
                task_kwargs={"quiet": True},
                wait=wait,
            )
            return "processing"
        except NoSuchContainer as _:
            msg = f"Container {Controller.CONTAINER_NAME_T % mc_port} is not up."
            logger.info(msg)
            raise HTTPException(status.HTTP_404_NOT_FOUND, msg)
        except DockerException as e:
            logger.error(f"Command {e.docker_command} exited with {e.return_code}: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)

    @classmethod
    def is_online(cls, mc_port: int) -> bool:
        """Checks if the container is online."""

        name = Controller.CONTAINER_NAME_T % mc_port
        try:
            docker = DockerClient()

            for container in docker.ps():
                if container.name == name:
                    return True
            return False

        except DockerException as e:
            logger.error(f"Command {e.docker_command} exited with {e.return_code}: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)

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

    @staticmethod
    def run_task(
        task: Callable,
        on_complete: Callable,
        task_kwargs: dict | None = None,
        on_complete_kwargs: dict | None = None,
        wait: bool = False,
    ):
        """Creates and starts a thread that executes the task and then calls the on_complete function."""

        def _wrapper():
            args = {} if task_kwargs is None else task_kwargs
            task(**args)
            args = {} if on_complete_kwargs is None else on_complete_kwargs
            on_complete(**args)

        t = threading.Thread(target=_wrapper)
        t.start()
        if wait:
            t.join()
