# Fonts

Caption burn-in requires a font with full Arabic support. The default `config.yaml` points at:

```
assets/fonts/NotoNaskhArabic-Regular.ttf
```

Download a Noto Arabic family (or Cairo / Amiri) and drop the `.ttf` here, or change
`paths.font` in `config.yaml` to point at your font. Do **not** rely on system default fonts —
they vary across machines and break reproducible rendering.

Suggested: [Noto Naskh Arabic](https://fonts.google.com/noto/specimen/Noto+Naskh+Arabic).

> Font files are intentionally **not** committed (licensing + repo size). The `doctor` command
> reports whether the configured font exists.
