import unittest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app

# Server intentionally only checks JPEG envelope, never decodes or re-encodes.
FIRST = b'\xff\xd8first\xff\xd9'
LATEST = b'\xff\xd8latest\xff\xd9'


class CameraTests(unittest.TestCase):
    def test_relay_latest_frame_and_multiple_viewers(self):
        with TestClient(app) as client:
            assert client.get('/camera').status_code == 404
            with client.websocket_connect('/ws/camera/publish') as publisher:
                assert publisher.receive_text() == 'ready'
                with client.websocket_connect('/ws/camera/view') as fast, client.websocket_connect('/ws/camera/view') as slow:
                    publisher.send_bytes(FIRST)
                    assert publisher.receive_text() == 'ok'
                    fast.send_text('next')
                    assert fast.receive_bytes() == FIRST
                    publisher.send_bytes(LATEST)
                    assert publisher.receive_text() == 'ok'
                    slow.send_text('next')
                    assert slow.receive_bytes() == LATEST
                    fast.send_text('next')
                    assert fast.receive_bytes() == LATEST
            # Exiting publisher connection clears stale data before another session.
            with client.websocket_connect('/ws/camera/view') as viewer:
                viewer.send_text('next')
                assert viewer.receive_json() == {'status': 'waiting'}
            with client.websocket_connect('/ws/camera/publish') as publisher:
                assert publisher.receive_text() == 'ready'


    def test_exclusive_publisher_and_invalid_frame(self):
        with TestClient(app) as client:
            with client.websocket_connect('/ws/camera/publish') as publisher:
                assert publisher.receive_text() == 'ready'
                with client.websocket_connect('/ws/camera/publish') as other:
                    with self.assertRaises(WebSocketDisconnect) as error:
                        other.receive_text()
                    assert error.exception.code == 1008
                publisher.send_bytes(b'not jpeg')
                with self.assertRaises(WebSocketDisconnect) as error:
                    publisher.receive_text()
                assert error.exception.code == 1003


    def test_oversized_frame_rejected(self):
        with TestClient(app) as client:
            with client.websocket_connect('/ws/camera/publish') as publisher:
                assert publisher.receive_text() == 'ready'
                publisher.send_bytes(b'\xff\xd8' + b'x' * (2 * 1024 * 1024) + b'\xff\xd9')
                with self.assertRaises(WebSocketDisconnect) as error:
                    publisher.receive_text()
                assert error.exception.code == 1009


    def test_stale_frame_hidden(self):
        with TestClient(app) as client:
            with client.websocket_connect('/ws/camera/publish') as publisher:
                assert publisher.receive_text() == 'ready'
                publisher.send_bytes(FIRST)
                assert publisher.receive_text() == 'ok'
                app.state.camera.received_at -= 4
                with client.websocket_connect('/ws/camera/view') as viewer:
                    viewer.send_text('next')
                    assert viewer.receive_json() == {'status': 'waiting'}
