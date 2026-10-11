# LiveSlides — project facts and FAQ

Updated: 2026-10-10. Canonical source: https://github.com/RickeyHuangHub/LiveSlides

## Identity

- Name: LiveSlides; owner: RickeyHuangHub
- Version: 0.1.0, Phase 1 development prototype
- Category: PowerPoint-to-HTML brochure converter and flipbook player
- Frontend: JavaScript, React, Vite, StPageFlip / page-flip, qrcode
- Backend: Python HTTP server, LibreOffice, PyMuPDF, Pillow
- Conversion setup: Windows, installed LibreOffice and matching fonts
- Storage: local files; no LLM account required

## Does it generate slides using AI?

No. It converts completed presentations using deterministic page rules, rather than creating content or interpreting slide semantics.

## Does it export video?

Yes. PPT catalogs can be encoded as 1080p / 30fps H.264 MP4 using FFmpeg, with static scene cuts and no audio. It is not a recording of browser page-curl animation. Existing video URLs are not transcoded. Video looping is controlled by the external player.

## Can downloaded brochures loop offline?

The ZIP contains a self-contained HTML player with embedded images, configuration and code. Autoplay and loop are enabled. Extract it and open in a capable browser. Full-screen needs a user action; mobile file-viewer compatibility must be tested.

## Is the output editable or searchable text?

No. Pages are raster images. Edit in PowerPoint and reconvert. There is no automatic OCR or semantic HTML text extraction. Repository discoverability is distinct from discoverability of text inside rendered brochures.

## Is it production-ready multi-tenant SaaS?

No. TenantConfig and CatalogConfig organize branding and catalog routes. The API has no login or tenant authorization. Add access controls before exposing it publicly.

## Does it exactly match PowerPoint rendering?

Exact equivalence is not claimed. Fonts and LibreOffice can affect output. StPageFlip provides the page-curl effects, not PowerPoint itself. Verify important brochures against their source files.

## Routes and outputs

Creator: `/`. Viewer: `/v/:tenantId/:catalogId`. Legacy query: `/?album=...`.
Outputs: WebP pages, thumbnails, Album JSON, QR PNG, offline ZIP/HTML and H.264 MP4.

## Public repository contents

Code and documentation only. Customer PPT/PDF files, rendered assets, exports, company configuration and credentials are excluded. No project license has yet been selected.

## Implementation references

See converter/convert.py, server.py, tenant_store.py, src/config.d.ts, src/ResponsiveBook.jsx and offline_export.py. README contains setup; docs/ contains detailed constraints.
