import tempfile
import unittest
from pathlib import Path
from PIL import Image
from video_export import build_ffmpeg_command, scenes, render_scene

class VideoTests(unittest.TestCase):
    def test_encoder_is_low_memory_and_keeps_1080p_h264(self):
        command = build_ffmpeg_command('ffmpeg.exe', Path('frames.txt'), Path('out.mp4'), 12.5)
        self.assertEqual(command[command.index('-vf') + 1], 'fps=30')
        self.assertEqual(command[command.index('-filter_threads') + 1], '1')
        self.assertEqual(command[command.index('-threads:v') + 1], '1')
        self.assertEqual(command[command.index('-preset') + 1], 'fast')
        self.assertIn('libx264', command)
        self.assertIn('-an', command)

    def test_encoder_preserves_audio_and_clamps_volume(self):
        command = build_ffmpeg_command('ffmpeg.exe', Path('frames.txt'), Path('out.mp4'), 12.5, Path('music.mp3'), 1.5)
        self.assertIn('volume=1', command)
        self.assertIn('aac', command)
        self.assertNotIn('-an', command)

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
