"""Consume the pose appsink independently of the network publisher."""
import sys
import threading
import time


class PoseWorker:
    def __init__(self, sink, Gst, infer, report, print_interval=1.0):
        self.sink = sink
        self.Gst = Gst
        self.infer = infer
        self.report = report
        self.print_interval = print_interval
        self.stopped = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self._run, name='movenet-pose', daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopped.set()

    def join(self, timeout=5):
        self.thread.join(timeout)
        if self.thread.is_alive():
            print('MoveNet has not returned within 5s; exiting with inference worker still pending.', file=sys.stderr)

    def _run(self):
        last_print = float('-inf')
        try:
            while not self.stopped.is_set():
                sample = self.sink.emit('try-pull-sample', self.Gst.SECOND // 5)
                if sample is None:
                    continue
                if self.stopped.is_set():
                    break
                buffer = sample.get_buffer()
                jpeg = buffer.extract_dup(0, buffer.get_size())
                result = self.infer(jpeg)
                now = time.monotonic()
                if not self.stopped.is_set() and now - last_print >= self.print_interval:
                    self.report(result)
                    last_print = now
        except Exception as exc:
            self.error = exc
            print(f'MoveNet stopped: {exc}. Camera streaming continues; restart to restore inference.', file=sys.stderr, flush=True)
