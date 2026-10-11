import copy
import json
import tempfile
import unittest
import io
from pathlib import Path
from unittest.mock import patch
import tenant_store as store

class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        album = self.root / 'runtime-albums' / 'album-test'
        album.mkdir(parents=True)
        (album / 'album.json').write_text(json.dumps({'title': 'Source', 'pages': []}), encoding='utf-8')
        self.patches = [patch.object(store, 'ROOT', self.root), patch.object(store, 'STORE', self.root / 'tenant-config.json')]
        for p in self.patches: p.start()
        self.data = {'tenants': [{'id': 'one', 'name': 'One'}, {'id': 'two', 'name': 'Two'}], 'catalogs': [
            {'id': 'book', 'tenantId': 'one', 'title': 'Book one', 'albumId': 'album-test'},
            {'id': 'book', 'tenantId': 'two', 'title': 'Video two', 'mediaType': 'video', 'videoUrl': 'https://example.com/demo.mp4'}]}
    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()
    def test_roundtrip(self):
        saved = store.save(self.data)
        self.assertEqual(saved, store.read())
        self.assertEqual(store.resolve('one', 'book')['album']['title'], 'Source')
        self.assertEqual(store.resolve('two', 'book')['catalog']['mediaType'], 'video')
    def test_scope_and_missing(self):
        store.save(self.data)
        with self.assertRaises(LookupError): store.resolve('other', 'book')
        with self.assertRaises(LookupError): store.resolve('one', 'missing')
    def test_invalid_config_preserves_previous(self):
        saved = store.save(self.data)
        invalid = copy.deepcopy(self.data)
        invalid['tenants'][0]['logoUrl'] = 'javascript:alert(1)'
        with self.assertRaises(ValueError): store.save(invalid)
        self.assertEqual(store.read(), saved)
    def test_duplicate_and_reference(self):
        for mutate in [lambda d: d['tenants'].append(d['tenants'][0]), lambda d: d['catalogs'].append(d['catalogs'][0]), lambda d: d['catalogs'][0].update(tenantId='missing'), lambda d: d['catalogs'][0].update(albumId='../escape')]:
            invalid = copy.deepcopy(self.data); mutate(invalid)
            with self.assertRaises(ValueError): store.save(invalid)
    def test_initial_migration(self):
        config = store.read()
        self.assertEqual(config['catalogs'][0]['albumId'], 'album-test')
        self.assertEqual(config['catalogs'][0]['tenantId'], 'default')
    def test_switch_content_stable_id(self):
        store.save(self.data)
        self.data['catalogs'][0].update(mediaType='video', videoUrl='https://example.com/new.mp4')
        store.save(self.data)
        self.assertEqual(store.resolve('one', 'book')['catalog']['videoUrl'], 'https://example.com/new.mp4')

    def request(self, method, path, body=None):
        payload = json.dumps(body).encode() if body is not None else b''
        handler = type('Request', (), {'command': method, 'path': path, 'headers': {'Content-Length': str(len(payload))}, 'rfile': io.BytesIO(payload)})()
        captured = []
        handled = store.handle(handler, lambda h, status, data: captured.append((status, data)), lambda: ('https://brochure.example.com', 'configured'))
        self.assertTrue(handled)
        return captured[0]

    def test_publish_routes_and_production_origin(self):
        store.save(self.data)
        for tid in ('one', 'two'):
            status, data = self.request('POST', '/api/catalog-publish', {'tenantId': tid, 'catalogId': 'book'})
            self.assertEqual(status, 200)
            self.assertEqual(data['url'], f'https://brochure.example.com/v/{tid}/book')
            self.assertEqual(data['addressMode'], 'configured')
        self.assertEqual(self.request('GET', '/api/view/one/missing')[0], 404)

    def test_config_api_validation_and_roundtrip(self):
        self.assertEqual(self.request('POST', '/api/config', self.data)[0], 200)
        status, data = self.request('GET', '/api/config')
        self.assertEqual(status, 200)
        self.assertEqual(len(data['tenants']), 2)
        self.assertEqual(self.request('POST', '/api/config', {'tenants': None})[0], 400)
        self.assertEqual(self.request('GET', '/api/view/two/book')[1]['catalog']['mediaType'], 'video')

if __name__ == '__main__': unittest.main()
