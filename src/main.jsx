import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { PageFlip } from 'page-flip';
import QRCode from 'qrcode';
import ResponsiveBook from './ResponsiveBook';
import TenantApp, { useTenant, publishConfigured, downloadOffline, VideoExportButton, MusicToggle, TenantBrand } from './TenantApp';
import './styles.css';

const modes = [
  ['left-cover-spread', '左半页封面 + 全页对开', '首页左半区作为封面 · 所有页面中线拆分', '电脑双页展开，手机逐半页阅读。'],
  ['single-slide', '全单页', '1 Slide → 1 页面', '完整保留每张 Slide，不裁切。'],
  ['cover-inner-split', '封面 + 内页拆分', '第 1 页完整居中 · 第 2 页起每页中线拆分', '按页面位置执行固定规则，不对封底内容做猜测。'],
  ['split-all', '全拆分', '每张 Slide → Left + Right', '整份文件统一按垂直中线等分。'],
];
const formatSize = (bytes) => `${(bytes / 1048576).toFixed(2)} MB`;

function Viewer({ album, base, id, onBack }) {
  if (album.pageMode === 'left-cover-spread') return <ResponsiveBook album={album} base={base} id={id} onBack={onBack} />;
  return <LegacyViewer album={album} base={base} id={id} onBack={onBack} />;
}

