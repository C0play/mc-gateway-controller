import json
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.security import APIKeyHeader

from controller import Controller
from models import ContainerConfig


class API:
    def __init__(self, api_key: str) -> None:

        self.api_key = api_key
        self.app = FastAPI(title="mc-gateway-controller")
        self.api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

        self.__register_endpoints()

    def __register_endpoints(self):

        @self.app.post(
            path="/container/create", dependencies=[Depends(self.authenticator)]
        )
        def create_container(config: ContainerConfig):
            state = Controller.deploy(config)
            return Response(
                json.dumps({"status": state}),
                status.HTTP_202_ACCEPTED,
                media_type="application/json",
            )

        @self.app.post(
            path="/container/start/{port}", dependencies=[Depends(self.authenticator)]
        )
        def container_start(port: int):
            state = Controller.start(port)
            return Response(
                json.dumps({"status": state}),
                status.HTTP_202_ACCEPTED,
                media_type="application/json",
            )

        @self.app.post(
            path="/container/stop/{port}", dependencies=[Depends(self.authenticator)]
        )
        def container_stop(port: int):
            state = Controller.stop(port)
            return Response(
                json.dumps({"status": state}),
                status.HTTP_202_ACCEPTED,
                media_type="application/json",
            )

    @property
    def authenticator(self):
        def _authenticate(api_key: Annotated[str | None, Depends(self.api_key_header)]):
            if api_key != self.api_key:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED)

        return _authenticate
