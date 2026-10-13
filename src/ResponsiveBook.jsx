import React, { useEffect, useRef, useState } from 'react';
import { PageFlip } from 'page-flip';
import QRCode from 'qrcode';
import { useTenant, publishConfigured, downloadOffline, VideoExportButton, MusicToggle } from './TenantApp';
import './responsive-book.css';

export default function ResponsiveBook({ album, base, id, onBack }) {
  const tenantContext = useTenant();
  const pages = album.pages;
  const [viewport, setViewport] = useState({ w: innerWidth, h: innerHeight });
  const single = viewport.w <= 768 || viewport.h > viewport.w;
  const [index, setIndex] = useState(0);
  const [closed, setClosed] = useState(true);
  const [opening, setOpening] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  const [visible, setVisible] = useState(false);
  const [hidden, setHidden] = useState(document.hidden);
  const [paused, setPaused] = useState(!album.viewer.autoplay);
  const [idle, setIdle] = useState(false);
  const [share, setShare] = useState(null);
  const [publishing, setPublishing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [drag, setDrag] = useState(0);
  const [backgrounds, setBackgrounds] = useState([base + pages[0].src, base + pages[0].src]);
  const [activeBackground, setActiveBackground] = useState(0);
  const host = useRef(null), engine = useRef(null), current = useRef(index);
  const hideTimer = useRef(), idleTimer = useRef(), openingTimer = useRef(), touch = useRef(null);
  current.current = index;
  const duration = album.viewer.flippingTime ?? 1000;
  const ratio = pages[0].width / pages[0].height;
  const pageHeight = Math.min(viewport.h * .85, (viewport.w - 32) / (ratio * (single ? 1 : 2)));
  const pageWidth = pageHeight * ratio;
  const coverHeight = Math.min(viewport.h * .85, Math.min(viewport.w * .94, viewport.w - 32) / ratio);
  const last = single ? pages.length - 1 : pages.length - 2;

  function reveal() {
    setVisible(true); clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => setVisible(false), 2500);
  }
  function interact() {
    reveal(); setIdle(true); clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => setIdle(false), album.viewer.idleResume ?? 12000);
  }
  useEffect(() => {
    const resize = () => setViewport({ w: innerWidth, h: innerHeight });
    const visibility = () => { setHidden(document.hidden); if (!document.hidden) interact(); };
    addEventListener('resize', resize); document.addEventListener('visibilitychange', visibility);
    return () => { removeEventListener('resize', resize); document.removeEventListener('visibilitychange', visibility); clearTimeout(hideTimer.current); clearTimeout(idleTimer.current); clearTimeout(openingTimer.current); };
  }, []);

  // Decode before starting the book or its timers. A failed asset never advances silently.
  useEffect(() => {
    let cancelled = false;
    Promise.all(pages.map(p => new Promise((resolve, reject) => {
      const image = new Image(); image.onload = resolve; image.onerror = reject; image.src = base + p.src;
    }))).then(() => { if (!cancelled) setLoaded(true); }).catch(() => { if (!cancelled) setError('页面图片加载失败，请刷新重试。'); });
    return () => { cancelled = true; };
  }, [album, base]);

  useEffect(() => {
    if (!loaded || !host.current) return;
    const mount = document.createElement('div'); host.current.appendChild(mount);
    let disposed = false;
    const remembered = current.current;
    const start = single ? remembered : Math.floor(remembered / 2) * 2;
    const book = new PageFlip(mount, {
      width: pageWidth, height: pageHeight, size: 'fixed', usePortrait: single,
      showCover: false, startPage: start, autoSize: false, flippingTime: duration,
      drawShadow: true, maxShadowOpacity: .5, useMouseEvents: false,
      showPageCorners: false, mobileScrollSupport: false,
    });
    book.on('flip', event => { if (!disposed) setIndex(Number(event.data)); });
    book.on('changeState', event => { if (!disposed) setBusy(event.data !== 'read'); });
    if (single) {
      // CanvasRender retains a portrait clip on its context across frames.
      // Use the library's soft HTML pages on phones: each half stays a full
      // independent image, without a persistent canvas clipping region.
      const leaves = pages.map((page, position) => {
        const leaf = document.createElement('div');
        leaf.className = 'mobile-book-leaf';
        leaf.dataset.density = 'soft';
        leaf.dataset.pageId = page.id;
        const image = document.createElement('img');
        image.src = base + page.src;
        image.alt = `${album.title} 第 ${position + 1} 页`;
        image.draggable = false;
        leaf.appendChild(image);
        mount.appendChild(leaf);
        return leaf;
      });
      book.loadFromHTML(leaves);
    } else {
      book.loadFromImages(pages.map(p => base + p.src));
    }
    // Initialization must not discard the remembered right half on a resize.
    setIndex(remembered); engine.current = book; setReady(true); setBusy(false);
    return () => { disposed = true; engine.current = null; book.destroy(); mount.remove(); setReady(false); };
  }, [loaded, single, pageWidth, pageHeight, album, base, duration]);

  useEffect(() => {
    const src = tenantContext?.tenant?.backgroundUrl || base + pages[index].src;
    setBackgrounds(old => { const next = [...old]; next[1 - activeBackground] = src; return next; });
    setActiveBackground(value => 1 - value);
  }, [index, base, tenantContext?.tenant?.backgroundUrl]);

  function advance(delta, manual = true) {
    if (manual) interact();
    if (!loaded || !ready || busy || opening) return;
    if (closed) {
      if (delta < 0) return;
      if (single) { setClosed(false); if (album.viewer.transition === 'slide') engine.current.turnToPage(1); else engine.current.flipNext('bottom'); }
      else { setOpening(true); openingTimer.current = setTimeout(() => { setClosed(false); setOpening(false); }, duration); }
      return;
    }
    if (delta < 0 && (single ? index === 0 : index < 2)) { setClosed(true); setIndex(0); engine.current.turnToPage(0); return; }
    if (delta > 0 && index >= last) {
      if (!manual && album.viewer.loop === false) { setPaused(true); return; }
      engine.current.turnToPage(0); setIndex(0); setClosed(true); return;
    }
    if (album.viewer.transition === 'slide') engine.current.turnToPage(Math.max(0, (single ? index : Math.floor(index / 2) * 2) + delta * (single ? 1 : 2)));
    else if (delta > 0) engine.current.flipNext('bottom'); else engine.current.flipPrev('bottom');
  }
  useEffect(() => {
    if (!loaded || !ready || paused || idle || hidden || busy || opening || share || publishing) return;
    const delay = !closed && index >= last ? (album.viewer.loopDelay ?? 2500) : (album.viewer.interval ?? 3000);
    const timer = setTimeout(() => advance(1, false), delay);
    return () => clearTimeout(timer);
  }, [loaded, ready, paused, idle, hidden, busy, opening, share, publishing, closed, index, last, single]);

  useEffect(() => {
    function key(event) {
      if (share) { if (event.key === 'Escape') setShare(null); return; }
      if (['ArrowLeft', 'ArrowRight', ' '].includes(event.key)) event.preventDefault();
      if (event.key === 'ArrowRight') advance(1);
      if (event.key === 'ArrowLeft') advance(-1);
      if (event.key === ' ') { reveal(); setPaused(value => !value); }
    }
    addEventListener('keydown', key); return () => removeEventListener('keydown', key);
  });

  async function publish() {
    setPublishing(true); setError('');
    try {
      const publishedData = await publishConfigured(tenantContext, id);
      const response = { ok: true, json: async () => publishedData };
      const data = await response.json(); if (!response.ok) throw new Error(data.error);
      const qr = await QRCode.toDataURL(data.url, { width: 1024, margin: 4, errorCorrectionLevel: 'H' });
      setShare({ ...data, qr });
    } catch (e) { setError(e.message || '发布失败'); } finally { setPublishing(false); }
  }
  async function copy() {
    try {
      if (navigator.clipboard) await navigator.clipboard.writeText(share.url);
      else { const input = document.createElement('textarea'); input.value = share.url; document.body.append(input); input.select(); const ok = document.execCommand('copy'); input.remove(); if (!ok) throw Error(); }
      setCopied(true);
    } catch { setError('请选中分享地址手动复制。'); }
  }
  function endTouch(event) {
    const start = touch.current; touch.current = null; setDrag(0);
    if (!start || (visualViewport?.scale ?? 1) > 1.05) return;
    const point = event.changedTouches[0]; const dx = point.clientX - start.x, dy = point.clientY - start.y;
    if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.4) advance(dx < 0 ? 1 : -1);
    else if (Math.abs(dx) < 10 && Math.abs(dy) < 10) reveal();
  }
  return <div data-layout={single ? 'single' : 'spread'} data-page={pages[index].id} data-phase={closed ? (opening ? 'opening' : 'cover') : 'reading'} className={`responsive-book ${visible ? 'controls-on' : ''} ${closed ? 'closed' : ''} ${opening ? 'opening' : ''}`} style={{ '--duration': `${duration}ms`, '--book-width': `${pageWidth * (single ? 1 : 2)}px`, '--page-height': `${pageHeight}px`, '--cover-width': `${coverHeight * ratio}px`, '--cover-height': `${coverHeight}px`, '--drag': `${drag}px` }} onPointerMove={reveal}>
    <div className={`ambient ${single || (closed && !opening) ? 'ambient-on' : ''}`} aria-hidden="true">{backgrounds.map((src, i) => <div key={i} style={{ backgroundImage: `url("${src}")`, opacity: i === activeBackground ? 1 : 0 }} />)}</div>
    <header className="book-controls">{tenantContext?.tenant?.logoUrl && <img src={tenantContext.tenant.logoUrl} alt={tenantContext.tenant.name}/>}<span>{tenantContext?.tenant?.name} · {album.title}{tenantContext?.tenant?.slogan ? ` · ${tenantContext.tenant.slogan}` : ''}</span>{onBack && <button onClick={onBack}>返回制作端</button>}<MusicToggle/><button onClick={() => setPaused(value => !value)}>{paused ? '播放' : '暂停'}</button><button onClick={() => { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen?.().catch(() => setError('当前浏览器不支持全屏。')); }}>全屏</button>{!tenantContext?.offline && <><button onClick={publish} disabled={publishing}>发布</button><button disabled={publishing} onClick={async () => { setPublishing(true); try { await downloadOffline(tenantContext, id); } catch (e) { setError(e.message); } finally { setPublishing(false); } }}>{publishing ? '处理中…' : '下载离线包'}</button><VideoExportButton albumId={id}/></>}</header>
    <main className="book-stage" onTouchStart={e => { interact(); touch.current = e.touches.length === 1 ? { x: e.touches[0].clientX, y: e.touches[0].clientY } : null; }} onTouchMove={e => { if (e.touches.length > 1 || (visualViewport?.scale ?? 1) > 1.05) { touch.current = null; setDrag(0); } else if (touch.current && single && !busy) { const dx = e.touches[0].clientX - touch.current.x; if (!closed || dx < 0) setDrag(Math.max(-60, Math.min(60, dx * .3))); } }} onTouchEnd={endTouch} onTouchCancel={() => { touch.current = null; setDrag(0); }}>
      <div className="book-engine" ref={host} style={{ opacity: closed && !opening ? 0 : 1 }} />
      {closed && <div className="standalone-cover"><img src={base + pages[0].src} alt="画册封面" /></div>}
      {!closed && <button className="book-prev" aria-label="上一页" onClick={() => advance(-1)}>‹</button>}
      <button className="book-next" aria-label={closed ? '翻开画册' : '下一页'} onClick={() => advance(1)}>›</button>
    </main>
    {error && <div className="book-error" role="alert">{error}<button onClick={() => setError('')}>关闭</button></div>}
    {share && <div className="publish-modal-backdrop"><section className="publish-modal" role="dialog" aria-modal="true" aria-label="发布结果"><button autoFocus className="publish-close" onClick={() => { setShare(null); setCopied(false); }}>×</button><h2>分享画册</h2><img className="publish-qr" src={share.qr} alt="画册二维码" /><p style={{ overflowWrap: 'anywhere' }}>{share.url}</p><div className="publish-actions"><button onClick={copy}>{copied ? '已复制' : '复制链接'}</button><a className="download-qr" href={share.qr} download={`${album.title}-二维码.png`}>下载二维码图片 (PNG)</a></div><p>{share.addressMode === 'lan' ? '手机需与电脑连接同一 Wi-Fi' : '分享链接已生成'}</p></section></div>}
  </div>;
}
