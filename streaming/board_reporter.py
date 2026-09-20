"""Bounded, independent posture and fall delivery; never wait in inference."""
import json
import sys
import threading
from urllib.request import Request, urlopen


def posture_payload(result):
    posture = result['stable_pose']
    return {
        'ts': result['ts'], 'in_camera': result['in_camera'],
        'current_posture': posture if result['in_camera'] and posture in
        ('standing', 'sitting', 'lying') else None,
    }


class BoardReporter:
    def __init__(self, server, port=8000, bed_id='101'):
        self.ws_url = f'ws://{server}:{port}/ws/room/{bed_id}?role=board'
        self.fall_url = f'http://{server}:{port}/api/beds/{bed_id}/possible-fall'
        self.condition = threading.Condition()
        self.stopped = threading.Event()
        self.latest = None
        self.sequence = 0
        self.pending_fall = None
        self.threads = [threading.Thread(target=target, daemon=True, name=name) for target, name in
                        ((self._postures, 'board-posture'), (self._falls, 'board-fall'))]

    def start(self):
        for thread in self.threads:
            thread.start()

    def submit(self, result):
        payload = posture_payload(result)
        with self.condition:
            self.latest = payload
            self.sequence += 1
            if result['fall_detected']:
                self.pending_fall = {'ts': result['ts']}
            self.condition.notify_all()

    def stop(self):
        self.stopped.set()
        with self.condition:
            self.condition.notify_all()
        for thread in self.threads:
            thread.join(timeout=7)

    def _postures(self):
        from websockets.sync.client import connect
        while not self.stopped.is_set():
            try:
                with connect(self.ws_url, open_timeout=3, close_timeout=1,
                             ping_interval=2, ping_timeout=3) as ws:
                    sent = -1
                    while not self.stopped.is_set():
                        with self.condition:
                            self.condition.wait_for(lambda: self.stopped.is_set() or
                                                    self.latest is not None and self.sequence != sent)
                            if self.stopped.is_set():
                                return
                            payload, sequence = self.latest, self.sequence
                        # Board endpoint is one-way: no ready/ACK to wait for.
                        ws.send(json.dumps(payload))
                        sent = sequence
            except Exception as exc:
                print(f'Posture upload unavailable: {exc}; retrying in 2s', file=sys.stderr)
                self.stopped.wait(2)

    def _falls(self):
        while not self.stopped.is_set():
            with self.condition:
                self.condition.wait_for(lambda: self.stopped.is_set() or self.pending_fall is not None)
                if self.stopped.is_set():
                    return
                payload = self.pending_fall
            try:
                request = Request(self.fall_url, data=json.dumps(payload).encode(),
                                  headers={'Content-Type': 'application/json'}, method='POST')
                with urlopen(request, timeout=3) as response:
                    if response.status != 200:
                        raise RuntimeError(f'Unexpected fall response: {response.status}')
                with self.condition:
                    if self.pending_fall is payload:
                        self.pending_fall = None
            except Exception as exc:
                print(f'Fall upload unavailable: {exc}; retrying in 2s', file=sys.stderr)
                self.stopped.wait(2)
