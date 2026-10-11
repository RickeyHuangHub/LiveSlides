# LiveSlides — PowerPoint to HTML Brochure & Offline Flipbook

**LiveSlides converts finished PowerPoint presentations (.pptx) into responsive HTML electronic brochures, with page-curl playback, QR-code sharing, multi-company configuration, and downloadable offline flipbooks.**

**将定稿 PPT 转为 HTML 电子画册，支持仿真翻页、手机阅读、二维码分享、多公司配置和离线循环播放。**

[中文说明](docs/README.zh-CN.md) · [Project facts / FAQ](docs/project-facts.md) · [Offline playback](docs/offline-player.md) · [Company configuration](docs/multi-tenant.md) · [AI-readable index](llms.txt)

Canonical repository: https://github.com/RickeyHuangHub/LiveSlides

Status: **Phase 1 development prototype**, version 0.1.0; snapshot: 2026-10-10.

## What is LiveSlides?

LiveSlides is a local-first **PPTX-to-HTML converter and digital brochure player** for company introductions, product catalogs, sales demonstrations and trade-show displays. Author content in PowerPoint; render and package it with LiveSlides.

It is not an AI slide generator or a PowerPoint editor. MP4 export uses static scene cuts, not a recording of the interactive page-curl animation. Conversion follows explicit page-splitting rules rather than guessing slide semantics. No LLM or paid AI API is required.

## Features

| Capability | Current implementation |
| --- | --- |
| Conversion | LibreOffice → PDF → PyMuPDF → WebP pages, thumbnails and Album JSON |
| Image quality | 180 DPI rasterization; WebP quality 92 / method 6; original aspect ratio |
| Page layouts | Full-slide, split-all, cover + inner split, left-half cover + spreads |
| Responsive reading | Centered cover and paired spreads on desktop; sequential half-pages on narrow/portrait screens |
| Page curl | StPageFlip / page-flip: desktop Canvas, mobile single-page soft HTML rendering |
| Presentation mode | Auto-hiding controls; no permanent QR, thumbnail strip or debug overlay |
| Autoplay | 3-second dwell, 1-second flip, 12-second idle resume, 2.5-second final-page loop delay |
| Companies and catalogs | TenantConfig / CatalogConfig, visual sidebar and JSON configuration |
| Sharing | /v/:tenantId/:catalogId, LAN address detection, configurable production origin, PNG QR codes |
| Offline playback | Self-contained HTML and instructions inside a ZIP; no server or Internet required |
| MP4 export | FFmpeg H.264, 1080p / 30fps, static cuts, background job and download; requires FFmpeg |
| Existing videos | Online muted looping of a configured direct video URL; not video generation |

## Quick start (Windows)

The current converter expects LibreOffice at `C:\Program Files\LibreOffice\program\soffice.exe`. Other operating systems' conversion environments are **not yet configured**.

Prerequisites: Python 3.10+, a Node.js version supported by the locked Vite dependencies, npm, LibreOffice and suitable Chinese fonts (for example Microsoft YaHei or Noto Sans SC). Matching the source fonts matters; fallback fonts cannot guarantee identical layout.

MP4 export additionally requires FFmpeg with libx264 in PATH, or an explicit LIVESLIDES_FFMPEG executable path. See [MP4 export](docs/mp4-export.md) for format and playback limits.

```powershell
git clone https://github.com/RickeyHuangHub/LiveSlides.git
cd LiveSlides
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
npm run build
```

Terminal 1:

```powershell
.\.venv\Scripts\python.exe server.py
```

Terminal 2:

```powershell
npm run dev -- --strictPort
```

Open **http://127.0.0.1:5193/**. Upload your own PPTX (up to 50 MB), choose a page mode, convert and preview. Customer presentations and pre-generated albums are not included.

## Share a brochure

Select a company, bind a catalog to a converted album and save. Click **发布 / 二维码** to obtain the URL and PNG QR code. A phone on the same reachable LAN can scan it while the computer's services remain running.

Keep tenant/catalog IDs stable and change the bound album to retain the same QR URL. Downloaded offline files are independent snapshots.

```powershell
$env:LIVESLIDES_PUBLIC_BASE_URL = "https://brochure.example.com"
.\.venv\Scripts\python.exe server.py
```

A domain setting does **not** deploy the app. Production needs SPA fallback for /v/*, an /api/* reverse proxy, HTTPS and access controls. .env.example is a reference only: the server does not automatically load dotenv. LIVESLIDES_VIEWER_PORT defaults to 5193.

## Offline flipbooks

Click **下载离线播放包**, extract the ZIP and open **开始播放.html** in a modern browser. Images, configuration, styles and player code are embedded; autoplay and loop are enabled. Full-screen requires a user action.

- No Python, Node, local server, CDN or network needed on the playback computer.
- Page images retain their original bytes; no recompression on export.
- Remote Logo/background URLs are rejected rather than silently requiring Internet access.
- Direct video URLs are not included in offline HTML. A separate **导出 MP4** action encodes PPT pages as static-cut H.264 video; see [MP4 export](docs/mp4-export.md).
- Mobile file previewers may not execute HTML; physical-device browser testing is required.

## Architecture

```text
PPTX → LibreOffice PDF → PyMuPDF rasterization → Pillow WebP
                                                 ↓
                                     Album JSON + page assets
                                                 ↓
                            React viewer / self-contained offline HTML
```

| Source | Responsibility |
| --- | --- |
| converter/convert.py | Deterministic conversion and page splitting |
| server.py | Local API and album assets |
| tenant_store.py, src/config.d.ts | Company/catalog persistence and types |
| src/TenantApp.jsx | Configuration UI, routing and existing-video playback |
| src/ResponsiveBook.jsx | Responsive page-curl viewer |
| offline_export.py, vite.offline.config.mjs | Self-contained offline package |

## Build and test

```powershell
npm run build
python -m unittest test_video_export test_offline_export test_tenant_store -v
```

Build outputs: dist/ and offline-dist/. Rebuild player code before exporting new offline packages. The 19 Python tests cover configuration, route helpers, export integrity, escaping, path restrictions and limits; they do not replace browser or phone acceptance.

## Security, limitations and licensing

- **Trusted local development only:** management APIs have no login or tenant authorization. Company configuration separation is not security isolation. Add authentication and authorization before Internet exposure.
- Fidelity depends on LibreOffice and fonts; PowerPoint-identical rendering is not guaranteed.
- Raster pages do not preserve PowerPoint animations, audio or editable/searchable text.
- Narrow viewports remain single-page even if rotated. Forced phone landscape has not been implemented.
- Full-screen and video audio remain subject to browser policies.
- Customer files, generated assets, exports, company configuration and secrets are excluded from Git.
- No project license has been selected. Public source availability does not itself grant an open-source license. Review [third-party notices](THIRD_PARTY_NOTICES.md) before redistribution.

## Find and cite the project

Canonical name: **LiveSlides**. Repository: **RickeyHuangHub/LiveSlides**.

Related terms: PowerPoint to HTML, PPTX converter, HTML flipbook, digital brochure, electronic catalog, offline presentation, QR brochure sharing; PPT 转 HTML、电子画册、离线翻页画册、企业宣传册。

For grounded summaries, see [project facts](docs/project-facts.md) and the linked source. Clear documentation helps retrieval, but does not guarantee search-engine or AI inclusion or ranking.
