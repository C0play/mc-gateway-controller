import os
from typing import Any, ClassVar

import yaml
from fastapi import HTTPException, status
from python_on_whales import DockerClient
from python_on_whales.exceptions import DockerException, NoSuchContainer, NoSuchVolume

from logger import logger
from models import ContainerConfig, ContainerStatus


class Container:
    CONTAINERS_DIR = "/app/containers"
    COMPOSE_FILENAME_T = "%d_compose.yml"
    CONTAINER_NAME_T = "mc_%d"

    starting: ClassVar[set[str]] = set()
    stopping: ClassVar[set[str]] = set()

    @classmethod
    def status(cls, mc_port: int) -> ContainerStatus:
        """Checks the status of a container."""
        name = Container.CONTAINER_NAME_T % mc_port
        if name in Container.starting:
            return "starting"
        if name in Container.stopping:
            return "stopping"

        return "online" if Container.__is_online(mc_port) else "offline"

    @classmethod
    def deploy(cls, config: ContainerConfig):
        """In the /containers directory creates a {config.mc_port}_compose.yml file."""

        path = cls.__path(config.mc_port)
        try:
            if Container.__is_online(config.mc_port):
                cls.stop(config.mc_port)

            logger.info(f"Writing compose file to {path}")
            with open(path, "w") as file:
                yaml.dump(
                    cls.__generate_yaml(config),
                    file,
                    default_flow_style=False,
                    sort_keys=False,
                )
        except OSError as e:
            logger.error(f"Failed to write file {path}: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)

    @classmethod
    def start(cls, mc_port: int):
        """Starts the container."""

        path = cls.__path(mc_port)
        if not os.path.exists(path):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"file {path} does not exist"
            )

        name = Container.CONTAINER_NAME_T % mc_port
        logger.info(f"Starting container {name}")

        cls.starting.add(name)
        try:
            DockerClient(compose_files=[path]).compose.up(
                quiet=True, wait=True, detach=True
            )
        except DockerException as e:
            logger.error(f"Command {e.docker_command} exited with {e.return_code}: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            cls.starting.remove(name)

    @classmethod
    def stop(cls, mc_port: int):
        """Stops the container."""

        path = cls.__path(mc_port)
        if not os.path.exists(path):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"file {path} does not exist"
            )

        name = Container.CONTAINER_NAME_T % mc_port
        logger.info(f"Stopping container {name}")

        cls.stopping.add(name)
        try:
            DockerClient(compose_files=[path]).compose.down(quiet=True)
        except NoSuchContainer as _:
            msg = f"Container {name} is not up."
            logger.info(msg)
            raise HTTPException(status.HTTP_404_NOT_FOUND, msg)
        except DockerException as e:
            logger.error(f"Command {e.docker_command} exited with {e.return_code}: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            cls.stopping.remove(name)

    @classmethod
    def delete(cls, mc_port: int):
        path = cls.__path(mc_port)
        container_name = Container.CONTAINER_NAME_T % mc_port
        logger.info(f"Deleting container {container_name}")

        if os.path.exists(path):
            if Container.__is_online(mc_port):
                cls.stop(mc_port)
            os.remove(path)

        try:
            volume_name = f"mc_{mc_port}_data"
            docker = DockerClient()

            if docker.container.list(filters={"name": container_name}):
                docker.container.remove(container_name)

            if docker.volume.list(filters={"name": volume_name}):
                docker.volume.remove(volume_name)

        except (NoSuchContainer, NoSuchVolume):
            logger.info(f"Container {container_name} does not exist.")
        except DockerException as e:
            logger.exception(
                f"Command {e.docker_command} exited with code {e.return_code}"
            )
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)

    @classmethod
    def __is_online(cls, mc_port: int) -> bool:
        """Checks if the container is online."""

        name = Container.CONTAINER_NAME_T % mc_port
        try:
            return bool(DockerClient().ps(filters={"name": name}))
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

    @classmethod
    def __path(cls, mc_port: int) -> str:
        return os.path.join(
            cls.CONTAINERS_DIR,
            cls.COMPOSE_FILENAME_T % mc_port,
        )
