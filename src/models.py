from datetime import datetime
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic_extra_types.timezone_name import TimeZoneName

ReleaseType: TypeAlias = Literal["release", "beta", "alpha"]


class ContainerConfig(BaseModel):
    # Environment
    uid: int = Field(1000, description="User id to run the container as.")
    gid: int = Field(1000, description="Group id to run the container as.")
    timezone: TimeZoneName = Field(..., description="Container timezone.")
    # Resources
    init_memory: str = Field(
        "2G",
        description="The amount of memory to allocate on start (e.g., '2G', '4G').",
    )
    max_memory: str = Field(
        "2G", description="The maximum amount of memory to allocate (e.g., '2G', '4G')."
    )
    cpu_count: int = Field(..., description="Number of CPU cores for the container.")
    # Ports
    mc_port: int = Field(..., description="Port used for minecraft client connections.")
    rcon_port: int = Field(..., description="Port used for RCON connections.")
    # Minecraft
    type: str = Field("FABRIC", description="Server type (e.g. FABRIC, VANILLA, ...)")
    version: str = Field("LATEST", description="Minecraft version to use.")
    view_distance: int = Field(10, ge=1, le=32, description="Server view distance.")
    mod_version_type: ReleaseType = Field(
        "release", description="Allowed mod release type for Modrinth projects."
    )
    modrinth_projects: list[str] = Field(
        [],
        description="List of Modrinth mod URLs or IDs to install.",
    )
    rcon_password: str = Field(description="RCON password used by the gateway.")
    # Server
    custom_server_properties: list = Field([], description="List of custom properties.")


StatusType = Literal["rejected", "processing", "completed"]


class TaskInfo(BaseModel):
    status: StatusType = Field(description="Task status.")
    id: UUID = Field(description="Task identifier.")
    created_time: datetime = Field(description="Time when the task was submitted")
    completed_time: datetime | None = Field(
        None, description="Time when the task was completed"
    )
