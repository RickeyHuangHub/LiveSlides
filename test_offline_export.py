import base64
import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import offline_export

class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        build = self.root / 'offline-dist'; build.mkdir()
        (build / 'player.js').write_text('console.log("offline");', encoding='utf-8')
        (build / 'player.css').write_text('body{margin:0}', encoding='utf-8')
        pages = self.root / 'runtime-albums' / 'album-test' / 'pages'; pages.mkdir(parents=True)
        self.image_bytes = b'original-webp-bytes-no-reencoding'
        (pages / 'one.webp').write_bytes(self.image_bytes)
        self.data = dict(id='album-test', base='/api/albums/album-test/',
            tenant=dict(id='company', name='Company', logoUrl='', backgroundUrl='', primaryColor='#336699'),
            catalog=dict(id='catalog', tenantId='company', title='Test', mediaType='album', albumId='album-test'),
            album=dict(title='Test', viewer=dict(autoplay=False, loop=False, interval=3000), pages=[dict(id='one', src='pages/one.webp', thumbnail='pages/one.webp', width=960, height=1080)]))

    def tearDown(self): self.temp.cleanup()

    def unpack(self, data=None):
        with offline_export.make_package(data or self.data, self.root) as package:
            with zipfile.ZipFile(package) as archive:
                self.assertEqual(set(archive.namelist()), {'开始播放.html', '使用说明.txt'})
                self.assertIsNone(archive.testzip())
                page = archive.read('开始播放.html').decode('utf-8')
        text = page.split('window.__LIVESLIDES_OFFLINE__=', 1)[1].split(';</script>', 1)[0]
        return page, json.loads(text)

    def test_standalone_assets_and_loop(self):
        original = copy.deepcopy(self.data)
        page, data = self.unpack()
        self.assertEqual(data['base'], '')
        self.assertTrue(data['album']['viewer']['autoplay'])
        self.assertTrue(data['album']['viewer']['loop'])
        image = data['album']['pages'][0]['src']
        self.assertEqual(base64.b64decode(image.split(',')[1]), self.image_bytes)
        self.assertIn("connect-src 'none'", page)
        self.assertNotIn('<script src=', page)
        self.assertNotIn('<link ', page)
        self.assertEqual(original, self.data)

    def test_script_injection_escaped(self):
        self.data['catalog']['title'] = '</script><script>alert(1)</script>'
        page, data = self.unpack()
        self.assertNotIn('</script><script>alert(1)', page)
        self.assertEqual(data['catalog']['title'], self.data['catalog']['title'])

    def test_external_brand_rejected(self):
        self.data['tenant']['logoUrl'] = 'https://example.com/logo.png'
        with self.assertRaisesRegex(ValueError, '网络 Logo'): self.unpack()

    def test_local_brand_embedded(self):
        self.data['tenant']['logoUrl'] = '/api/albums/album-test/pages/one.webp'
        _, data = self.unpack()
        self.assertTrue(data['tenant']['logoUrl'].startswith('data:image/webp;'))

    def test_traversal_and_missing(self):
        for path in ('../../secret.webp', '/secret.webp', 'https://example.com/a.webp', 'pages/missing.webp'):
            self.data['album']['pages'][0]['src'] = path
            with self.assertRaises(ValueError): self.unpack()

    def test_missing_build(self):
        (self.root / 'offline-dist' / 'player.js').unlink()
        with self.assertRaisesRegex(ValueError, '尚未构建'): self.unpack()

    def test_video_not_silently_online(self):
        self.data['catalog']['mediaType'] = 'video'
        with self.assertRaisesRegex(ValueError, '暂不支持视频'): self.unpack()

    def test_size_limit(self):
        with patch.object(offline_export, 'MAX_ASSETS', 1):
            with self.assertRaisesRegex(ValueError, '256MB'): self.unpack()

if __name__ == '__main__': unittest.main()
