# Fonts bundled with TIREKICK

Three typefaces are vendored here as variable `.woff2` subsets and served from
our own origin. Self-hosting is deliberate: the report must render identically
offline, and a font CDN request would announce that somebody is reading a vehicle
report to a third party we have no agreement with. See `docs/BRAND.md`.

All three are licensed under the **SIL Open Font License, Version 1.1**. The full
licence text and each project's copyright notice are in this directory, unmodified
as fetched from the upstream repository, which is what the OFL requires to travel
with the binaries.

| File | Family | Copyright | Licence |
|---|---|---|---|
| `archivo.woff2` | Archivo (variable) | Copyright 2020 The Archivo Project Authors | [`archivo-OFL.txt`](archivo-OFL.txt) |
| `newsreader.woff2` | Newsreader (variable) | Copyright 2020 The Newsreader Project Authors | [`newsreader-OFL.txt`](newsreader-OFL.txt) |
| `jetbrainsmono.woff2` | JetBrains Mono (variable) | Copyright 2020 The JetBrains Mono Project Authors | [`jetbrainsmono-OFL.txt`](jetbrainsmono-OFL.txt) |

Upstream, in the same order:
https://github.com/Omnibus-Type/Archivo ·
https://github.com/productiontype/Newsreader ·
https://github.com/JetBrains/JetBrainsMono

## Modification

None of the three has been modified beyond subsetting and conversion to woff2,
both of which the OFL permits. **No family declares a Reserved Font Name**, so the
subsets keep their original names and are referenced as `Archivo`, `Newsreader`
and `JetBrains Mono` in `globals.css`.

The OFL forbids selling the fonts on their own and requires that they remain under
the OFL wherever they travel. Bundling them inside a commercial product is
explicitly permitted and is what we do.

`fonts.test.ts` fails the build if a `.woff2` here has no licence beside it, if a
licence is not OFL 1.1, or if `globals.css` loads a face this file does not
account for.
