import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import QRCode from 'qrcode';
import './tenant.css';

const Context = createContext(null);
/** @typedef {import('./config').TenantConfig} TenantConfig */
/** @typedef {import('./config').CatalogConfig} CatalogConfig */
export const useTenant = () => useContext(Context);
export function TenantBrand() {
  const { tenant } = useTenant() || {};
  return <div className="brand tenant-brand">{tenant?.logoUrl ? <img src={tenant.logoUrl} alt=""/> : <b>{tenant?.name?.slice(0, 1) || 'L'}</b>}<span>{tenant?.name || 'LiveSlides'}{tenant?.slogan && <small>{tenant.slogan}</small>}</span></div>;
}
async function api(path, data) {
  const response = await fetch(path, data === undefined ? { cache: 'no-store' } : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '请求失败');
  return result;
}
async function copyLink(url) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(url);
  const field = document.createElement('textarea');
  field.value = url; field.style.position = 'fixed'; field.style.opacity = '0';
  document.body.appendChild(field); field.select();
  try { if (!document.execCommand('copy')) throw new Error('请手动复制链接'); }
  finally { field.remove(); }
}
async function prepareCatalog(context, albumId) {
  if (!context) throw new Error('公司配置尚未载入');
  const { tenant, catalog } = context;
  if (!tenant) throw new Error('请先选择公司');
  let target = catalog;
  if (albumId && (catalog?.mediaType !== 'album' || catalog.albumId !== albumId)) {
    const source = await api(`/api/albums/${encodeURIComponent(albumId)}/album.json`);
    target = { id: albumId, tenantId: tenant.id, title: source.title, mediaType: 'album', albumId, videoUrl: '' };
    await context.attach(target);
  }
  if (!target) throw new Error('请先创建并保存画册配置');
  await context.persist?.();
  return { tenantId: tenant.id, catalogId: target.id };
}
export async function publishConfigured(context, albumId) {
  return api('/api/catalog-publish', await prepareCatalog(context, albumId));
}
export async function downloadOffline(context, albumId) {
  const identity = await prepareCatalog(context, albumId);
  const response = await fetch('/api/offline-export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(identity) });
  if (!response.ok) { const result = await response.json(); throw new Error(result.error || '离线打包失败'); }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url; link.download = `${identity.tenantId}-${identity.catalogId}-offline.zip`;
  document.body.appendChild(link); link.click(); link.remove();
  // Let the browser finish consuming the blob before revoking its URL.
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function Theme({ tenant, children }) {
  return <div className="tenant-theme" style={{ '--tenant-primary': tenant?.primaryColor || '#f36948', '--tenant-background': tenant?.backgroundUrl ? `url("${tenant.backgroundUrl}")` : 'none' }}>{children}</div>;
}

export function VideoExportButton({ albumId }) {
  const context = useTenant();
  const [job, setJob] = useState(null), [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  useEffect(() => {
    if (!job || job.status !== 'running') return;
    let cancelled = false, timer;
    const poll = async () => {
      try {
        const result = await api(`/api/video-export/${job.id}`);
        if (cancelled) return;
        setMessage(result.message);
        if (result.status === 'running') timer = setTimeout(poll, 1500);
        else { setJob(result); setBusy(false); }
      } catch (error) { if (!cancelled) { setBusy(false); setMessage(error.message); } }
    };
    poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [job?.id, job?.status]);
  if (context?.offline) return null;
  return <span className="video-export"><button disabled={busy || (!albumId && context?.catalog?.mediaType !== 'album')} onClick={async () => {
    setBusy(true); setJob(null); setMessage('准备 MP4…');
    try { const identity = await prepareCatalog(context, albumId); const result = await api('/api/video-export', identity); setJob({ id: result.id, status: 'running' }); }
    catch (error) { setMessage(error.message); setBusy(false); }
  }}>{busy ? 'MP4 生成中…' : '导出 MP4'}</button>{message && <small role="status">{message}</small>}{job?.status === 'complete' && <a href={`/api/video-export/${job.id}/download`} download>下载 MP4（1080p）</a>}</span>;
}

function VideoPlayer({ catalog }) {
  const { tenant } = useTenant();
  const [visible, setVisible] = useState(false), [error, setError] = useState('');
  const video = useRef(null), timer = useRef(null);
  const reveal = () => { setVisible(true); clearTimeout(timer.current); timer.current = setTimeout(() => setVisible(false), 2500); };
  useEffect(() => { video.current?.play().catch(() => setError('点击播放开始演示')); return () => clearTimeout(timer.current); }, [catalog.videoUrl]);
  return <div className="tenant-video" onPointerMove={reveal} onPointerDown={reveal} onKeyDown={reveal}>
    <video ref={video} src={catalog.videoUrl} autoPlay muted loop playsInline onError={() => setError('视频无法加载，请检查直链及浏览器支持的编码。')} />
    <header className={visible ? 'visible' : ''}>{tenant.logoUrl && <img className="tenant-logo" src={tenant.logoUrl} alt={tenant.name}/>}<span>{tenant.name} · {catalog.title} {tenant.slogan}</span><button onClick={() => { if (video.current.paused) video.current.play().then(() => setError('')).catch(() => setError('无法播放')); else video.current.pause(); }}>播放 / 暂停</button><button onClick={() => { video.current.muted = !video.current.muted; }}>声音开关</button><button onClick={() => { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen?.().catch(() => setError('请使用浏览器全屏功能')); }}>全屏</button></header>
    {error && <button className="video-error" onClick={() => video.current.play().then(() => setError('')).catch(() => {})}>{error}</button>}
  </div>;
}

function Landing({ Viewer, tenantId, catalogId }) {
  const [resolved, setResolved] = useState(null), [error, setError] = useState('');
  useEffect(() => {
    let cancelled = false;
    api(`/api/view/${encodeURIComponent(tenantId)}/${encodeURIComponent(catalogId)}`).then(data => { if (!cancelled) { setResolved(data); document.title = `${data.catalog.title} · ${data.tenant.name}`; } }).catch(e => { if (!cancelled) setError(e.message); });
    document.documentElement.requestFullscreen?.().catch(() => {});
    return () => { cancelled = true; };
  }, [tenantId, catalogId]);
  if (error) return <main className="config-error" role="alert">无法打开画册：{error}</main>;
  if (!resolved) return <main className="config-error">正在载入公司配置…</main>;
  const { tenant, catalog, album } = resolved;
  return <Context.Provider value={{ tenant, catalog }}><Theme tenant={tenant}>{catalog.mediaType === 'video' ? <VideoPlayer catalog={catalog}/> : <Viewer {...resolved} album={{ ...album, title: catalog.title, viewer: { ...album.viewer, autoplay: true, loop: true } }} onBack={() => location.assign('/')} />}</Theme></Context.Provider>;
}

export default function TenantApp({ CreatorApp, Viewer }) {
  if (window.__LIVESLIDES_OFFLINE__) return <OfflinePlayer Viewer={Viewer} data={window.__LIVESLIDES_OFFLINE__}/>;
  const route = location.pathname.match(/^\/v\/([^/]+)\/([^/]+)\/?$/);
  if (route) return <Landing Viewer={Viewer} tenantId={route[1]} catalogId={route[2]}/>;
  if (location.pathname !== '/') return <main className="config-error">页面不存在</main>;
  return <Studio CreatorApp={CreatorApp}/>;
}

function OfflinePlayer({ Viewer, data }) {
  const [album] = useState(() => ({ ...data.album, title: data.catalog.title, viewer: { ...data.album.viewer, autoplay: true, loop: true } }));
  useEffect(() => { document.title = `${data.catalog.title} · 离线画册`; }, [data.catalog.title]);
  return <Context.Provider value={{ tenant: data.tenant, catalog: data.catalog, offline: true }}><Theme tenant={data.tenant}><div className="offline-player"><Viewer {...data} album={album} onBack={() => {}}/></div></Theme></Context.Provider>;
}

function Studio({ CreatorApp }) {
  const [store, setStore] = useState(null), [tenantId, setTenantId] = useState(''), [catalogId, setCatalogId] = useState('');
  const [albums, setAlbums] = useState([]), [message, setMessage] = useState(''), [json, setJson] = useState(''), [share, setShare] = useState(null), [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(!location.search);
  const latest = useRef(null);
  const update = data => { latest.current = data; setStore(data); };
  useEffect(() => { Promise.all([api('/api/config'), api('/api/album-list')]).then(([data, list]) => { update(data); setAlbums(list); const legacyId = new URLSearchParams(location.search).get('album'); const selected = data.catalogs.find(c => c.albumId === legacyId) || data.catalogs[0]; setTenantId(selected?.tenantId || data.tenants[0]?.id || ''); setCatalogId(selected?.id || ''); }).catch(e => setMessage(e.message)); }, []);
  const tenant = store?.tenants.find(t => t.id === tenantId);
  const catalog = store?.catalogs.find(c => c.tenantId === tenantId && c.id === catalogId);
  const persist = async () => { const saved = await api('/api/config', latest.current); update(saved); return saved; };
  const attach = async target => { const data = latest.current; const saved = await api('/api/config', { ...data, catalogs: [...data.catalogs.filter(c => !(c.tenantId === target.tenantId && c.id === target.id)), target] }); update(saved); setCatalogId(target.id); };
  const changeTenant = (key, value) => update({ ...store, tenants: store.tenants.map(t => t.id === tenantId ? { ...t, [key]: value } : t) });
  const changeCatalog = (key, value) => update({ ...store, catalogs: store.catalogs.map(c => c.tenantId === tenantId && c.id === catalogId ? { ...c, [key]: value } : c) });
  async function run(action) { setBusy(true); setMessage(''); try { await action(); } catch (e) { setMessage(e.message); } finally { setBusy(false); } }
  async function publish() { await persist(); if (!catalog) throw new Error('请先添加画册'); const result = await api('/api/catalog-publish', { tenantId, catalogId }); setShare({ ...result, qr: await QRCode.toDataURL(result.url, { width: 1024, margin: 4, errorCorrectionLevel: 'H' }) }); }
  function addTenant() { const id = `company-${Date.now()}`; update({ ...store, tenants: [...store.tenants, { id, name: '新公司', slogan: '', logoUrl: '', backgroundUrl: '', primaryColor: '#336699' }] }); setTenantId(id); setCatalogId(''); }
  function addCatalog() { const id = `catalog-${Date.now()}`; update({ ...store, catalogs: [...store.catalogs, { id, tenantId, title: '新画册', mediaType: 'album', albumId: albums[0]?.id || '', videoUrl: '' }] }); setCatalogId(id); }
  if (!store) return <main className="config-error">{message || '正在载入配置…'}</main>;
  const context = { tenant, catalog, persist, attach };
  return <Context.Provider value={context}><Theme tenant={tenant}><button className="config-toggle" onClick={() => setOpen(!open)}>公司配置</button>
    <div className={open ? 'config-layout' : ''}>{open && <aside className="config-sidebar"><h2>公司与画册</h2><p>配置独立于 PPT 内容；保存后分享页生效。</p>
      <fieldset disabled={busy}><label>公司预设<select value={tenantId} onChange={e => { setTenantId(e.target.value); setCatalogId(store.catalogs.find(c => c.tenantId === e.target.value)?.id || ''); }}>{store.tenants.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label><button onClick={addTenant}>＋ 公司</button>
      {tenant && <><small>公司 ID：{tenant.id}</small>{[['name', '公司名称'], ['slogan', '标语'], ['logoUrl', 'Logo URL'], ['backgroundUrl', '背景图 URL'], ['primaryColor', '主色调']].map(([key, label]) => <label key={key}>{label}<input type={key === 'primaryColor' ? 'color' : 'text'} value={tenant[key]} onChange={e => changeTenant(key, e.target.value)}/></label>)}<div className="brand-preview">{tenant.logoUrl && <img src={tenant.logoUrl} alt="公司 Logo"/>}<strong>{tenant.name}</strong><p>{tenant.slogan}</p></div>
      <label>画册<select value={catalogId} onChange={e => setCatalogId(e.target.value)}><option value="">请选择</option>{store.catalogs.filter(c => c.tenantId === tenantId).map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</select></label><button onClick={addCatalog}>＋ 画册</button></>}
      {catalog && <><small>画册 ID：{catalog.id}</small><label>标题<input value={catalog.title} onChange={e => changeCatalog('title', e.target.value)}/></label><label>内容类型<select value={catalog.mediaType} onChange={e => changeCatalog('mediaType', e.target.value)}><option value="album">PPT 画册</option><option value="video">视频直链</option></select></label>{catalog.mediaType === 'album' ? <label>绑定已转换画册<select value={catalog.albumId} onFocus={() => api('/api/album-list').then(setAlbums).catch(e => setMessage(e.message))} onChange={e => changeCatalog('albumId', e.target.value)}><option value="">请选择</option>{albums.map(a => <option key={a.id} value={a.id}>{a.title}</option>)}</select></label> : <label>视频直链<input type="url" value={catalog.videoUrl} onChange={e => changeCatalog('videoUrl', e.target.value)}/></label>}<p className="route-preview">/v/{tenantId}/{catalogId}</p></>}
      <button onClick={() => run(async () => { await persist(); setMessage('配置已保存'); })}>保存配置</button><button disabled={!catalog} onClick={() => run(async () => { await persist(); location.assign(`/v/${tenantId}/${catalogId}`); })}>打开播放页</button><button disabled={!catalog} onClick={() => run(publish)}>发布 / 二维码</button>
      <button disabled={!catalog || catalog.mediaType !== 'album'} onClick={() => run(async () => { setMessage('正在生成离线播放包，请稍候…'); await downloadOffline(context); setMessage('已发起 ZIP 下载。解压后双击“开始播放.html”，即可离线循环播放。'); })}>{busy ? '处理中…' : '下载离线播放包'}</button><p>离线包仅支持 PPT 画册；无需安装程序，解压后双击 HTML 播放。</p>
      <VideoExportButton key={`${tenantId}/${catalogId}`}/><p>MP4：1080p 静态切页，无音轨；不是卷页录屏。循环需播放器开启。</p>
      <details><summary>JSON 配置导入 / 导出</summary><button onClick={() => setJson(JSON.stringify(store, null, 2))}>载入当前配置</button><textarea aria-label="JSON 配置" value={json} onChange={e => setJson(e.target.value)}/><button onClick={() => run(async () => { const saved = await api('/api/config', JSON.parse(json)); update(saved); setTenantId(saved.tenants[0]?.id || ''); setCatalogId(saved.catalogs[0]?.id || ''); setMessage('JSON 配置已校验并保存'); })}>校验并保存 JSON</button></details></fieldset><p role="status">{message}</p></aside>}
      <div className="creator-content"><CreatorApp key={tenantId}/></div></div>
    {share && <div className="tenant-modal" role="dialog" aria-modal="true" aria-label="发布结果"><section><button onClick={() => setShare(null)}>关闭</button><h2>发布完成</h2><img src={share.qr} alt="画册分享二维码"/><a href={share.url} target="_blank" rel="noreferrer">{share.url}</a><button onClick={() => copyLink(share.url).then(() => setMessage('链接已复制')).catch(() => setMessage('请手动复制上方链接'))}>复制链接</button><a download={`${tenantId}-${catalogId}-qr.png`} href={share.qr}>下载二维码图片 (PNG)</a><p role="status">{message}</p><p>{share.addressMode === 'lan' ? '手机需连接同一局域网，电脑服务需保持运行。' : '请确保正式域名已部署并可访问。'}</p></section></div>}
  </Theme></Context.Provider>;
}
