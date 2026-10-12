"""Small local development API for the Phase 1 creator flow."""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import tempfile
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.parse import quote
from uuid import uuid4

from converter.convert import convert, validate_pptx
import tenant_store
import offline_export
import video_export

ROOT = Path(__file__).parent
ALBUMS = ROOT / "runtime-albums"
TEMP_ROOT = ROOT / ".tmp"
ALBUMS.mkdir(exist_ok=True)
TEMP_ROOT.mkdir(exist_ok=True)
MAX_UPLOAD = 50 * 1024 * 1024


def detect_lan_ip() -> str:
    """Return the LAN address used for outbound connections, with loopback fallback."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            address = probe.getsockname()[0]
            if address and not address.startswith(("127.", "169.254.")):
                return address
    except OSError:
        pass
    try:
        candidates = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        for candidate in candidates:
            address = candidate[4][0]
            if address and not address.startswith(("127.", "169.254.")):
                return address
    except OSError:
        pass
    return "127.0.0.1"


def public_base_url() -> tuple[str, str]:
    """Resolve the share origin, preferring the configured production URL."""
    configured = os.environ.get("LIVESLIDES_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured, "configured"
    port = os.environ.get("LIVESLIDES_VIEWER_PORT", "5193").strip() or "5193"
    return f"http://{detect_lan_ip()}:{port}", "lan"


def json_response(handler: BaseHTTPRequestHandler, status: int, value: dict) -> None:
    payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


class Handler(BaseHTTPRequestHandler):
    server_version = "LiveSlides/0.1"

    def do_POST(self) -> None:
        if video_export.handle(self, json_response, tenant_store.resolve): return
        if urlparse(self.path).path == '/api/music-upload':
            self.upload_music()
            return
        if urlparse(self.path).path == '/api/offline-export':
            self.export_offline()
            return
        if tenant_store.handle(self, json_response, public_base_url): return
        route = urlparse(self.path).path
        if route == "/api/publish":
            self.publish_album()
            return
        if route == "/api/validate":
            self.validate_file()
            return
        if route != "/api/convert":
            json_response(self, 404, {"error": "Not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD:
            json_response(self, 413, {"error": "Upload is empty or exceeds the 50 MB limit"})
            return
        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            json_response(self, 400, {"error": "Expected multipart/form-data"})
            return
        message = BytesParser(policy=default).parsebytes((f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n").encode() + body)
        file_part = next((part for part in message.walk() if part.get_filename()), None)
        if not file_part:
            json_response(self, 400, {"error": "No PPTX file was provided"})
            return
        filename = Path(file_part.get_filename()).name
        if not filename.lower().endswith(".pptx"):
            json_response(self, 400, {"error": "Only .pptx files are accepted"})
            return
        page_mode_part = next((part for part in message.walk() if part.get_param("name", header="content-disposition") == "pageMode"), None)
        mode_part = next((part for part in message.walk() if part.get_param("name", header="content-disposition") == "mode"), None)
        mode_source = page_mode_part or mode_part
        mode = (mode_source.get_payload(decode=True) or b"cover-inner-split").decode("utf-8", "ignore") if mode_source else "cover-inner-split"
        if mode not in {"single-slide", "cover-inner-split", "split-all", "left-cover-spread"}:
            json_response(self, 400, {"error": "Invalid page mode"})
            return
        interval_part = next((part for part in message.walk() if part.get_param("name", header="content-disposition") == "interval"), None)
        transition_part = next((part for part in message.walk() if part.get_param("name", header="content-disposition") == "transition"), None)
        try:
            interval = int((interval_part.get_payload(decode=True) or b"3000").decode("utf-8", "ignore")) if interval_part else 3000
        except ValueError:
            interval = 3000
        transition = (transition_part.get_payload(decode=True) or b"page-curl").decode("utf-8", "ignore") if transition_part else "page-curl"
        if interval not in (3000, 5000) or transition not in {"page-curl", "slide"}:
            json_response(self, 400, {"error": "Invalid Viewer timing or transition"})
            return
        album_id = f"album-{uuid4().hex[:10]}"
        album_dir = ALBUMS / album_id
        with tempfile.TemporaryDirectory(prefix="liveslides-upload-", dir=TEMP_ROOT) as temp:
            source = Path(temp) / filename
            source.write_bytes(file_part.get_payload(decode=True) or b"")
            try:
                convert(source, album_dir, mode, interval=interval, transition=transition)
            except Exception as error:
                shutil.rmtree(album_dir, ignore_errors=True)
                json_response(self, 422, {"error": str(error)})
                return
        album = json.loads((album_dir / "album.json").read_text(encoding="utf-8"))
        json_response(self, 200, {"id": album_id, "album": album, "base": f"/api/albums/{album_id}/"})

    def validate_file(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD:
            json_response(self, 413, {"error": "文件为空或超过 50MB 上限"})
            return
        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            json_response(self, 400, {"error": "Expected multipart/form-data"})
            return
        message = BytesParser(policy=default).parsebytes((f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n").encode() + body)
        file_part = next((part for part in message.walk() if part.get_filename()), None)
        if not file_part:
            json_response(self, 400, {"error": "No PPTX file was provided"})
            return
        filename = Path(file_part.get_filename()).name
        data = file_part.get_payload(decode=True) or b""
        if not filename.lower().endswith(".pptx"):
            json_response(self, 400, {"error": "只接受 .pptx 文件"})
            return
        with tempfile.TemporaryDirectory(prefix="liveslides-validate-", dir=TEMP_ROOT) as temp:
            source = Path(temp) / filename
            source.write_bytes(data)
            try:
                visible = validate_pptx(source, max_mb=50)
            except Exception as error:
                json_response(self, 422, {"error": str(error)})
                return
        json_response(self, 200, {"valid": True, "filename": filename, "bytes": len(data), "visibleSlides": len(visible)})

    def publish_album(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            album_id = str(payload["id"])
        except (ValueError, KeyError, json.JSONDecodeError):
            json_response(self, 400, {"error": "A valid album id is required"})
            return
        album_dir = (ALBUMS / album_id).resolve()
        if ALBUMS.resolve() not in album_dir.parents or not (album_dir / "album.json").is_file():
            json_response(self, 404, {"error": "Album not found"})
            return
        base_url, address_mode = public_base_url()
        configs = tenant_store.read()
        matches = [c for c in configs['catalogs'] if c.get('albumId') == album_id]
        if len(matches) != 1:
            json_response(self, 409, {'error': '请在公司配置中选择画册后发布，以确定公司和画册路由'})
            return
        catalog = matches[0]
        public_url = f"{base_url}/v/{catalog['tenantId']}/{catalog['id']}"
        published = {"id": album_id, "url": public_url, "baseUrl": base_url, "addressMode": address_mode}
        (album_dir / "published.json").write_text(json.dumps(published, ensure_ascii=False, indent=2), encoding="utf-8")
        json_response(self, 200, {**published, "status": "published"})

    def export_offline(self) -> None:
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 4096: raise ValueError('无效的导出请求')
            payload = json.loads(self.rfile.read(size))
            resolved = tenant_store.resolve(payload['tenantId'], payload['catalogId'])
            package = offline_export.make_package(resolved)
        except (KeyError, ValueError, TypeError) as error:
            json_response(self, 400, {'error': str(error)})
            return
        except (LookupError, FileNotFoundError):
            json_response(self, 404, {'error': '公司、画册或离线资源不存在'})
            return
        except OSError:
            json_response(self, 500, {'error': '无法读取离线资源，请检查磁盘与文件权限'})
            return
        with package:
            package.seek(0, 2)
            length = package.tell()
            package.seek(0)
            filename = quote(f"{resolved['tenant']['id']}-{resolved['catalog']['id']}-offline.zip")
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Disposition', f"attachment; filename=\"liveslides-offline.zip\"; filename*=UTF-8''{filename}")
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(length))
            self.end_headers()
            shutil.copyfileobj(package, self.wfile)

    def do_GET(self) -> None:
        if video_export.handle(self, json_response, tenant_store.resolve): return
        music_match = re.fullmatch(r'/api/music/([\w-]+)/([\w-]+)', urlparse(self.path).path)
        if music_match:
            self.serve_music(*music_match.groups())
            return
        if tenant_store.handle(self, json_response, public_base_url): return
        path = unquote(urlparse(self.path).path)
        match = re.fullmatch(r"/api/albums/([\w-]+)/(.*)", path)
        if not match:
            json_response(self, 404, {"error": "Not found"})
            return
        album_id, relative = match.groups()
        target = (ALBUMS / album_id / relative).resolve()
        root = (ALBUMS / album_id).resolve()
        if (root not in target.parents and target != root) or not target.is_file():
            json_response(self, 404, {"error": "Asset not found"})
            return
        content = target.read_bytes()
        content_type = "application/json" if target.suffix == ".json" else "image/webp" if target.suffix == ".webp" else "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def upload_music(self) -> None:
        length = int(self.headers.get('Content-Length', '0'))
        if length <= 0 or length > 25 * 1024 * 1024:
            json_response(self, 413, {'error': 'MP3 文件须小于 25 MB'})
            return
        content_type = self.headers.get('Content-Type', '')
        if not content_type.startswith('multipart/form-data'):
            json_response(self, 400, {'error': '请上传 MP3 文件'})
            return
        message = BytesParser(policy=default).parsebytes((f'Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n').encode() + self.rfile.read(length))
        parts = {part.get_param('name', header='content-disposition'): part for part in message.walk() if part.get_param('name', header='content-disposition')}
        file_part = parts.get('file')
        try:
            tid = tenant_store.identifier((parts['tenantId'].get_payload(decode=True) or b'').decode())
            cid = tenant_store.identifier((parts['catalogId'].get_payload(decode=True) or b'').decode())
            resolved = tenant_store.resolve(tid, cid)
            if resolved['catalog']['mediaType'] != 'album': raise ValueError('背景音乐仅适用于 PPT 画册')
            if not file_part or not str(file_part.get_filename() or '').lower().endswith('.mp3'): raise ValueError('目前仅支持 MP3 音频')
            data = file_part.get_payload(decode=True) or b''
            if not data or not (data.startswith(b'ID3') or (len(data) > 1 and data[0] == 0xff and data[1] & 0xe0 == 0xe0)):
                raise ValueError('文件内容不像有效的 MP3 音频')
        except (KeyError, ValueError, LookupError) as error:
            json_response(self, 400, {'error': str(error) or '画册配置无效'})
            return
        folder = ROOT / 'runtime-music' / tid
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f'{cid}.mp3').write_bytes(data)
        json_response(self, 200, {'musicUrl': f'/api/music/{tid}/{cid}', 'bytes': len(data)})

    def serve_music(self, tid: str, cid: str) -> None:
        try:
            resolved = tenant_store.resolve(tid, cid)
            if resolved['catalog'].get('musicUrl') != f'/api/music/{tid}/{cid}': raise LookupError()
            path = ROOT / 'runtime-music' / tid / f'{cid}.mp3'
            content = path.read_bytes()
        except (LookupError, FileNotFoundError):
            json_response(self, 404, {'error': '背景音乐不存在'})
            return
        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpeg')
        self.send_header('Cache-Control', 'public, max-age=31536000, immutable')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args) -> None:
        print(f"[LiveSlides API] {format % args}")


if __name__ == "__main__":
    print("LiveSlides API listening at http://127.0.0.1:8787")
    ThreadingHTTPServer(("127.0.0.1", 8787), Handler).serve_forever()
