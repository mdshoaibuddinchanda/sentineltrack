import queue
import threading
from typing import Optional, Any


class BoundedStreamQueue:
    """
    Thread-safe bounded queue for live stream ingestion.
    Implements a 'latest-frame' drop policy when capacity is reached:
    drops oldest analytical frames to eliminate lagging queues while tracking drop metrics.
    """

    def __init__(self, maxsize: int = 30):
        self.maxsize = maxsize
        self._queue = queue.Queue(maxsize=maxsize)
        self._lock = threading.Lock()
        self.total_enqueued = 0
        self.total_dequeued = 0
        self.total_dropped = 0

    def put_latest(self, item: Any) -> bool:
        """
        Enqueues an item. If queue is full, drops the oldest frame and enqueues the new item.
        """
        with self._lock:
            self.total_enqueued += 1
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                    self.total_dropped += 1
                except queue.Empty:
                    pass
            try:
                self._queue.put_nowait(item)
                return True
            except queue.Full:
                self.total_dropped += 1
                return False

    def get(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        item = self._queue.get(block=block, timeout=timeout)
        with self._lock:
            self.total_dequeued += 1
        return item

    def qsize(self) -> int:
        return self._queue.qsize()

    def get_metrics(self) -> dict:
        with self._lock:
            return {
                'qsize': self._queue.qsize(),
                'maxsize': self.maxsize,
                'total_enqueued': self.total_enqueued,
                'total_dequeued': self.total_dequeued,
                'total_dropped': self.total_dropped,
                'drop_rate': round(self.total_dropped / max(self.total_enqueued, 1), 4)
            }
