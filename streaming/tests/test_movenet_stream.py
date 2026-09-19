"""Hardware-free tests; actual V4L2 / Ethos-U still require board acceptance."""
import contextlib
import io
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from streaming import movenet_pose as pose
from streaming import publish_camera as publisher
from streaming.pose_worker import PoseWorker


class FakeInterpreter:
    def __init__(self, dtype=np.uint8, quantization=(0.0, 0), output=None):
        self.dtype, self.quantization = dtype, quantization
        self.output = output if output is not None else np.zeros((1, 1, 17, 3), np.float32)

    def allocate_tensors(self):
        pass

    def get_input_details(self):
        return [{'shape': [1, 2, 2, 3], 'dtype': self.dtype, 'quantization': self.quantization, 'index': 0}]

    def get_output_details(self):
        return [{'shape': self.output.shape, 'quantization': (0.01, 0), 'index': 1}]

    def set_tensor(self, index, tensor):
        self.tensor = tensor

    def invoke(self):
        pass

    def get_tensor(self, index):
        return self.output


class Sample:
    def __init__(self, value):
        self.value = value

    def get_buffer(self):
        return self

    def get_size(self):
        return len(self.value)

    def extract_dup(self, offset, size):
        return self.value[offset:offset + size]


class LatestSink:
    def __init__(self):
        self.items = queue.Queue(maxsize=1)

    def put(self, value):
        try:
            self.items.get_nowait()
        except queue.Empty:
            pass
        self.items.put_nowait(Sample(value))

    def emit(self, action, timeout):
        try:
            return self.items.get(timeout=timeout / 1_000_000_000)
        except queue.Empty:
            return None


class PoseRulesTests(unittest.TestCase):
    def keypoints(self):
        points = {name: {'x': 0.5, 'y': 0.5, 'score': 0.9} for name in pose.KEYPOINT_NAMES}
        for side, x in (('left', .4), ('right', .6)):
            for joint, y in (('shoulder', .2), ('hip', .5), ('knee', .7), ('ankle', .9), ('wrist', .4)):
                points[f'{side}_{joint}'].update(x=x, y=y)
        return points

    def test_standing_sitting_lying_and_raising_hand(self):
        points = self.keypoints()
        self.assertEqual(pose.classify_pose(points)['base_pose'], 'standing')
        for side in ('left', 'right'):
            points[f'{side}_knee']['x'] += .2
            points[f'{side}_knee']['y'] = .5
            points[f'{side}_ankle']['x'] += .2
        self.assertEqual(pose.classify_pose(points)['base_pose'], 'sitting')
        points = self.keypoints()
        points['left_wrist']['y'] = .05
        result = pose.classify_pose(points)
        self.assertEqual(result['pose_class'], 'raising_hand')
        self.assertEqual(result['base_pose'], 'standing')
        points = self.keypoints()
        for side in ('left', 'right'):
            points[f'{side}_shoulder']['x'] += .3
            points[f'{side}_shoulder']['y'] = .5
        self.assertEqual(pose.classify_pose(points)['base_pose'], 'lying')

    def test_low_confidence_and_smoothing(self):
        points = self.keypoints()
        for point in points.values():
            point['score'] = 0
        self.assertEqual(pose.classify_pose(points)['pose_class'], 'unknown')
        self.assertEqual(pose.get_stable_pose(['unknown', 'standing', 'standing', 'sitting']), 'standing')
        self.assertEqual(pose.get_stable_pose(['unknown'] * 5), 'unknown')

    def estimator(self, interpreter):
        with contextlib.redirect_stdout(io.StringIO()):
            return pose.MoveNetPose(interpreter=interpreter)

    def test_jpeg_decode_rgb_mapping_and_original_bytes_unchanged(self):
        interpreter = FakeInterpreter()
        estimator = self.estimator(interpreter)
        ok, data = cv2.imencode('.jpg', np.full((8, 12, 3), (15, 80, 190), dtype=np.uint8))
        self.assertTrue(ok)
        jpeg = data.tobytes()
        original = bytes(jpeg)
        result = estimator.infer_jpeg(jpeg)
        expected = cv2.cvtColor(cv2.resize(cv2.imdecode(data, cv2.IMREAD_COLOR), (2, 2)), cv2.COLOR_BGR2RGB)
        np.testing.assert_array_equal(interpreter.tensor[0], expected)
        self.assertEqual(jpeg, original)
        self.assertEqual((result['frame_width'], result['frame_height']), (12, 8))
        self.assertEqual(len(result['keypoints']), 17)
        with self.assertRaises(ValueError):
            estimator.infer_jpeg(b'not jpeg')

    def test_int8_input_and_quantized_output(self):
        output = np.full((1, 1, 17, 3), 50, dtype=np.int8)
        interpreter = FakeInterpreter(np.int8, (2.0, -128), output)
        estimator = self.estimator(interpreter)
        frame = np.full((2, 2, 3), (20, 40, 60), np.uint8)
        result = estimator.infer_frame(frame)
        np.testing.assert_array_equal(interpreter.tensor[0, 0, 0], [-98, -108, -118])
        self.assertAlmostEqual(result['keypoints']['nose']['x'], .5)
        self.assertAlmostEqual(result['keypoints']['nose']['score'], .5)


