"""Export a single-file, file:// compatible player without network dependencies."""
import base64
import copy
import html
import json
import re
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).parent
MAX_ASSETS = 256 * 1024 * 1024
IMAGE_TYPES = {'.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif'}

def make_document(resolved, root=ROOT):
    """Build the complete, self-contained HTML playback document."""
    root = Path(root)
    bundle = root / 'offline-dist' / 'player.js'
    stylesheet = root / 'offline-dist' / 'player.css'
    if not bundle.is_file() or not stylesheet.is_file():
        raise ValueError('离线播放器尚未构建，请运行 npm run build:offline')
    data = copy.deepcopy(resolved)
    if data['catalog']['mediaType'] != 'album':
        raise ValueError('首版离线包仅支持 PPT 画册，暂不支持视频直链')
    aid = data['catalog']['albumId']
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', aid):
        raise ValueError('无效画册 ID')
    album_root = (root / 'runtime-albums' / aid).resolve()
    if (root / 'runtime-albums').resolve() not in album_root.parents:
        raise ValueError('画册目录超出允许范围')
    total, cache = 0, {}

    def embed(path, allowed_root):
        nonlocal total
        allowed_root = allowed_root.resolve()
        path = path.resolve()
        if allowed_root not in path.parents or not path.is_file():
            raise ValueError('画册资源不存在或超出允许目录')
        if path.suffix.lower() not in IMAGE_TYPES:
            raise ValueError('离线图片仅支持 WebP、PNG、JPEG、GIF')
        if path not in cache:
            total += path.stat().st_size
            if total > MAX_ASSETS: raise ValueError('离线图片总量超过 256MB，请拆分画册')
            content = path.read_bytes()
            cache[path] = f'data:{IMAGE_TYPES[path.suffix.lower()]};base64,' + base64.b64encode(content).decode('ascii')
        return cache[path]

    def page_asset(relative):
        if not isinstance(relative, str) or not relative or urlsplit(relative).scheme or relative.startswith(('/', '\\')) or '\\' in relative:
            raise ValueError('无效的画册资源路径')
        return embed(album_root / relative, album_root)

    for page in data['album']['pages']:
        page['src'] = page_asset(page['src'])
        if page.get('thumbnail'): page['thumbnail'] = page_asset(page['thumbnail'])
    if not data['album']['pages']: raise ValueError('画册没有可播放的页面')
    for key in ('logoUrl', 'backgroundUrl'):
        url = data['tenant'].get(key, '')
        if not url: continue
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc:
            raise ValueError('离线包不能引用网络 Logo 或背景。请先使用本站图片路径，或清空该公司对应图片配置后导出。')
        path = unquote(parsed.path)
        prefix = f'/api/albums/{aid}/'
        if path.startswith(prefix):
            data['tenant'][key] = page_asset(path[len(prefix):])
        elif path.startswith('/') and not path.startswith('/api/'):
            data['tenant'][key] = embed(root / 'public' / path.lstrip('/'), root / 'public')
        else:
            raise ValueError('品牌图片需为本站 public 目录图片或当前画册图片')
    data['base'] = ''
    data['album']['title'] = data['catalog']['title']
    data['album']['viewer'].update(autoplay=True, loop=True)
    # Drop unused remote metadata; no sharing UI exists inside offline packages.
    data['album'].pop('share', None)
    data['catalog']['videoUrl'] = ''
    music_url = data['catalog'].get('musicUrl', '')
    if music_url:
        match = re.fullmatch(r'/api/music/([A-Za-z0-9_-]+)/([A-Za-z0-9_-]+)', music_url)
        if not match or match.groups() != (data['tenant']['id'], data['catalog']['id']):
            raise ValueError('背景音乐与当前公司或画册配置不匹配')
        music_path = (root / 'runtime-music' / match[1] / f'{match[2]}.mp3').resolve()
        music_root = (root / 'runtime-music' / match[1]).resolve()
        if music_root not in music_path.parents or not music_path.is_file():
            raise ValueError('背景音乐文件不存在，请重新上传')
        if music_path.stat().st_size > 25 * 1024 * 1024:
            raise ValueError('背景音乐超过 25 MB，无法嵌入离线包')
        data['catalog']['musicUrl'] = 'data:audio/mpeg;base64,' + base64.b64encode(music_path.read_bytes()).decode('ascii')
    payload = json.dumps(data, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    script = bundle.read_text(encoding='utf-8').replace('</script', '<\\/script')
    css = stylesheet.read_text(encoding='utf-8').replace('</style', '<\\/style')
    title = html.escape(data['catalog']['title'])
    document = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; media-src data:; base-uri 'none'; form-action 'none'">
<title>{title} · 离线画册</title><style>{css}</style></head>
<body><div id="root"></div><noscript>请使用允许 JavaScript 的现代浏览器打开画册。</noscript>
<script>window.__LIVESLIDES_OFFLINE__={payload};</script><script>{script}</script></body></html>'''
    return document

def make_html(resolved, root=ROOT):
    """Caller owns and must close the returned seekable HTML file."""
    result = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode='w+b')
    try:
        result.write(make_document(resolved, root).encode('utf-8'))
        result.seek(0)
        return result
    except Exception:
        result.close()
        raise

def make_package(resolved, root=ROOT):
    """Caller owns and must close returned seekable zip file."""
    document = make_document(resolved, root)
    title = resolved['catalog']['title']
    instructions = f'''{title} — 离线播放包

1. 将 ZIP 完整解压到电脑上的文件夹，不要直接在压缩包预览中打开。
2. 双击“开始播放.html”，用 Microsoft Edge 或 Chrome 打开。
3. 页面加载完成后自动循环播放。鼠标移动或轻触可唤出暂停、全屏按钮。
4. 全屏需要点击一次“全屏”（或浏览器 F11），Esc 可退出。
5. 无需网络、Python、Node、安装程序或后台服务；关闭浏览器即可停止。

所有图片保持原始高清 WebP/PNG/JPEG 字节，不重新压缩。
此包是 HTML 画册，不是 MP4。它是导出时的内容快照；在线更新后需重新导出。
整个画册已嵌入 HTML，可只复制“开始播放.html”到另一台电脑使用。
现代浏览器是唯一运行依赖；不要使用邮件附件预览器或禁用脚本的预览程序。
'''
    result = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode='w+b')
    try:
        with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr('开始播放.html', document.encode('utf-8'))
            archive.writestr('使用说明.txt', instructions.encode('utf-8-sig'))
        result.seek(0)
        return result
    except Exception:
        result.close()
        raise
