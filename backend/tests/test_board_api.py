import unittest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.main import app
from app import store


class BoardApiTests(unittest.TestCase):
    def test_posture_and_fall_timestamp_deduplication(self):
        with TestClient(app) as client:
            payload = {'ts': '2026-09-19T14:32:10Z', 'in_camera': True, 'current_posture': None}
            with client.websocket_connect('/ws/room/101?role=board') as board:
                board.send_json(payload)
                # A second invalid message closes only after the first is processed.
                board.send_json({**payload, 'current_posture': 'fall'})
                with self.assertRaises(WebSocketDisconnect):
                    board.receive_text()
            self.assertTrue(store.get_in_camera('101'))
            self.assertIsNone(store.get_posture('101'))
            self.assertEqual(store.get_location('101'), 'out_of_bed')
            with client.websocket_connect('/ws/room/101') as viewer:
                self.assertEqual(viewer.receive_json()['location'], 'out_of_bed')
            first = client.post('/api/beds/101/possible-fall', json={'ts': payload['ts']})
            self.assertEqual(first.status_code, 200)
            first = first.json()
            self.assertEqual(first['started_at'], payload['ts'])
            second = client.post('/api/beds/101/possible-fall', json={'ts': '2026-09-19T14:32:11Z'}).json()
            self.assertEqual(first['event_id'], second['event_id'])
            self.assertEqual(second['last_seen_at'], '2026-09-19T14:32:11Z')
            client.post('/api/events/' + first['event_id'] + '/resolve', json={
                'completed_actions': 'checked', 'follow_up': 'monitor'})
            third = client.post('/api/beds/101/possible-fall', json={'ts': '2026-09-19T14:32:12Z'}).json()
            self.assertNotEqual(first['event_id'], third['event_id'])

    def test_invalid_posture_closes_with_policy_error(self):
        payload = {'ts': '2026-09-19T14:32:10Z', 'in_camera': True, 'current_posture': 'standing'}
        cases = [[], {k: v for k, v in payload.items() if k != 'in_camera'},
                 {**payload, 'in_camera': 'false'}, {**payload, 'in_camera': False},
                 {**payload, 'current_posture': 'unknown'}]
        with TestClient(app) as client:
            for case in cases:
                with client.websocket_connect('/ws/room/101?role=board') as board:
                    board.send_json(case)
                    with self.assertRaises(WebSocketDisconnect) as error:
                        board.receive_text()
                    self.assertEqual(error.exception.code, 1008)
