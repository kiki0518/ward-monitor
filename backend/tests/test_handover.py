import io
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import handover, store


class HandoverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [patch.object(handover, 'DB_PATH', root / 'handover.db'),
                        patch.object(store, '_CASE_REPORTS_JSON_PATH', root / 'cases.json'),
                        patch.object(store, '_EVENT_HISTORY_JSON_PATH', root / 'events.json')]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.temp.cleanup)
        store.seed_demo_data()
        app = FastAPI()
        app.include_router(handover.router)
        self.client = TestClient(app)
        self.event = store.get_active_events('103')[0]
        store.resolve_event(self.event.event_id, completed_actions='協助回床', follow_up='持續觀察', notes='家屬已知悉')
        self.request = {'handover_date': '2026-09-20', 'shift': 'night', 'source_event_ids': [self.event.event_id]}
        self.content = {'completed_actions': '已協助回床', 'follow_up': '需持續觀察', 'notes': '已通知家屬'}

    def draft(self):
        with patch.object(handover, 'summarize', return_value=self.content):
            result = self.client.post('/api/beds/103/handover-drafts', json=self.request)
        self.assertEqual(result.status_code, 200)
        return result.json()

    def test_review_submit_idempotency_persistence_and_source_retention(self):
        draft = self.draft()
        self.assertEqual(self.client.get('/api/beds/103/handovers').json(), [])
        body = {**self.content, 'completed_actions': '人工修正：已陪同回床', 'handover_date': '2026-09-21', 'shift': 'day'}
        path = f'/api/beds/103/handover-drafts/{draft["id"]}/submit'
        first = self.client.post(path, json=body)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['completed_actions'], body['completed_actions'])
        self.assertEqual(first.json(), self.client.post(path, json=body).json())
        store.seed_demo_data()
        self.assertEqual(len(self.client.get('/api/beds/103/handovers').json()), 1)
        sources = self.client.get('/api/beds/103/handover-sources').json()
        self.assertEqual(len(sources), 1)
        self.assertTrue(sources[0]['included_in_handover'])
        self.assertEqual(sources[0]['completed_actions'], '協助回床')

    def test_patient_isolation_and_validation(self):
        self.assertEqual(self.client.post('/api/beds/101/handover-drafts', json=self.request).status_code, 422)
        draft = self.draft()
        body = {**self.content, 'handover_date': '2026-09-20', 'shift': 'night'}
        self.assertEqual(self.client.post(f'/api/beds/101/handover-drafts/{draft["id"]}/submit', json=body).status_code, 404)
        self.assertEqual(self.client.get('/api/beds/missing/handovers').status_code, 404)
        self.assertEqual(self.client.post('/api/beds/103/handover-drafts', json={**self.request, 'source_event_ids': []}).status_code, 422)
        store._beds['103'].patient_name = '另一位病人'
        self.assertEqual(self.client.get('/api/beds/103/handover-sources').json(), [])
        self.assertEqual(self.client.get('/api/beds/103/handovers').json(), [])

    def test_real_adapter_request_and_invalid_output(self):
        response = {'choices': [{'message': {'content': json.dumps(self.content)}, 'finish_reason': 'stop'}]}
        with patch.dict(os.environ, {'TAIDE_API_BASE': 'http://localhost:8080/v1', 'TAIDE_MODEL': 'taide-test'}):
            with patch.object(handover, 'urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as mocked:
                result = self.client.post('/api/beds/103/handover-drafts', json=self.request)
                self.assertEqual(result.status_code, 200)
                request = mocked.call_args.args[0]
                sent = json.loads(request.data)
                self.assertEqual(sent['model'], 'taide-test')
                self.assertNotIn('patient_name', sent['messages'][1]['content'])
            with patch.object(handover, 'urlopen', return_value=io.BytesIO(b'{"choices": []}')):
                self.assertEqual(self.client.post('/api/beds/103/handover-drafts', json=self.request).status_code, 502)
            with patch.object(handover, 'urlopen', side_effect=TimeoutError):
                self.assertEqual(self.client.post('/api/beds/103/handover-drafts', json=self.request).status_code, 502)
        self.assertEqual(self.client.get('/api/beds/103/handovers').json(), [])
        self.assertFalse(self.client.get('/api/beds/103/handover-sources').json()[0]['included_in_handover'])

    def test_multiple_sources_are_sorted_and_deduplicated(self):
        second = store.report_event('103', state='bed_exit', priority='yellow',
                                    reason='離床', location='out_of_bed')
        store.resolve_event(second.event_id, completed_actions='第二筆處理', follow_up='交班事項', notes='')
        request = {**self.request, 'source_event_ids': [second.event_id, self.event.event_id, second.event_id]}
        with patch.object(handover, 'summarize', return_value=self.content) as model:
            result = self.client.post('/api/beds/103/handover-drafts', json=request)
        self.assertEqual(result.status_code, 200)
        rows = model.call_args.args[0]
        self.assertEqual([r['completed_actions'] for r in rows], ['協助回床', '第二筆處理'])
        self.assertTrue(rows[0]['resolved_at'].endswith('+08:00'))
        self.assertEqual(len(result.json()['source_records']), 2)
        self.assertEqual(self.client.get('/api/beds/103/handovers').json(), [])

    def test_concurrent_submit_and_new_sources_during_review(self):
        draft = self.draft()
        later = store.report_event('103', state='bed_exit', priority='yellow', reason='離床', location='out_of_bed')
        store.resolve_event(later.event_id, completed_actions='稍後新增', follow_up='觀察', notes='')
        path = f'/api/beds/103/handover-drafts/{draft["id"]}/submit'
        body = {**self.content, 'handover_date': '2026-09-20', 'shift': 'night'}
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.client.post(path, json=body), range(2)))
        self.assertEqual([r.status_code for r in results], [200, 200])
        self.assertEqual(results[0].json(), results[1].json())
        self.assertEqual(len(self.client.get('/api/beds/103/handovers').json()), 1)
        available = self.client.get('/api/beds/103/handover-sources').json()
        self.assertFalse(next(r for r in available if r['event_id'] == later.event_id)['included_in_handover'])

    def test_invalid_human_edit_keeps_draft_and_original_sources(self):
        draft = self.draft()
        path = f'/api/beds/103/handover-drafts/{draft["id"]}/submit'
        body = {**self.content, 'completed_actions': '   ', 'handover_date': '2026-09-20', 'shift': 'night'}
        self.assertEqual(self.client.post(path, json=body).status_code, 422)
        self.assertEqual(self.client.get('/api/beds/103/handovers').json(), [])
        self.assertEqual(len(self.client.get('/api/beds/103/handover-sources').json()), 1)

    def test_unconfigured_model_does_not_create_fake_summary(self):
        with patch.dict(os.environ, {'TAIDE_API_BASE': '', 'TAIDE_MODEL': ''}):
            self.assertEqual(self.client.post('/api/beds/103/handover-drafts', json=self.request).status_code, 503)
        self.assertEqual(self.client.get('/api/beds/103/handovers').json(), [])


if __name__ == '__main__':
    unittest.main()
