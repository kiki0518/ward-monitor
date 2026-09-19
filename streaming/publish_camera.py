#!/usr/bin/env python3
"""Publish a Linux V4L2 camera (or a test pattern) to MediaMTX over RTSP/TCP."""

import argparse
import re
import shlex
import shutil
import subprocess
import sys


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True, help="Server IPv4 address or hostname")
    parser.add_argument("--source", choices=["raw", "mjpeg", "h264", "test"], default="raw")
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--width", type=positive_int, default=640)
    parser.add_argument("--height", type=positive_int, default=480)
    parser.add_argument("--fps", type=positive_int, default=15)
    parser.add_argument("--bitrate", type=positive_int, default=1500, help="Software encoder kbit/s")
    parser.add_argument("--dry-run", action="store_true", help="Print pipeline without opening a camera")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", args.server):
        parser.error("--server must be an IPv4 address or hostname, without a scheme or port")
    if not re.fullmatch(r"/dev/video[0-9]+", args.device):
        parser.error("--device must look like /dev/video0")
    if args.source != "h264" and (args.width % 2 or args.height % 2):
        parser.error("I420 encoding requires even width and height")
    return args


def build_pipeline(args):
    elements = ["rtspclientsink", "h264parse", "rtph264pay"]
    dimensions = f"width={args.width},height={args.height},framerate={args.fps}/1"
    if args.source == "test":
        elements += ["videotestsrc"]
        pipeline = ["videotestsrc", "is-live=true", "pattern=ball", "!", f"video/x-raw,{dimensions}"]
    else:
        elements += ["v4l2src"]
        media_type = {"raw": "video/x-raw", "mjpeg": "image/jpeg", "h264": "video/x-h264"}[args.source]
        pipeline = ["v4l2src", f"device={args.device}", "do-timestamp=true", "!", f"{media_type},{dimensions}"]
    if args.source == "mjpeg":
        elements += ["jpegdec"]
        pipeline += ["!", "jpegdec"]
    if args.source != "h264":
        elements += ["queue", "videoconvert", "x264enc"]
        # Only drop raw frames before encoding; never arbitrarily drop H.264 reference frames.
        pipeline += [
            "!", "queue", "max-size-buffers=2", "max-size-bytes=0", "max-size-time=0", "leaky=downstream",
            "!", "videoconvert", "!", "video/x-raw,format=I420",
            "!", "x264enc", "tune=zerolatency", "speed-preset=ultrafast",
            f"bitrate={args.bitrate}", f"key-int-max={args.fps}", "bframes=0",
            "!", "video/x-h264,profile=baseline",
        ]
    pipeline += [
        "!", "h264parse", "config-interval=-1",
        "!", "rtspclientsink", "protocols=tcp",
        f"location=rtsp://{args.server}:8554/camera",
    ]
    return ["gst-launch-1.0", "-e", *pipeline], elements


def main(argv=None):
    args = parse_args(argv)
    command, elements = build_pipeline(args)
    print(shlex.join(command), flush=True)
    if args.dry_run:
        return 0
    for executable in ("gst-launch-1.0", "gst-inspect-1.0"):
        if not shutil.which(executable):
            print(f"Missing {executable}; see streaming/README.md for dependencies.", file=sys.stderr)
            return 2
    missing = [element for element in elements if subprocess.run(
        ["gst-inspect-1.0", element], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode]
    if missing:
        print("Missing GStreamer plugins: " + ", ".join(missing), file=sys.stderr)
        return 2
    print(f"Watch: http://{args.server}:8889/camera", flush=True)
    print("Ctrl+C stops publishing. If disconnected, fix the connection and run again.", flush=True)
    try:
        return subprocess.call(command)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