function LegacyViewer({ album, base, id, onBack }) {
  const tenantContext = useTenant();
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(Boolean(album.viewer.autoplay));
  const [isFlipping, setIsFlipping] = useState(false);
  const [pageFlipReady, setPageFlipReady] = useState(false);
  const [pageFlipError, setPageFlipError] = useState(false);
  const [controlsVisible, setControlsVisible] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(Boolean(document.fullscreenElement));
  const [published, setPublished] = useState(null);
  const [publishBusy, setPublishBusy] = useState(false);
  const [offlineBusy, setOfflineBusy] = useState(false);
  const [publishError, setPublishError] = useState('');
  const [copyState, setCopyState] = useState('');
  const flipRoot = useRef(null);
  const pageFlip = useRef(null);
  const autoFlip = useRef(false);
  const resumeTimer = useRef(null);
  const loopTimer = useRef(null);
  const controlsTimer = useRef(null);
  const visibilityResume = useRef(false);
  const page = album.pages[index];
  const interval = album.viewer.interval ?? 3000;
  const flipDuration = album.viewer.flippingTime ?? 1000;
  const loopDelay = album.viewer.loopDelay ?? 2500;
  const transition = album.viewer.transition ?? 'page-curl';
  const showPageCurl = transition === 'page-curl' && !pageFlipError;
  const showCover = album.pageMode !== 'split-all';
  const finalSpreadStart = showCover
    ? album.pages.length - 1
    : Math.max(0, album.pages.length - (album.pages.length % 2 === 0 ? 2 : 1));

  const showControlsTemporarily = useCallback(() => {
    setControlsVisible(true);
    window.clearTimeout(controlsTimer.current);
    controlsTimer.current = window.setTimeout(() => setControlsVisible(false), 2500);
  }, []);

  const manualInteraction = useCallback(() => {
    setPlaying(false);
    window.clearTimeout(resumeTimer.current);
    window.clearTimeout(loopTimer.current);
    autoFlip.current = false;
    resumeTimer.current = window.setTimeout(() => setPlaying(true), album.viewer.idleResume ?? 12000);
  }, [album.viewer.idleResume]);

  useEffect(() => {
    if (transition !== 'page-curl' || !flipRoot.current) return undefined;
    let disposed = false;
    // Every mode except single-slide feeds physical half-slide pages to the
    // book. cover-inner-split has normalized 8:9 cover pages as well, so it
    // must use the same spread geometry as split-all.
    const splitPages = album.pageMode !== 'single-slide';
    const pageWidth = splitPages ? 960 : 1920;
    const pageHeight = 1080;
    try {
      const instance = new PageFlip(flipRoot.current, {
        // split-all emits half-slide pages (960 × 1080). A full-slide album
        // keeps its native 16:9 page size so ImagePage never stretches it.
        width: pageWidth,
        height: pageHeight,
        size: 'stretch',
        minWidth: 320,
        maxWidth: splitPages ? 1400 : 2560,
        minHeight: splitPages ? 360 : 240,
        maxHeight: splitPages ? 1575 : 1440,
        // split-all has no standalone cover: keeping the first left/right
        // pair together is what preserves the original Slide composition.
        showCover,
        startPage: 0,
        flippingTime: flipDuration,
        maxShadowOpacity: 0.5,
        drawShadow: true,
        // A full-slide album is one 16:9 page at a time. Split modes are a
        // 960x1080 half-page spread whose total canvas is 16:9.
        usePortrait: !splitPages,
        autoSize: true,
        mobileScrollSupport: true,
      });
      instance.on('flip', (event) => {
        if (disposed) return;
        setIndex(Number(event.data));
        setIsFlipping(false);
        autoFlip.current = false;
      });
      instance.on('changeState', (event) => {
        if (disposed || autoFlip.current) return;
        if (['user_fold', 'fold_corner', 'flipping'].includes(event.data)) manualInteraction();
      });
      instance.loadFromImages(album.pages.map((item) => `${base}${item.src}`));
      pageFlip.current = instance;
      setPageFlipReady(true);
    } catch (error) {
      console.error('PageFlip initialization failed', error);
      if (!disposed) setPageFlipError(true);
    }
    return () => { disposed = true; pageFlip.current?.destroy(); pageFlip.current = null; setPageFlipReady(false); };
  }, [album, base, flipDuration, manualInteraction, showCover, transition]);

  const autoAdvance = useCallback(() => {
    if (showPageCurl && !pageFlip.current) return;
    autoFlip.current = true;
    setIsFlipping(true);
    if (index >= finalSpreadStart) {
      window.clearTimeout(loopTimer.current);
      loopTimer.current = window.setTimeout(() => {
        if (pageFlip.current && showPageCurl) pageFlip.current.turnToPage(0);
        setIndex(0);
        setIsFlipping(false);
        autoFlip.current = false;
      }, loopDelay);
      return;
    }
    if (showPageCurl) pageFlip.current.flipNext('bottom');
    else {
      setIndex((value) => (value + 1) % album.pages.length);
      setIsFlipping(false);
      autoFlip.current = false;
    }
  }, [album.pages.length, finalSpreadStart, index, loopDelay, showPageCurl]);

  const move = useCallback((delta) => {
    if (showPageCurl && pageFlip.current) {
      manualInteraction();
      autoFlip.current = false;
      setIsFlipping(true);
      if (delta > 0) {
        if (index >= album.pages.length - 1) pageFlip.current.turnToPage(0);
        else pageFlip.current.flipNext('bottom');
      } else if (index <= 0) pageFlip.current.turnToPage(album.pages.length - 1);
      else pageFlip.current.flipPrev('bottom');
      return;
    }
    manualInteraction();
    setIsFlipping(true);
    setIndex((value) => (value + delta + album.pages.length) % album.pages.length);
  }, [album.pages.length, index, manualInteraction, showPageCurl]);

  useEffect(() => {
    if (!playing || isFlipping || album.pages.length < 2 || (showPageCurl && !pageFlipReady)) return undefined;
    const timer = window.setTimeout(autoAdvance, interval);
    return () => window.clearTimeout(timer);
  }, [album.pages.length, autoAdvance, index, interval, isFlipping, pageFlipReady, playing, showPageCurl]);
  useEffect(() => () => {
    window.clearTimeout(resumeTimer.current);
    window.clearTimeout(loopTimer.current);
    window.clearTimeout(controlsTimer.current);
  }, []);
  useEffect(() => {
    const keyHandler = (event) => {
      showControlsTemporarily();
      if (event.key === 'ArrowRight') { event.preventDefault(); move(1); }
      if (event.key === 'ArrowLeft') { event.preventDefault(); move(-1); }
      if (event.key === ' ') { event.preventDefault(); setPlaying((value) => !value); }
      if (event.key.toLowerCase() === 'f') document.documentElement.requestFullscreen?.().catch(() => {});
    };
    const visibilityHandler = () => {
      if (document.hidden) { visibilityResume.current = playing; window.clearTimeout(resumeTimer.current); window.clearTimeout(loopTimer.current); setPlaying(false); }
      else if (visibilityResume.current) setPlaying(true);
    };
    window.addEventListener('keydown', keyHandler); document.addEventListener('visibilitychange', visibilityHandler);
    return () => { window.removeEventListener('keydown', keyHandler); document.removeEventListener('visibilitychange', visibilityHandler); };
  }, [move, playing, showControlsTemporarily]);
  useEffect(() => {
    const fullscreenHandler = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', fullscreenHandler);
    return () => document.removeEventListener('fullscreenchange', fullscreenHandler);
  }, []);
  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
    else document.documentElement.requestFullscreen?.().catch(() => {});
    showControlsTemporarily();
  };
  const publishAlbum = async () => {
    setPublishBusy(true);
    setPublishError('');
    setCopyState('');
    try {
      const publishedData = await publishConfigured(tenantContext, id);
      const response = { ok: true, json: async () => publishedData };
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '发布失败');
      const qr = await QRCode.toDataURL(data.url, {
        errorCorrectionLevel: 'H',
        type: 'image/png',
        width: 1024,
        margin: 4,
        color: { dark: '#111827', light: '#ffffff' },
      });
      setPublished({ ...data, qr });
    } catch (error) {
      setPublishError(error.message || '发布失败');
    } finally {
      setPublishBusy(false);
    }
  };
  const downloadAlbumOffline = async () => {
    setOfflineBusy(true);
    setPublishError('');
    try {
      await downloadOffline(tenantContext, id);
    } catch (error) {
      setPublishError(error.message || '离线画册生成失败');
    } finally {
      setOfflineBusy(false);
    }
  };
  const copyPublishedUrl = async () => {
    if (!published?.url) return;
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(published.url);
      else {
        const input = document.createElement('textarea');
        input.value = published.url;
        input.style.position = 'fixed';
        input.style.opacity = '0';
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        input.remove();
      }
      setCopyState('已复制');
      window.setTimeout(() => setCopyState(''), 1800);
    } catch {
      setCopyState('复制失败，请手动复制');
    }
  };
  const selectThumbnail = (itemIndex) => {
    manualInteraction();
    if (showPageCurl && pageFlip.current) { autoFlip.current = false; setIsFlipping(true); pageFlip.current.flip(itemIndex, 'bottom'); }
    else { setIsFlipping(true); setIndex(itemIndex); }
  };
  const preload = [-2, -1, 1, 2].map((offset) => album.pages[(index + offset + album.pages.length) % album.pages.length]).filter(Boolean);
  return <div className={`viewer ${controlsVisible ? 'controls-visible' : ''}`} onPointerMove={showControlsTemporarily} onTouchStart={showControlsTemporarily}><header className="viewer-header"><span className="viewer-title">{tenantContext?.tenant?.logoUrl && <img className="tenant-logo" src={tenantContext.tenant.logoUrl} alt={tenantContext.tenant.name}/>} {tenantContext?.tenant?.name} · {album.title} {tenantContext?.tenant?.slogan}</span><div className="viewer-tools">{onBack && <button className="viewer-play" onClick={onBack}>返回制作端</button>}<MusicToggle/><button className="viewer-play" onClick={() => setPlaying((value) => !value)}>{playing ? '暂停' : '播放'}</button><button className="viewer-play" onClick={toggleFullscreen}>{isFullscreen ? '退出全屏' : '全屏'}</button>{!tenantContext?.offline && <><button className="viewer-play" onClick={downloadAlbumOffline} disabled={offlineBusy}>{offlineBusy ? '打包中…' : '下载离线包'}</button><VideoExportButton albumId={id}/><button className="viewer-publish" onClick={publishAlbum} disabled={publishBusy}>{publishBusy ? '发布中…' : '发布'}</button></>}</div></header><main className="viewer-main"><div className="viewer-meta"><span>PREVIEW / {String(index + 1).padStart(2, '0')} — {String(album.pages.length).padStart(2, '0')}</span><span>{page.part.toUpperCase()} · SLIDE {page.parentSlide}</span></div><div className="page-stage"><button onClick={() => move(-1)} aria-label="上一页">‹</button>{showPageCurl ? <div className="pageflip-root" ref={flipRoot} aria-label={`${album.title} Page Curl Viewer`} /> : <div className={`page-frame slide-transition ${isFlipping ? 'is-flipping' : ''}`} style={{ '--flip-duration': `${flipDuration}ms` }} onAnimationEnd={() => setIsFlipping(false)}><img src={`${base}${page.src}`} alt={`${album.title} 第 ${index + 1} 页`} /></div>}<button onClick={() => move(1)} aria-label="下一页">›</button></div><div className="progress"><i style={{ width: `${((index + 1) / album.pages.length) * 100}%`}} /></div><div className="thumb-strip">{album.pages.map((item, itemIndex) => <button className={itemIndex === index ? 'active' : ''} onClick={() => selectThumbnail(itemIndex)} key={item.id}><img src={`${base}${item.thumbnail}`} alt={`第 ${itemIndex + 1} 页`} /></button>)}</div><div className="preload" aria-hidden="true">{preload.map((item) => <img key={item.id} src={`${base}${item.src}`} alt="" />)}</div></main>{published && <div className="publish-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="publish-title" onMouseDown={(event) => { if (event.target === event.currentTarget) setPublished(null); }}><section className="publish-modal"><button className="publish-close" onClick={() => setPublished(null)} aria-label="关闭发布面板">×</button><p className="publish-kicker">PUBLISH RESULT</p><h2 id="publish-title">画册已发布</h2><p className="publish-description">扫描二维码，在手机或大屏设备上打开这本电子画册。</p><img className="publish-qr" src={published.qr} alt="画册分享二维码" /><div className="publish-url"><span>{published.url}</span><button onClick={copyPublishedUrl}>{copyState || '复制链接'}</button></div><div className="publish-actions"><a className="download-qr" href={published.qr} download={`${album.title || 'LiveSlides'}-二维码.png`}>下载二维码图片 (PNG)</a><button className="publish-done" onClick={() => setPublished(null)}>完成</button></div><small className="publish-address">{published.addressMode === 'lan' ? '当前使用局域网地址 · 手机需与此电脑连接同一 Wi‑Fi' : '当前使用生产域名地址'}</small></section></div>}{publishError && <div className="publish-error" role="alert">{publishError}</div>}</div>;
}

