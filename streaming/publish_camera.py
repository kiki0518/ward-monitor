#!/usr/bin/env python3
"""Forward camera-native MJPEG to FastAPI, without decoding or re-encoding."""
import argparse
import math
import re
import sys
import time


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('must be greater than zero')
    return number


def positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('must be finite and greater than zero')
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True, help='Server IPv4 address or hostname')
    parser.add_argument('--port', type=positive_int, default=8000)
    parser.add_argument('--source', choices=['mjpeg', 'test'], default='mjpeg')
    parser.add_argument('--device', default='/dev/video0')
    parser.add_argument('--width', type=positive_int, default=640)
    parser.add_argument('--height', type=positive_int, default=480)
    parser.add_argument('--fps', type=positive_int, default=15)
    parser.add_argument('--bed-id', default='101', choices=['101'], help='Demo camera bed')
    parser.add_argument('--pose', action='store_true', help='Run MoveNet on a separate JPEG branch')
    parser.add_argument('--model', default='/opt/gopoint-apps/downloads/movenet_quant_vela.tflite')
    parser.add_argument('--delegate', default='/usr/lib/libethosu_delegate.so')
    parser.add_argument('--pose-print-interval', type=positive_float, default=1.0)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', args.server):
        parser.error('--server must be an IPv4 address or hostname without a scheme or port')
    if not re.fullmatch(r'/dev/video[0-9]+', args.device):
        parser.error('--device must look like /dev/video0')
    if args.port > 65535:
        parser.error('--port must be at most 65535')
    return args


def build_pipeline(args):
    dimensions = f'width={args.width},height={args.height},framerate={args.fps}/1'
    if args.source == 'test':
        source = f'videotestsrc is-live=true pattern=ball ! video/x-raw,{dimensions} ! jpegenc'
    else:
        source = f'v4l2src device={args.device} do-timestamp=true ! image/jpeg,{dimensions}'
    sink_options = 'max-buffers=1 drop=true sync=false enable-last-sample=false'
    if not args.pose:
        return source + f' ! appsink name=frames {sink_options}'
    # Each branch gets its own scheduling thread and bounded, leaky queue.
    queue = 'queue max-size-buffers=1 max-size-bytes=0 max-size-time=0 leaky=downstream'
    return (
        source + ' ! tee name=camera '
        f'camera. ! {queue} ! appsink name=frames {sink_options} '
        f'camera. ! {queue} ! appsink name=pose_frames {sink_options}'
    )


def check_camera(bus, Gst):
    error = bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.EOS)
    if error:
        if error.type == Gst.MessageType.ERROR:
            reason, debug = error.parse_error()
            raise RuntimeError(f'Camera: {reason}; {debug}')
        raise RuntimeError('Camera stream ended')


def run(args, Gst, connect):
    pose = None
    if args.pose:
        if __package__:
            from .movenet_pose import MoveNetPose, print_pose
            from .pose_worker import PoseWorker
            from .board_reporter import BoardReporter
        else:
            from movenet_pose import MoveNetPose, print_pose
            from pose_worker import PoseWorker
            from board_reporter import BoardReporter
        # Fail visibly before opening the camera if the model/delegate is unavailable.
        pose = MoveNetPose(args.model, args.delegate)
    pipeline = Gst.parse_launch(build_pipeline(args))
    sink = pipeline.get_by_name('frames')
    bus = pipeline.get_bus()
    url = f'ws://{args.server}:{args.port}/ws/camera/publish'
    worker = None
    reporter = None
    try:
        if pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError('Unable to start camera pipeline')
        if pose is not None:
            reporter = BoardReporter(args.server, args.port, args.bed_id)
            reporter.start()
            worker = PoseWorker(
                pipeline.get_by_name('pose_frames'), Gst, pose.infer_jpeg,
                print_pose, args.pose_print_interval, on_result=reporter.submit,
            )
            worker.start()
            print('MoveNet branch started; JPEG streaming and inference run independently.', flush=True)
        while True:
            check_camera(bus, Gst)
            try:
                with connect(url, compression=None, max_size=1024, open_timeout=5, close_timeout=2) as ws:
                    if ws.recv(timeout=5) != 'ready':
                        raise RuntimeError('Unexpected server handshake')
                    print(f'Connected. Viewer API: ws://{args.server}:{args.port}/ws/camera/view', flush=True)
                    last_sample = time.monotonic()
                    while True:
                        check_camera(bus, Gst)
                        sample = sink.emit('try-pull-sample', Gst.SECOND)
                        if sample is None:
                            if time.monotonic() - last_sample > 5:
                                raise RuntimeError('No camera frames for 5 seconds; check device and MJPEG caps')
                            continue
                        last_sample = time.monotonic()
                        buffer = sample.get_buffer()
                        frame = buffer.extract_dup(0, buffer.get_size())
                        if len(frame) > 2 * 1024 * 1024:
                            raise RuntimeError('JPEG exceeds server limit of 2 MiB; lower resolution')
                        ws.send(frame)
                        if ws.recv(timeout=5) != 'ok':
                            raise RuntimeError('Unexpected server acknowledgement')
            except (OSError, TimeoutError) as exc:
                print(f'Connection unavailable: {exc}; retrying in 2s', file=sys.stderr)
                time.sleep(2)
            except Exception as exc:
                from websockets.exceptions import ConnectionClosed
                if not isinstance(exc, ConnectionClosed):
                    raise
                if exc.rcvd is not None and exc.rcvd.code in (1003, 1008, 1009):
                    raise RuntimeError(f'Server rejected stream: {exc}') from exc
                print(f'Connection closed: {exc}; retrying in 2s', file=sys.stderr)
                time.sleep(2)
    finally:
        if worker is not None:
            worker.stop()
        pipeline.set_state(Gst.State.NULL)
        if worker is not None:
            worker.join()
        if reporter is not None:
            reporter.stop()


def main(argv=None):
    args = parse_args(argv)
    print(build_pipeline(args), flush=True)
    if args.dry_run:
        return 0
    try:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        from websockets.sync.client import connect
        Gst.init(None)
        run(args, Gst, connect)
    except KeyboardInterrupt:
        return 130
    except (ImportError, ValueError, RuntimeError, OSError) as exc:
        print(f'{exc}\nSee streaming/README.md for dependencies and camera setup.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
