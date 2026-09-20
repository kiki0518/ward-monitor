import unittest
from streaming.board_reporter import BoardReporter, posture_payload


class BoardReporterTests(unittest.TestCase):
    def result(self, **kwargs):
        return dict(ts='2026-09-19T14:32:10Z', in_camera=True,
                    stable_pose='standing', fall_detected=False, **kwargs)

    def test_mapping_never_sends_fall_or_unknown(self):
        for pose in ('unknown', 'fall', 'standing', 'sitting', 'lying'):
            for present in (True, False):
                result = self.result()
                result.update(stable_pose=pose, in_camera=present)
                payload = posture_payload(result)
                self.assertEqual(payload['current_posture'], pose if present and pose in
                                 ('standing', 'sitting', 'lying') else None)

    def test_latest_posture_keeps_pending_fall_after_recovery(self):
        reporter = BoardReporter('localhost')
        result = self.result()
        result['fall_detected'] = True
        reporter.submit(result)
        for i in range(100):
            result = self.result()
            result['ts'] = str(i)
            reporter.submit(result)
        self.assertEqual(reporter.latest['ts'], '99')
        self.assertEqual(reporter.pending_fall['ts'], '2026-09-19T14:32:10Z')

    def test_uploads_one_way_posture_and_retries_fall_independently(self):
        import json
        import threading
        from unittest.mock import patch
        reporter = BoardReporter('localhost')
        posture_sent, fall_sent = threading.Event(), threading.Event()
        received, attempts = [], []

        class Socket:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def send(self, data):
                received.append(json.loads(data))
                posture_sent.set()
            # No recv method: board API must never wait for an ACK.

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        def post(request, timeout):
            attempts.append(json.loads(request.data))
            if len(attempts) == 1:
                raise OSError('offline')
            fall_sent.set()
            return Response()

        with patch('websockets.sync.client.connect', return_value=Socket()), patch(
                'streaming.board_reporter.urlopen', side_effect=post):
            result = self.result()
            result['fall_detected'] = True
            reporter.submit(result)
            reporter.start()
            try:
                self.assertTrue(posture_sent.wait(1))
                self.assertTrue(fall_sent.wait(4))
            finally:
                reporter.stop()
        self.assertEqual(received[0], posture_payload(result))
        self.assertEqual(attempts, [{'ts': result['ts']}] * 2)
        self.assertFalse(any(t.is_alive() for t in reporter.threads))
