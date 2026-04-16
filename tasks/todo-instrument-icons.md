# TODO: Design Custom Instrument Class Icons

## Context
The terminal uses SVG icons to visually distinguish asset types (Stock, ETF, Futures, Currency, Crypto, Bond, Option) in the ticker column. Current icons are simple geometric placeholder SVGs at `frontend/public/assets/icons/`.

## Task
Design a cohesive set of instrument class icons that:
- Are visually distinct at 11x11px (tiny display in ticker cells)
- Work on dark backgrounds (terminal theme)
- Have consistent stroke weight and style
- Are recognizable at a glance by traders

## Icon Files to Replace
```
frontend/public/assets/icons/
  stock.svg     — Stock/Equity (current: upward trend line)
  etf.svg       — ETF (current: bar chart in rectangle)
  future.svg    — Futures (current: concentric circles)
  currency.svg  — Currency/Forex (current: overlapping circles)
  crypto.svg    — Cryptocurrency (current: B symbol)
  bond.svg      — Bond (current: certificate grid)
  option.svg    — Option (current: circle with plus)
```

## Integration
Icons are loaded via `<img src="./assets/icons/{file}">` with CSS `filter: brightness(0) invert(0.7)` for dark theme. Unicode fallback glyphs are defined in `ASSET_TYPE_ICONS` in `terminal-app.js` in case images fail to load.

## Notes
- Keep SVG viewBox at `0 0 16 16` for consistency
- Use `stroke="currentColor"` — the CSS filter handles coloring
- Consider Material Design or Phosphor icon sets for reference
