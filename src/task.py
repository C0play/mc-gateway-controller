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

        self.function(**kwargs)


@dataclass
class Callback(Worker):
    def __call__(self, task_id: uuid.UUID, created_time: datetime) -> Any:
        return super().__call__(task_id=task_id, created_time=created_time)


@dataclass
class Task:
    task: Worker
    callback: Callback
    id: uuid.UUID
    created_time: datetime


class TaskManager:
    def __init__(self) -> None:

        self.queue: queue.Queue[Task] = queue.Queue()

    def start(self):
        logger.info("Starting task manager.")
        threading.Thread(target=self.__execute_tasks, daemon=True).start()

    def stop(self):
        logger.info("Stopping task manager.")
        self.queue.shutdown()

    def push(self, task: Worker, callback: Callback) -> TaskInfo:
        id = uuid.uuid7()
        created_time = datetime.now(UTC)
        try:
            self.queue.put(
                Task(task, callback, id, created_time),
                block=False,
            )
        except (queue.Full, queue.ShutDown):
            status = "rejected"
        else:
            status = "processing"

        return TaskInfo(
            status=status,
            id=id,
            created_time=created_time,
            completed_time=None,
        )

    def pop(self) -> Task | None:
        try:
            return self.queue.get()
        except (queue.Empty, queue.ShutDown):
            return None

    def __execute_tasks(self):
        while not self.queue.is_shutdown or not self.queue.empty():
            logger.debug(f"Queue is empty '{self.queue.empty()}'")
            if t := self.pop():
                logger.debug(f"Executing task '{t.id}'")
                t.task()
                t.callback(t.id, t.created_time)

        logger.info("Stopped task manager.")
