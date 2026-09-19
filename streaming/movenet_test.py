#!/usr/bin/env python3
"""Combined entry point for the supplied MoveNet test and MJPEG stream.

Defaults to /dev/video2 as in the original script. --device can override it.
"""
import sys

try:
    from .publish_camera import main
except ImportError:
    from publish_camera import main


if __name__ == '__main__':
    sys.exit(main(['--pose', '--device', '/dev/video2', *sys.argv[1:]]))
