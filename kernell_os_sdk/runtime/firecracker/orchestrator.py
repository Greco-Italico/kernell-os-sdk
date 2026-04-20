import time
import threading
from concurrent.futures import Future
from typing import Dict, Tuple

from ..models import ExecutionRequest, ExecutionResult
from .scheduler import Scheduler
from ..base import BaseRuntime

class RuntimeOrchestrator:
    def __init__(self, runtime: BaseRuntime, num_workers: int = 10):
        self.runtime = runtime
        self.scheduler = Scheduler()
        self.num_workers = num_workers
        self.running = True
        self.futures: Dict[str, Future] = {}
        self.lock = threading.Lock()
        
        self.workers = []
        for _ in range(num_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True)
            t.start()
            self.workers.append(t)

    def submit(self, request: ExecutionRequest, request_id: str) -> Future:
        future = Future()
        with self.lock:
            self.futures[request_id] = future
        
        # Attach the request ID to the request object dynamically for tracing
        request._internal_id = request_id
        
        self.scheduler.submit(request)
        return future

    def _worker_loop(self):
        while self.running:
            req = self.scheduler.next()
            
            if not req:
                time.sleep(0.005) # 5ms backoff if queue is empty
                continue
                
            req_id = getattr(req, "_internal_id", None)
            
            try:
                # 1. Execute via the underlying FirecrackerRuntime (which applies Admission Control)
                result = self.runtime.execute(req)
                
                if req_id:
                    with self.lock:
                        if req_id in self.futures:
                            self.futures[req_id].set_result(result)
                            del self.futures[req_id]
            except Exception as e:
                if req_id:
                    with self.lock:
                        if req_id in self.futures:
                            self.futures[req_id].set_exception(e)
                            del self.futures[req_id]

    def shutdown(self):
        self.running = False
        for w in self.workers:
            w.join(timeout=1.0)