class BranchTests(unittest.TestCase):
    def test_single_capture_two_bounded_jpeg_branches(self):
        args = publisher.parse_args(['--server', 'localhost', '--pose'])
        pipeline = publisher.build_pipeline(args)
        self.assertEqual(pipeline.count('v4l2src'), 1)
        self.assertEqual(pipeline.count('leaky=downstream'), 2)
        self.assertIn('name=pose_frames', pipeline)
        self.assertNotIn('jpegenc', pipeline)
        self.assertNotIn('jpegdec', pipeline)

    def test_pose_worker_skips_old_frames_while_busy(self):
        sink = LatestSink()
        entered, release, newest = threading.Event(), threading.Event(), threading.Event()
        seen = []
        def infer(value):
            seen.append(value)
            if value == b'first':
                entered.set()
                if not release.wait(2):
                    raise RuntimeError('test release timed out')
            if value == b'latest':
                newest.set()
            return {}
        worker = PoseWorker(sink, SimpleNamespace(SECOND=1_000_000_000), infer, lambda result: None)
        sink.put(b'first')
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            sink.put(b'old')
            sink.put(b'latest')
            release.set()
            self.assertTrue(newest.wait(2))
        finally:
            release.set()
            worker.stop()
            worker.join()
        self.assertEqual(seen, [b'first', b'latest'])
        self.assertFalse(worker.thread.is_alive())

    def run_fake(self, connect, infer):
        frame = b'\xff\xd8unchanged\xff\xd9'
        sinks = {'frames': LatestSink(), 'pose_frames': LatestSink()}
        for sink in sinks.values():
            sink.put(frame)
        states = []
        pipeline = SimpleNamespace(
            get_by_name=lambda name: sinks[name],
            get_bus=lambda: SimpleNamespace(pop_filtered=lambda kinds: None),
            set_state=lambda state: states.append(state),
        )
        gst = SimpleNamespace(
            SECOND=1_000_000_000, parse_launch=lambda spec: pipeline,
            State=SimpleNamespace(PLAYING='playing', NULL='null'),
            StateChangeReturn=SimpleNamespace(FAILURE='failure'),
            MessageType=SimpleNamespace(ERROR=1, EOS=2),
        )
        args = publisher.parse_args(['--server', 'localhost', '--pose'])
        with patch.object(pose, 'MoveNetPose', return_value=SimpleNamespace(infer_jpeg=infer)), patch.object(pose, 'print_pose'), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                publisher.run(args, gst, connect)
        self.assertEqual(states[-1], 'null')
        self.assertFalse(any(t.name == 'movenet-pose' and t.is_alive() for t in threading.enumerate()))
        return frame

    def test_network_sends_original_jpeg_while_inference_is_blocked(self):
        entered, release = threading.Event(), threading.Event()
        sent = []
        def infer(value):
            entered.set()
            if not release.wait(2):
                raise RuntimeError('test release timed out')
            return {}
        class Connection:
            def __enter__(self):
                if not entered.wait(2):
                    raise RuntimeError('inference did not start')
                return self
            def __exit__(self, *args):
                release.set()
            def recv(self, **kwargs):
                return 'ready'
            def send(self, value):
                sent.append(value)
                raise KeyboardInterrupt
        try:
            frame = self.run_fake(lambda *args, **kwargs: Connection(), infer)
        finally:
            release.set()
        self.assertEqual(sent, [frame])

    def test_inference_runs_before_network_connects(self):
        inferred = threading.Event()
        def infer(value):
            inferred.set()
            return {}
        def connect(*args, **kwargs):
            if not inferred.wait(2):
                raise RuntimeError('inference blocked by network')
            raise KeyboardInterrupt
        self.run_fake(connect, infer)
        self.assertTrue(inferred.is_set())

    def test_worker_failure_is_visible_and_does_not_escape_thread(self):
        sink = LatestSink()
        sink.put(b'bad jpeg')
        def fail(value):
            raise ValueError('decode failed')
        worker = PoseWorker(sink, SimpleNamespace(SECOND=1_000_000_000), fail, lambda result: None)
        log = io.StringIO()
        with contextlib.redirect_stderr(log):
            worker.start()
            worker.join()
        self.assertIsInstance(worker.error, ValueError)
        self.assertIn('Camera streaming continues', log.getvalue())


if __name__ == '__main__':
    unittest.main()
