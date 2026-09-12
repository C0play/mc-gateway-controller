from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import APIKeyHeader

from container import Container
from logger import logger
from models import ContainerConfig, StatusType, TaskInfo
from task import Callback, TaskManager, Worker


class API:
    def __init__(self, api_key: str | None, manager: TaskManager) -> None:

        self.manager = manager

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

        @self.app.post(
            path="/container/create",
            dependencies=[Depends(self.authenticator)],
            response_model=TaskInfo,
            status_code=202,
        )
        def create_container(config: ContainerConfig, response: Response):
            info = self.manager.push(
                Worker(
                    Container.deploy,
                    {"config": config},
                ),
                Callback(
                    logger.info,
                    {
                        "msg": f"Completed deployment of {Container.CONTAINER_NAME_T % config.mc_port}"
                    },
                ),
            )
            response.status_code = API.__get_status_code(info.status)
            return info

        @self.app.post(
            path="/container/start/{port}",
            dependencies=[Depends(self.authenticator)],
            response_model=TaskInfo,
            status_code=202,
        )
        def container_start(port: int, response: Response):
            info = self.manager.push(
                Worker(
                    Container.start,
                    {"mc_port": port},
                ),
                Callback(
                    logger.info,
                    {
                        "msg": f"Completed deployment of {Container.CONTAINER_NAME_T % port}"
                    },
                ),
            )
            response.status_code = API.__get_status_code(info.status)
            return info

        @self.app.post(
            path="/container/stop/{port}",
            dependencies=[Depends(self.authenticator)],
            response_model=TaskInfo,
            status_code=202,
        )
        def container_stop(port: int, response: Response):
            info = self.manager.push(
                Worker(
                    Container.stop,
                    {"mc_port": port},
                ),
                Callback(
                    logger.info,
                    {
                        "msg": f"Completed deployment of {Container.CONTAINER_NAME_T % port}"
                    },
                ),
            )
            response.status_code = API.__get_status_code(info.status)
            return info

    @property
    def authenticator(self):
        def _authenticate(api_key: Annotated[str | None, Depends(self.api_key_header)]):
            if self.api_key is not None and api_key != self.api_key:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED)

        return _authenticate

    @staticmethod
    def __get_status_code(s: StatusType) -> int:
        match s:
            case "rejected":
                return status.HTTP_429_TOO_MANY_REQUESTS
            case "processing":
                return status.HTTP_202_ACCEPTED
            case "completed":
                return status.HTTP_200_OK
