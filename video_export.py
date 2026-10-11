"""Deterministic H.264 MP4 export. Static cuts, not a browser curl recording."""
import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from uuid import uuid4
from PIL import Image, ImageOps

ROOT = Path(__file__).parent
JOBS = {}
LOCK = threading.Lock()
ENCODER_SLOT = threading.BoundedSemaphore(1)

def encoder():
    executable = os.environ.get('LIVESLIDES_FFMPEG') or shutil.which('ffmpeg')
    if not executable or not Path(executable).is_file():
        raise ValueError('未找到 FFmpeg；请安装并加入 PATH，或设置 LIVESLIDES_FFMPEG')
    return executable

def scenes(album):
    pages = album['pages']
    if not pages or len(pages) > 400: raise ValueError('视频导出支持 1–400 个逻辑页面')
    groups = []
    for page in pages:
        if groups and groups[-1][0].get('parentSlide') == page.get('parentSlide') and page.get('parentSlide') is not None:
            groups[-1].append(page)
        else: groups.append([page])
    if album.get('pageMode') == 'left-cover-spread': groups.insert(0, [pages[0]])
    return groups

def render_scene(group, album_root, size=(1920, 1080)):
    images = []
    for page in sorted(group, key=lambda p: {'left': 0, 'full': 0, 'right': 1}.get(p.get('part'), 0)):
        relative = page['src']
        if not isinstance(relative, str) or ':' in relative or '\\' in relative or relative.startswith('/'):
            raise ValueError('无效页面路径')
        path = (album_root / relative).resolve()
        if album_root.resolve() not in path.parents: raise ValueError('页面超出画册目录')
        with Image.open(path) as source:
            images.append(source.convert('RGB'))
    combined = Image.new('RGB', (sum(i.width for i in images), max(i.height for i in images)), 'white')
    x = 0
    for image in images:
        combined.paste(image, (x, (combined.height - image.height) // 2)); x += image.width
        image.close()
    frame = Image.new('RGB', size, '#0b0f19')
    fitted = ImageOps.contain(combined, size, Image.Resampling.LANCZOS)
    frame.paste(fitted, ((size[0]-fitted.width)//2, (size[1]-fitted.height)//2))
    fitted.close(); combined.close()
    return frame

def write_video(resolved, target, report=lambda message: None, root=ROOT):
    if resolved['catalog']['mediaType'] != 'album': raise ValueError('仅支持 PPT 画册导出 MP4')
    album = resolved['album']
    aid = resolved['catalog']['albumId']
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', aid): raise ValueError('无效画册 ID')
    root = Path(root)
    album_root = (root / 'runtime-albums' / aid).resolve()
    if (root / 'runtime-albums').resolve() not in album_root.parents: raise ValueError('无效画册目录')
    executable = encoder()
    items = scenes(album)
    stay = max(1, min(30, float(album.get('viewer', {}).get('interval', 3000)) / 1000))
    final_stay = max(1, min(30, float(album.get('viewer', {}).get('loopDelay', 2500)) / 1000))
    durations = [stay] * len(items)
    durations[-1] = final_stay
    with tempfile.TemporaryDirectory(prefix='liveslides-mp4-') as temp:
        work = Path(temp)
        sequence = []
        for index, group in enumerate(items):
            report(f'生成高清画面 {index + 1}/{len(items)}')
            with render_scene(group, album_root) as frame: frame.save(work / f'frame-{index:04d}.png')
            sequence += [f"file 'frame-{index:04d}.png'", f'duration {durations[index]:.3f}']
        sequence.append(f"file 'frame-{len(items)-1:04d}.png'")
        (work / 'frames.txt').write_text('\n'.join(sequence), encoding='utf-8')
        report('正在编码 H.264 / MP4，请稍候…')
        command = [executable, '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-f', 'concat', '-safe', '1', '-i', str(work / 'frames.txt'),
                   '-vf', 'fps=30', '-t', str(sum(durations)), '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                   '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target)]
        result = subprocess.run(command, capture_output=True, timeout=900, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode: raise ValueError('FFmpeg 编码失败，请检查 libx264 支持及磁盘空间：' + result.stderr.decode('utf-8', errors='replace')[-1200:])
    return dict(width=1920, height=1080, fps=30, duration=sum(durations), scenes=len(items), transition='cut')

def start(resolved):
    if resolved['catalog']['mediaType'] != 'album': raise ValueError('仅支持 PPT 画册导出 MP4')
    encoder()
    if not ENCODER_SLOT.acquire(blocking=False): raise ValueError('已有 MP4 正在生成，请完成后再试')
    job_id = uuid4().hex
    with LOCK: JOBS[job_id] = dict(id=job_id, status='running', message='准备生成 MP4')
    def update(**values):
        with LOCK: JOBS[job_id].update(values)
    def run():
        target = ROOT / 'runtime-videos' / f'{job_id}.mp4'
        try:
            target.parent.mkdir(exist_ok=True)
            metadata = write_video(copy.deepcopy(resolved), target, lambda message: update(message=message))
            update(status='complete', message='MP4 已生成', **metadata)
        except Exception as error:
            target.unlink(missing_ok=True)
            update(status='failed', message=str(error))
        finally: ENCODER_SLOT.release()
    threading.Thread(target=run, daemon=True).start()
    return job_id

def handle(handler, respond, resolve):
    from urllib.parse import urlsplit
    path = urlsplit(handler.path).path
    if path != '/api/video-export' and not path.startswith('/api/video-export/'): return False
    try:
        if handler.command == 'POST' and path == '/api/video-export':
            length = int(handler.headers.get('Content-Length', 0))
            if not 0 < length <= 4096: raise ValueError('无效请求')
            payload = json.loads(handler.rfile.read(length))
            job_id = start(resolve(payload['tenantId'], payload['catalogId']))
            respond(handler, 202, {'id': job_id})
        elif handler.command == 'GET':
            match = re.fullmatch(r'/api/video-export/([a-f0-9]{32})(/download)?', path)
            if not match: raise LookupError()
            with LOCK: job = copy.deepcopy(JOBS.get(match[1]))
            if not job: raise LookupError()
            if not match[2]: respond(handler, 200, job)
            else:
                if job['status'] != 'complete': raise ValueError('MP4 尚未完成')
                target = ROOT / 'runtime-videos' / f"{job['id']}.mp4"
                with target.open('rb') as stream:
                    handler.send_response(200)
                    handler.send_header('Content-Type', 'video/mp4')
                    handler.send_header('Content-Disposition', 'attachment; filename="LiveSlides-1080p.mp4"')
                    handler.send_header('Content-Length', str(target.stat().st_size))
                    handler.send_header('Cache-Control', 'no-store')
                    handler.end_headers()
                    shutil.copyfileobj(stream, handler.wfile)
        else: respond(handler, 405, {'error': 'Method not allowed'})
    except (KeyError, ValueError, TypeError) as error: respond(handler, 400, {'error': str(error)})
    except (LookupError, FileNotFoundError): respond(handler, 404, {'error': '视频任务不存在'})
    return True
