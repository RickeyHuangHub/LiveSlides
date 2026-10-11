# Converter milestone

Run from the `liveslides-app` directory:

```powershell
python converter/convert.py .\your-brochure.pptx .\sample-album --mode single-slide
```

The output contains `album.json`, `pages/*.webp`, `thumbs/*.webp`, and `cover.webp`.
The converter intentionally uses a full-slide raster pipeline. It does not parse or rebuild PowerPoint elements.
