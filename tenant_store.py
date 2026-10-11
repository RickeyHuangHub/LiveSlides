"""File-backed presentation configuration; not an authentication boundary."""
import json
import os
import re
import threading
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit

ROOT = Path(__file__).parent
STORE = ROOT / 'tenant-config.json'
LOCK = threading.RLock()

def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', value):
        raise ValueError('ID 只允许字母、数字、连字符和下划线，最长 80 位')
    return value

def media_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('资源地址格式错误')
    parsed = urlsplit(value)
    if value and not (value.startswith('/') and not value.startswith('//')) and not (parsed.scheme in ('https', 'http') and parsed.netloc):
        raise ValueError('资源地址仅支持 http(s) 或站内绝对路径')
    if any(c in value for c in ('\\', '\n', '\r', '"', '<', '>')):
        raise ValueError('资源地址包含非法字符')
    return value

def validate(data):
    if not isinstance(data, dict) or not isinstance(data.get('tenants'), list) or not isinstance(data.get('catalogs'), list):
        raise ValueError('需要 tenants 和 catalogs 数组')
    tenants, catalogs, seen = [], [], set()
    for raw in data['tenants']:
        tid = identifier(raw['id'])
        if tid in seen: raise ValueError('公司 ID 重复')
        seen.add(tid)
        name = raw['name']
        if not isinstance(name, str) or not name.strip() or len(name) > 160: raise ValueError('公司名不能为空，最长 160 字')
        color = raw.get('primaryColor', '#f36948')
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color): raise ValueError('主色调须为 #RRGGBB')
        slogan = raw.get('slogan', '')
        if not isinstance(slogan, str) or len(slogan) > 500: raise ValueError('标语最长 500 字')
        tenants.append(dict(id=tid, name=name.strip(), slogan=slogan, primaryColor=color,
                            logoUrl=media_url(raw.get('logoUrl', '')), backgroundUrl=media_url(raw.get('backgroundUrl', ''))))
    keys = set()
    for raw in data['catalogs']:
        tid, cid = identifier(raw['tenantId']), identifier(raw['id'])
        if tid not in seen: raise ValueError('画册引用了不存在的公司')
        if (tid, cid) in keys: raise ValueError('同一公司的画册 ID 重复')
        keys.add((tid, cid))
        kind = raw.get('mediaType', 'album')
        if kind not in ('album', 'video'): raise ValueError('mediaType 必须为 album 或 video')
        title = raw['title']
        if not isinstance(title, str) or not title.strip() or len(title) > 200: raise ValueError('画册标题不能为空，最长 200 字')
        aid = raw.get('albumId', '')
        video = media_url(raw.get('videoUrl', ''))
        if kind == 'album':
            identifier(aid)
            if not (ROOT / 'runtime-albums' / aid / 'album.json').is_file(): raise ValueError('指定的画册不存在')
        if kind == 'video' and not video: raise ValueError('请填写视频直链')
        catalogs.append(dict(id=cid, tenantId=tid, title=title.strip(), mediaType=kind, albumId=aid if kind == 'album' else '', videoUrl=video))
    return dict(tenants=tenants, catalogs=catalogs)

def read():
    with LOCK:
        if STORE.exists(): return json.loads(STORE.read_text(encoding='utf-8'))
        albums = sorted((ROOT / 'runtime-albums').glob('*/album.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        return {'tenants': [dict(id='default', name='我的公司', slogan='', primaryColor='#f36948', logoUrl='', backgroundUrl='')],
                'catalogs': [dict(id=p.parent.name, tenantId='default', title=json.loads(p.read_text(encoding='utf-8'))['title'], mediaType='album', albumId=p.parent.name, videoUrl='') for p in albums]}

def save(data):
    normalized = validate(data)
    with LOCK:
        temp = STORE.with_suffix('.' + uuid4().hex + '.tmp')
        try:
            temp.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(temp, STORE)
        finally:
            temp.unlink(missing_ok=True)
    return normalized

def resolve(tid, cid):
    identifier(tid); identifier(cid)
    data = read()
    tenant = next((x for x in data['tenants'] if x['id'] == tid), None)
    catalog = next((x for x in data['catalogs'] if x['tenantId'] == tid and x['id'] == cid), None)
    if not tenant or not catalog: raise LookupError('公司或画册不存在')
    result = dict(tenant=tenant, catalog=catalog)
    if catalog['mediaType'] == 'album':
        aid = identifier(catalog['albumId'])
        result.update(album=json.loads((ROOT / 'runtime-albums' / aid / 'album.json').read_text(encoding='utf-8')), base=f'/api/albums/{aid}/', id=aid)
    return result

def handle(handler, respond, base_url):
    path = urlsplit(handler.path).path
    if path not in ('/api/config', '/api/catalog-publish', '/api/album-list') and not path.startswith('/api/view/'):
        return False
    try:
        if handler.command == 'GET' and path == '/api/config':
            result = read()
        elif handler.command == 'GET' and path == '/api/album-list':
            result = [dict(id=p.parent.name, title=json.loads(p.read_text(encoding='utf-8'))['title']) for p in (ROOT / 'runtime-albums').glob('*/album.json')]
        elif handler.command == 'GET' and path.startswith('/api/view/'):
            parts = path.split('/')
            if len(parts) != 5: raise LookupError('无效的播放地址')
            result = resolve(parts[3], parts[4])
        elif handler.command == 'POST' and path in ('/api/config', '/api/catalog-publish'):
            size = int(handler.headers.get('Content-Length', 0))
            if not 0 < size <= 262144: raise ValueError('配置请求大小须在 256KB 以内')
            data = json.loads(handler.rfile.read(size))
            if path == '/api/config': result = save(data)
            else:
                resolved = resolve(data['tenantId'], data['catalogId'])
                origin, mode = base_url()
                result = dict(url=f"{origin}/v/{resolved['tenant']['id']}/{resolved['catalog']['id']}", baseUrl=origin, addressMode=mode, status='published')
        else:
            respond(handler, 405, {'error': 'Method not allowed'}); return True
        respond(handler, 200, result)
    except (LookupError, FileNotFoundError): respond(handler, 404, {'error': '公司或画册不存在'})
    except (ValueError, TypeError, AttributeError) as error: respond(handler, 400, {'error': str(error)})
    return True
