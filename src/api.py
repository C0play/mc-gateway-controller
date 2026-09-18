from typing import Annotated

import requests
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import APIKeyHeader

from container import Container
from logger import logger
from models import (
    ContainerConfig,
    StatusResponse,
    TaskInfo,
    TaskStatus,
)
from task import Callback, TaskManager, Worker


class API:
    def __init__(
        self,
        api_key: str | None,
        mc_gateway_url: str,
        manager: TaskManager,
    ) -> None:

        self.manager = manager

        self.mc_gateway_url = mc_gateway_url
        self.api_key = api_key
        self.app = FastAPI(title="mc-gateway-controller")
        self.api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

        self.__register_endpoints()
        self.__register_middleware()

    def run(self, ip: str, port: int):
        self.manager.start()
        logger.info(f"Starting api on {ip}:{port}")
        uvicorn.run(
            self.app,
            host=ip,
            port=port,
            log_config=None,
            access_log=False,
            timeout_graceful_shutdown=120,
        )

    def __register_middleware(self) -> None:

        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            client_ip = request.client.host if request.client else "unknown"
            try:
                response = await call_next(request)
                logger.info(
                    f"API: {client_ip} - [{response.status_code}] {request.method:<7} {request.url.path}"
                )
                return response
            except Exception as e:
                logger.error(f"API: error processing {request.url.path}: {e}")
                raise

    def __register_endpoints(self):

        callback = Callback(self.__callback, {})

        @self.app.get(
            "/container/status/{port}",
            dependencies=[Depends(self.authenticator)],
            response_model=StatusResponse,
        )
        def get_status(port: int):
            return {"status": Container.status(port)}

        @self.app.post(
            path="/container/create",
            dependencies=[Depends(self.authenticator)],
            response_model=TaskInfo,
            status_code=202,
        )
        def create_container(config: ContainerConfig, response: Response):
            name = Container.CONTAINER_NAME_T % config.mc_port
            worker = Worker(Container.deploy, {"config": config})
            info = self.manager.push(worker, callback, name, "create")
            response.status_code = API.__get_status_code(info.status)
            return info

        @self.app.post(
            path="/container/start/{port}",
            dependencies=[Depends(self.authenticator)],
            response_model=TaskInfo,
            status_code=202,
        )
        def container_start(port: int, response: Response):
            name = Container.CONTAINER_NAME_T % port
            worker = Worker(Container.start, {"mc_port": port})
            info = self.manager.push(worker, callback, name, "start")
            response.status_code = API.__get_status_code(info.status)
            return info

        @self.app.post(
            path="/container/stop/{port}",
            dependencies=[Depends(self.authenticator)],
            response_model=TaskInfo,
            status_code=202,
        )
        def container_stop(port: int, response: Response):
            name = Container.CONTAINER_NAME_T % port
            worker = Worker(Container.stop, {"mc_port": port})
            info = self.manager.push(worker, callback, name, "stop")
            response.status_code = API.__get_status_code(info.status)
            return info

        @self.app.delete(
            path="/container/delete/{port}",
            dependencies=[Depends(self.authenticator)],
            response_model=TaskInfo,
            status_code=202,
        )
        def container_delete(port: int, response: Response):
            name = Container.CONTAINER_NAME_T % port
            worker = Worker(Container.delete, {"mc_port": port})
            info = self.manager.push(worker, callback, name, "delete")
            response.status_code = API.__get_status_code(info.status)
            return info

    @property
    def authenticator(self):
        def _authenticate(api_key: Annotated[str | None, Depends(self.api_key_header)]):
            if self.api_key is not None and api_key != self.api_key:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED)

        return _authenticate

    @staticmethod
    def __get_status_code(s: TaskStatus) -> int:
        match s:
            case "rejected":
                return status.HTTP_429_TOO_MANY_REQUESTS
            case "processing":
                return status.HTTP_202_ACCEPTED
            case "completed":
                return status.HTTP_200_OK
            case "failed":
                return status.HTTP_500_INTERNAL_SERVER_ERROR

    def __callback(self, info: TaskInfo):
        logger.info(f"Completed task '{info.job}'")
        requests.post(
            url=f"{self.mc_gateway_url}/system/task/completed",
            json=info.model_dump(mode="json"),
        )
