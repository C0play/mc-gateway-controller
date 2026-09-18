import inspect
import queue
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from logger import logger
from models import TaskInfo


@dataclass
class Worker:
    function: Callable
    kwargs: dict

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        kwargs = {**self.kwargs}
        for name, value in kwds.items():
            if name not in inspect.signature(self.function).parameters:
                continue
            kwargs[name] = value

        return self.function(**kwargs)


@dataclass
class Callback(Worker):
    def __call__(self, info: TaskInfo) -> Any:
        return super().__call__(info=info)


@dataclass
class Task:
    worker: Worker
    callback: Callback
    info: TaskInfo


class TaskManager:
    def __init__(self) -> None:

        self.queue: queue.Queue[Task] = queue.Queue()

    def start(self):
        logger.info("Starting task manager.")
        threading.Thread(target=self.__execute_tasks, daemon=True).start()

    def stop(self):
        logger.info("Stopping task manager.")
        self.queue.shutdown()

    def push(
        self,
        worker: Worker,
        callback: Callback,
        container_name: str,
        job_name: str,
    ) -> TaskInfo:
        id = uuid.uuid7()

        info = TaskInfo(
            status="processing",
            id=str(id),
            container_name=container_name,
            job=job_name,
            created_time=datetime.now(UTC),
            completed_time=None,
        )
        try:
            self.queue.put(
                Task(worker, callback, info),
                block=False,
            )
        except (queue.Full, queue.ShutDown):
            status = "rejected"
        else:
            status = "processing"
        info.status = status

        logger.debug(f"Queued task {job_name} ({id}) for {container_name}")
        return info

    def pop(self) -> Task | None:
        try:
            return self.queue.get()
        except (queue.Empty, queue.ShutDown):
            return None

    def __execute_tasks(self):
        while not self.queue.is_shutdown or not self.queue.empty():
            logger.debug(f"Queue is empty '{self.queue.empty()}'")
            if task := self.pop():
                logger.debug(f"Executing task '{task.info.id}'")
                try:
                    task.worker()
                except Exception:
                    logger.exception(f"Task {task.info.job} failed")
                    task.info.status = "failed"
                else:
                    task.info.status = "completed"

                task.info.completed_time = datetime.now(UTC)
                task.callback(info=task.info)

        logger.info("Stopped task manager.")
