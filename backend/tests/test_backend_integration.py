"""Verify ward APIs and JPEG streaming share the same application lifecycle."""
import asyncio
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app


class BackendIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        for field, name in (("_CASE_REPORTS_JSON_PATH", "cases.json"), ("_EVENT_HISTORY_JSON_PATH", "events.json")):
            override = patch("app.store." + field, Path(temporary.name) / name)
            override.start()
            self.addCleanup(override.stop)

    def test_camera_and_ward_apis_work_together(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/').json(), {'status': 'ok'})
            self.assertEqual(client.get('/camera').status_code, 404)
            beds = client.get('/api/beds').json()
            self.assertTrue(any(b['bed_id'] == '103' for b in beds))
            with (
                client.websocket_connect('/ws/camera/publish') as publisher,
                client.websocket_connect('/ws/camera/view') as viewer,
                client.websocket_connect('/ws/overview') as overview,
                client.websocket_connect('/ws/room/103') as room,
            ):
                self.assertEqual(publisher.receive_text(), 'ready')
                self.assertEqual(len(overview.receive_json()), len(beds))
                state = room.receive_json()
                self.assertEqual(state['type'], 'state')
                self.assertEqual(state['bed_id'], '103')
                self.assertEqual(state['vitals']['bed_id'], '103')
                # Beds start with no seeded events; create one to exercise resolve() below.
                client.post('/api/beds/103/demo-event', json={'scenario': 'empty_bed'})
                event = client.get('/api/beds/103/events').json()[0]
                self.assertIsNone(event['resolved_at'])
                report = {'completed_actions': 'checked on patient', 'follow_up': 'monitor', 'notes': ''}
                first = client.post(f'/api/events/{event["event_id"]}/resolve', json=report)
                self.assertEqual(first.status_code, 200)
                self.assertIsNotNone(first.json()['resolved_at'])
                again = client.post(f'/api/events/{event["event_id"]}/resolve', json=report)
                self.assertEqual(first.json()['resolved_at'], again.json()['resolved_at'])
                self.assertNotIn(event['event_id'], [e['event_id'] for e in client.get('/api/beds/103/events').json()])
                for jpeg in (b'\xff\xd8first\xff\xd9', b'\xff\xd8second\xff\xd9'):
                    publisher.send_bytes(jpeg)
                    self.assertEqual(publisher.receive_text(), 'ok')
                    viewer.send_text('next')
                    self.assertEqual(viewer.receive_bytes(), jpeg)
                # Existing ward socket is still pushing after camera traffic and REST writes.
                state = room.receive_json()
                self.assertNotIn(event['event_id'], [e['event_id'] for e in state['active_events']])

    def test_existing_error_contracts_and_cors(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/beds/not-a-bed/events').status_code, 404)
            report = {'completed_actions': 'n/a', 'follow_up': 'n/a', 'notes': ''}
            self.assertEqual(client.post('/api/events/not-an-event/resolve', json=report).status_code, 404)
            with self.assertRaises(WebSocketDisconnect) as error:
                with client.websocket_connect('/ws/room/not-a-bed'):
                    pass
            self.assertEqual(error.exception.code, 4004)
            response = client.options('/api/beds', headers={
                'Origin': 'http://localhost:5173',
                'Access-Control-Request-Method': 'GET',
            })
            self.assertEqual(response.headers['access-control-allow-origin'], 'http://localhost:5173')

    def test_single_lifespan_starts_and_awaits_both_simulators(self):
        started, stopped = [], []
        async def background(name):
            started.append(name)
            try:
                await asyncio.Event().wait()
            finally:
                # An async cleanup must finish before lifespan exits.
                await asyncio.sleep(0)
                stopped.append(name)
        with (
            patch('app.main.simulator.run_vitals_jitter', new=lambda: background('vitals')),
            patch('app.main.simulator.run_event_script', new=lambda: background('events')),
        ):
            with TestClient(app) as client:
                self.assertEqual(client.get('/camera').status_code, 404)
                self.assertEqual(sorted(started), ['events', 'vitals'])
                self.assertIsNone(app.state.camera.frame)
                first_camera_state = app.state.camera
            self.assertEqual(sorted(stopped), ['events', 'vitals'])
            with TestClient(app):
                self.assertIsNot(app.state.camera, first_camera_state)
        self.assertEqual(len(started), 4)
        self.assertEqual(len(stopped), 4)


if __name__ == '__main__':
    unittest.main()