function Creator({ initialAlbum }) {
  const [pageMode, setPageMode] = useState('left-cover-spread');
  const [interval, setInterval] = useState(3000);
  const [transition, setTransition] = useState('page-curl');
  const [file, setFile] = useState(null);
  const [fileMeta, setFileMeta] = useState(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [result, setResult] = useState(initialAlbum);
  const fileInput = useRef(null);
  const stepIndex = busy ? 1 : 0;
  async function validateFile(next) {
    if (!next.name.toLowerCase().endsWith('.pptx')) { setFile(null); setFileMeta(null); setMessage('只接受 .pptx 文件。旧版 .ppt 请先另存为 .pptx。'); return; }
    if (next.size > 50 * 1024 * 1024) { setFile(null); setFileMeta(null); setMessage('文件超过 50MB 上限，请先压缩或拆分源文件。'); return; }
    setFile(next); setFileMeta({ status: 'validating' }); setMessage('正在校验 PPTX 容器、文件完整性和可见页数…');
    const form = new FormData(); form.append('file', next);
    try { const response = await fetch('/api/validate', { method: 'POST', body: form }); const data = await response.json(); if (!response.ok) throw new Error(data.error || '文件校验失败'); setFileMeta({ status: 'valid', slides: data.visibleSlides, bytes: data.bytes }); setMessage('文件校验通过，可以开始转换。'); } catch (error) { setFileMeta({ status: 'invalid' }); setMessage(error.message); }
  }
  function choose(event) { const next = event.target.files?.[0]; if (next) validateFile(next); }
  function drop(event) { event.preventDefault(); setDragActive(false); const next = event.dataTransfer.files?.[0]; if (next) validateFile(next); }
  async function convertFile() {
    setBusy(true); setMessage('正在校验 PPTX、渲染页面并生成 WebP…'); const form = new FormData(); form.append('file', file); form.append('pageMode', pageMode); form.append('mode', pageMode); form.append('interval', String(interval)); form.append('transition', transition);
    try { const response = await fetch('/api/convert', { method: 'POST', body: form }); const data = await response.json(); if (!response.ok) throw new Error(data.error || '转换失败'); setResult(data); setMessage(`转换完成：${data.album.pages.length} 个逻辑页面。`); window.history.replaceState({}, '', `/?album=${data.id}`); } catch (error) { setMessage(error.message); } finally { setBusy(false); }
  }
  function clearFile(event) { event.preventDefault(); event.stopPropagation(); setFile(null); setFileMeta(null); setMessage(''); if (fileInput.current) { fileInput.current.value = ''; window.setTimeout(() => fileInput.current?.click(), 0); } }
  if (result) return <Viewer album={result.album} base={result.base} id={result.id} onBack={() => { setResult(null); window.history.replaceState({}, '', '/'); }} />;
  const fileStateText = fileMeta?.status === 'validating' ? '正在校验…' : fileMeta?.status === 'valid' ? `${formatSize(fileMeta.bytes || file.size)} · ${fileMeta.slides} Slides · 校验通过` : fileMeta?.status === 'invalid' ? '校验失败，请重新选择' : file ? `${formatSize(file.size)} · 等待校验` : '';
  return <div className="shell"><header><TenantBrand /><span>PHASE 1 · PPT → HTML</span><i>● 转换器原型</i></header><main><section className="hero"><small>ELECTRONIC BROCHURE CONVERTER</small><h1><span>把已经完成的 PPT，</span><em>变成可直接在线分享的电子画册。</em></h1><p>PowerPoint 负责内容与版式。LiveSlides 负责确定性转换、在线播放与发布。</p></section><section className="work"><nav>{['导入与模式', '转换与预览', '发布与二维码'].map((step, stepNumber) => <span className={stepNumber === stepIndex ? 'active' : stepNumber < stepIndex ? 'done' : ''} key={step}><b>0{stepNumber + 1}</b>{step}</span>)}</nav><article><label>SOURCE FILE<h2>上传已定稿的 PowerPoint</h2></label><label className={`drop ${file ? 'has-file' : ''} ${dragActive ? 'drag-active' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragActive(true); }} onDragLeave={() => setDragActive(false)} onDrop={drop}><input ref={fileInput} type="file" accept=".pptx" onChange={choose}/>{file ? <><b className="file-check">✓</b><strong>{file.name}</strong><small>{fileStateText}</small><button type="button" className="reselect" onClick={clearFile}>重新选择</button></> : <><b aria-hidden="true">↑</b><strong>拖入 PPTX 文件，或</strong><span className="drop-action">选择文件</span><small>内容、字体和版式请先在本地 PowerPoint 中完成</small></>}</label>{message && <p className="msg">{message}</p>}<div className="checks">{["不解析 PPT 图元", "不自动判断跨页", "不修改你的内容"].map(item => <span key={item}><b aria-hidden="true">✓</b>{item}</span>)}</div><div className="constraints">支持 .pptx 格式 · 文件上限 50MB · 建议使用开源中文字体</div></article><article><label>PAGE MODE<h2>这份 PPT 如何成为逻辑页面？</h2></label><div className="modes">{modes.map(([id, title, rule, desc]) => <button type="button" aria-pressed={pageMode === id} data-page-mode={id} className={pageMode === id ? 'chosen' : ''} onClick={() => setPageMode(id)} key={id}><span className="mode-radio" aria-hidden="true" /><strong>{title}</strong><small>{rule}</small><em>{desc}</em></button>)}</div></article><article className="viewer-settings"><label>VIEWER DEFAULTS<h2>在线播放与翻页体验</h2></label><div className="settings-grid"><div className="setting"><span>单页静止停留</span><div className="choices">{[[3000, '3 秒'], [5000, '5 秒']].map(([value, text]) => <button type="button" aria-pressed={interval === value} className={interval === value ? 'selected' : ''} onClick={() => setInterval(value)} key={value}>{text}</button>)}</div><small>页面落平后开始下一轮计时</small></div><div className="setting"><span>翻页动画</span><div className="choices">{[['page-curl', 'Page Curl'], ['slide', 'Slide']].map(([value, text]) => <button type="button" aria-pressed={transition === value} className={transition === value ? 'selected' : ''} onClick={() => setTransition(value)} key={value}>{text}</button>)}</div><small>{transition === 'page-curl' ? '默认 Canvas 物理卷页 · 1.0 秒' : '轻量滑动回退动画'}</small></div></div></article><div className="action"><p>将生成 WebP 页面、缩略图、Album JSON 和 HTML Viewer。</p><button disabled={!file || fileMeta?.status !== 'valid' || busy} onClick={convertFile}>{busy ? '转换中…' : '开始校验与转换 →'}</button></div></section></main><footer><span>LiveSlides / deterministic brochure delivery</span><span>AutoPlay 3s · Page Curl 1s · Idle Resume 12s　·　@AIWorkLab</span></footer></div>;
}

function App() {
  const id = new URLSearchParams(window.location.search).get('album');
  const [loading, setLoading] = useState(Boolean(id));
  const [initialAlbum, setInitialAlbum] = useState(null);
  useEffect(() => {
    if (!id) return undefined;
    let cancelled = false;
    fetch(`/api/albums/${id}/album.json`).then((response) => { if (!response.ok) throw new Error('Album not found'); return response.json(); }).then((album) => { if (!cancelled) setInitialAlbum({ id, album, base: `/api/albums/${id}/` }); }).catch(() => { window.history.replaceState({}, '', '/'); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);
  if (loading) return <div className="loading">正在打开画册…</div>;
  return <Creator key={initialAlbum?.id || 'creator'} initialAlbum={initialAlbum} />;
}

createRoot(document.getElementById('root')).render(<TenantApp CreatorApp={App} Viewer={Viewer} />);
