"""Qt worker primitives; signal delivery returns results to the GUI thread."""

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class TaskSignals(QObject):
    done = Signal(object)
    error = Signal(str)


class Task(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = TaskSignals()

    def run(self):
        try:
            self.signals.done.emit(self.function())
        except Exception as exc:
            self.signals.error.emit(str(exc))


class TaskRunner(QObject):
    """Bound concurrency and retain workers until their queued signal arrives.

    QImage may cross thread boundaries; QPixmap and all widget updates stay on
    the GUI thread. A shared runner prevents each feature spawning its own pool.
    """

    MAX_PENDING = 8

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.tasks: set[Task] = set()

    @property
    def pending(self) -> int:
        return len(self.tasks)

    def submit(
        self,
        function: Callable,
        on_done: Callable,
        on_error: Callable | None = None,
    ) -> bool:
        if self.pending >= self.MAX_PENDING:
            if on_error is not None:
                on_error("后台任务较多，请稍后重试。")
            return False
        task = Task(function)
        self.tasks.add(task)

        def finish(value, failed: bool = False) -> None:
            self.tasks.discard(task)
            if failed:
                if on_error is not None:
                    on_error(value)
                else:
                    logging.warning("Background task failed: %s", value)
            else:
                on_done(value)

        task.signals.done.connect(finish)
        task.signals.error.connect(lambda message: finish(message, True))
        self.pool.start(task)
        return True
