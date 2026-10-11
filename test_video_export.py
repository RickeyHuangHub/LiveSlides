import tempfile
import unittest
from pathlib import Path
from PIL import Image
from video_export import scenes, render_scene

class VideoTests(unittest.TestCase):
    def test_cover_and_spread_sequence(self):
        left = dict(parentSlide=1, part='left', src='left.png')
        right = dict(parentSlide=1, part='right', src='right.png')
        self.assertEqual(scenes(dict(pageMode='left-cover-spread', pages=[left, right])), [[left], [left, right]])
        self.assertEqual(scenes(dict(pageMode='split-all', pages=[left, right])), [[left, right]])
    def test_pairing_and_aspect(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Image.new('RGB', (80, 90), 'red').save(root/'l.png')
            Image.new('RGB', (80, 90), 'blue').save(root/'r.png')
            with render_scene([dict(src='r.png', part='right'), dict(src='l.png', part='left')], root, (160, 90)) as frame:
                self.assertEqual(frame.getpixel((10, 40)), (255, 0, 0))
                self.assertEqual(frame.getpixel((150, 40)), (0, 0, 255))
            with render_scene([dict(src='l.png', part='left')], root, (160, 90)) as frame:
                self.assertEqual(frame.getpixel((0, 40)), (11, 15, 25))
    def test_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError): render_scene([dict(src='../secret.png')], Path(temp))

if __name__ == '__main__': unittest.main()
