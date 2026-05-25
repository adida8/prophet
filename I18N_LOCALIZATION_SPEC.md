# Odds Primer — Internationalization (i18n) Spec · v0.1

Goal: serve the Spanish-speaking market (LATAM-led). Two things ship:
the **site** reads in Spanish, and **The Desk** produces editorial copy
in Spanish. Built so a third language (French, Portuguese) is a new
locale, not another rebuild.

- **First locale:** neutral LATAM Spanish — BCP-47 `es-419`. No Spain-only idioms.
- **Canonical/base locale:** `en`. Everything falls back to `en` when a
  localized string or blurb is missing.
- **Locale set is data, not code.** A `LOCALES` list / `DESK_LOCALES` env
  var drives loops everywhere. Adding `fr` = add the locale + its content,
  no structural change.

This spec spans both products Adi owns end-to-end here (engine + site).
It is independent of the Faktor split — Adi is coding all of it.

---

## 0. The decision: native generation, not translation

The Desk generates Spanish copy **natively** with Haiku (a Spanish voice
guide + a Spanish system prompt), it does **not** machine-translate the
English blurb.

Why: the product *is* the voice — "a columnist who happens to write about
probability, dry, confident, never a tipster" (`desk/VOICE.md`). That
register does not survive a translation pass; you get flat, literal
Spanish that reads like a settings menu. Cost is not the constraint
(Haiku ≈ $0.003/article, one run amortizes across the whole slate via
prompt caching), so the marginal cost of a second language is one more
generation pass. We already have the forced-tool-use Haiku writer
(`desk/desk/explainer/haiku.py`) — localization parametrizes it by locale
rather than bolting on a translator.

**The one exception is quotes.** Never MT a source quote. The contract
already carries `Citation.quote_original` + `Citation.quote_lang`. The
Spanish edition prefers Spanish-language sources and renders their
verbatim `quote_original`; for English-only sources it shows the English
`quote` (optionally tagged "en"). Truthful attribution over uniform
language.

---

## 1. Contract change (ADR required)

Per `desk/desk/publish/contract.py` header + `THE_DESK_SPEC.md §6`, any
contract field needs an ADR. This is **ADR-i18n-1**.

The change is **purely additive** — `copy.title/summary/blurb/drivers`
stay English (canonical). A new locale-keyed map carries translations:

```python
# desk/desk/publish/contract.py

LangCode = Annotated[
    str, StringConstraints(min_length=2, max_length=8, pattern=r"^[a-z]{2}(?:-[a-z0-9]{2,4})?$")
]  # "es", "es-419", "pt-br", "fr"

class LocalizedCopy(BaseModel):
    """One locale's editorial prose. Mirrors the prose fields of Copy.
    editorial_citations are NOT duplicated here — they live once on Copy
    and the renderer picks quote vs quote_original by locale (see §1.1)."""
    model_config = ConfigDict(extra="forbid")
    title:   Annotated[str, StringConstraints(min_length=0, max_length=120)] = ""
    summary: Annotated[str, StringConstraints(min_length=0, max_length=400)] = ""
    blurb:   Annotated[str, StringConstraints(min_length=0, max_length=4000)] = ""
    drivers: list[Annotated[str, StringConstraints(min_length=1, max_length=200)]] = \
        Field(default_factory=list, max_length=6)

# add ONE field to the existing Copy model:
class Copy(BaseModel):
    ...
    i18n: dict[LangCode, LocalizedCopy] = Field(default_factory=dict)
```

Consumers reading `copy.title` are unaffected (still English). A localized
consumer reads `copy.i18n["es-419"]` and falls back to the top-level
English fields when the key or a sub-field is empty.

**Tasks in PR I1:**
- Add `LocalizedCopy` + `Copy.i18n` to `contract.py`.
- Regenerate `desk/contract.schema.json` and keep the in-sync test green.
- Write `desk/adr/ADR-i18n-1-localized-copy.md` (or wherever ADRs live —
  grep first; create the dir if none).
- No change to `Verdict`, `Venue`, `Competition` — those are codes /
  numbers / proper nouns the front-of-house localizes at render time
  (stage labels, venue country) from its own string tables, not the
  contract.

### 1.1 Quote-language resolution (render rule, not contract)

For locale `L`, when rendering a `Citation`:
- if `quote_lang` base-matches `L` (e.g. `es` ⊂ `es-419`) and
  `quote_original` is set → show `quote_original`.
- else → show `quote` (English).

Document this once; both the static generator (§3) and the React app (§4)
implement the same helper.

---

## 2. Desk content generation (PR I2)

### 2.1 Voice doc per locale

- Keep `desk/VOICE.md` (en, canonical).
- Add `desk/VOICE.es.md` — an **adaptation**, not a translation, of the
  four rules into es-419. Same spine (every blurb has a point; 5–8
  sentences; one real insight; every claim sourced, never invent a
  source). Add es-specific guidance: register is *usted*-neutral
  journalistic Spanish, no regionalisms (no "vos", no Spain-only "vale"),
  numbers/percentages in es format where the design system allows.

### 2.2 Haiku writer — parametrize by locale

`desk/desk/explainer/haiku.py` today loads `_VOICE_DOC` at import and bakes
one `_SYSTEM_PROMPT`. Refactor to a per-locale factory:

```python
def _voice_doc_for(locale: str) -> str: ...        # VOICE.md | VOICE.es.md (+ fallback)
def _system_prompt_for(locale: str) -> str: ...     # field instructions translated per locale
def try_haiku_copy(i: Inputs, *, locale: str = "en",
                   extractor: BlurbExtractor | None = None) -> LocalizedCopy | None: ...
```

- The system prompt's field instructions (title shape, "sentence case",
  summary length) are themselves written in/for the target locale.
- `editorial_citations` block in the user message is unchanged — the model
  attributes the same outlets; for es it may quote `quote_original` when
  the source is Spanish (extend `_format_citations` to pass
  `quote_original`/`quote_lang` so the model can quote in-language).
- Cache key note: the es system prompt is a *different* cached prefix from
  en — that's fine, each locale's slate amortizes against its own prefix.

### 2.3 Word-count window per locale

Spanish runs ~15–20% longer than English for the same content. Replace the
single `[_BLURB_MIN_WORDS, _BLURB_MAX_WORDS]` with a per-locale map:

```python
_BLURB_WORDS = {"en": (80, 220), "es": (90, 250)}   # keyed by base lang
```

### 2.4 Voice post-checks per locale

`desk/desk/explainer/voice.py`:
- Hard, language-agnostic rules stay global: **no exclamation marks, no
  emoji** — keep enforced for all locales.
- Banned-phrase list is English-specific → make it locale-keyed. Add an
  es banned list (tipster-speak: "no te lo pierdas", "apuesta segura",
  "ganador garantizado", etc.). `is_voice_clean(text, locale="en")`.
- Attribution allow-list check in `haiku.py` (`_ATTRIBUTION_RE`) is
  English ("per", "according to", "reported"). Add es patterns ("según",
  "informó", "según informó X"). Same fail-closed posture: an attribution
  to an outlet not in `editorial_citations` → reject → fall back.

### 2.5 Dispatcher — loop locales (`desk/desk/explainer/__init__.py`)

```python
def build_copy(i: Inputs) -> Copy:
    base = _stub_build_copy(i)                 # English, as today
    if _haiku.haiku_enabled():
        en = _haiku.try_haiku_copy(i, locale="en")
        if en: base = base.model_copy(update={...})  # existing overlay
    for loc in extra_locales():                # DESK_LOCALES minus "en"
        base.i18n[loc] = _localized_copy_for(i, loc)  # Haiku → es-stub fallback
    return base
```

`_localized_copy_for` tries `try_haiku_copy(i, locale=loc)`; on any failure
(no key, voice fail, word-count, attribution) falls back to a **localized
stub**. Add `desk/desk/explainer/stub.py` es templates (`build_localized_copy(i, locale)`)
so the es edition degrades to deterministic Spanish, never to English.
If even the stub can't (unknown locale), omit the key → renderer falls
back to English. **Localization never fails the pipeline.**

### 2.6 Env vars (add to `desk/desk/config.py` + CLAUDE.md table)

| Variable | Default | Purpose |
|---|---|---|
| `DESK_LOCALES` | `en` | Comma-list of output locales, e.g. `en,es-419`. Drives the dispatcher loop + which `copy.i18n` keys get written. |
| `DESK_VOICE_DOC_<LANG>` | unset | Optional path override for a locale's voice doc (e.g. `DESK_VOICE_DOC_ES`). |

`DESK_BLURB_HAIKU` / `ANTHROPIC_API_KEY` gate Haiku for **all** locales as
today. With Haiku off, every locale uses its stub.

---

## 3. Static site generator (PR I4) — `site/generate.py`

The generator renders `/`, `/matches`, `/m/{id}`, `/outrights`, `/o/{id}`
from Desk JSON. Localize by emitting a parallel locale tree and reading
`copy.i18n`.

### 3.1 Output tree

- `site/public/...` stays the **English / x-default** tree (root).
- `site/public/es/...` mirrors it: `es/index.html`, `es/matches/index.html`,
  `es/m/{id}.html`, `es/outrights/index.html`, `es/o/{id}.html`.

`main()` loops `for locale in SITE_LOCALES:` and writes into the locale's
prefix (`""` for en, `"es"` for Spanish).

### 3.2 Render functions take a locale

Thread a `locale` arg (or a small `Ctx`) through `render_home`,
`render_matches_index`, `render_match_page`, `render_outright_*`,
`chrome_head`, `chrome_masthead`, `chrome_footer`, `_render_sources_block`,
and the `fmt_*` date helpers.

- `chrome_head(...)`: `<html lang="{locale}">` (e.g. `es-419`); canonical =
  the locale's own URL; **emit hreflang alternates** on every page:

  ```html
  <link rel="alternate" hreflang="en"     href="https://oddsprimer.com{path}">
  <link rel="alternate" hreflang="es-419" href="https://oddsprimer.com/es{path}">
  <link rel="alternate" hreflang="x-default" href="https://oddsprimer.com{path}">
  ```
- Match/outright pages read prose from `match["copy"]["i18n"][locale]`
  with fallback to `match["copy"]`. Add `localized_copy(match, locale)`.
- `_render_sources_block`: apply the §1.1 quote rule.
- `fmt_kickoff_*`: localize month/day names. Stdlib `babel` is cleanest;
  if avoiding a dep, a small `{locale: {month_names...}}` table is fine.
  Numerics keep JetBrains Mono per design system.

### 3.3 Chrome strings table

UI chrome currently inlined in `chrome_masthead` / `chrome_footer` /
CTA helpers ("View source on", "Today's board", nav labels, edition
strip). Extract to `site/strings.py`:

```python
STRINGS = {
  "en": {"nav.matches": "Matches", "cta.view_source": "View source on", ...},
  "es-419": {"nav.matches": "Partidos", "cta.view_source": "Ver fuente en", ...},
}
def t(locale, key): return STRINGS.get(locale, STRINGS["en"]).get(key, STRINGS["en"][key])
```

### 3.4 Sitemap

Emit `site/public/sitemap.xml` with per-locale `<url>` + `<xhtml:link>`
alternates so Google indexes both trees. (If a sitemap already exists,
extend it; grep first.)

---

## 4. React editorial app (PR I5 + I6) — `frontend/src/op`

The editorial front-of-house (home, about, learn + 6 articles, world-cup)
is a path-routed SPA (`OpApp.jsx`, no router lib, pushState/popstate).

### 4.1 Stack

Add `i18next` + `react-i18next`. Provider at the `OpApp` root. Locale comes
from the URL prefix.

### 4.2 Locale routing (extend `readPath` in `OpApp.jsx`)

`readPath()` strips a leading `/es` segment, sets `locale`, then matches
the remaining path exactly as today:

```js
const LOCALE_PREFIXES = { "/es": "es-419" };
// "/es/learn/is-it-legal" -> locale "es-419", route "learn-article", slug "is-it-legal"
// "/learn/is-it-legal"    -> locale "en",     ...
```

`navigate(to)` and all masthead/footer links prepend the active locale
prefix. Add a **language switcher** in `op/Masthead.jsx` that swaps the
prefix on the *current* path (so `/learn` ↔ `/es/learn`).

### 4.3 String extraction

- UI chrome strings in `Masthead`, `Footer`, `FooterSignup`,
  `NewsletterPopup`, `StickyMobileBar`, `home/*` components → `t("key")`
  with `locales/en.json` + `locales/es-419.json` namespaces.
- The `META` table in `OpApp.jsx` (per-route title/description) becomes
  per-locale: `META[locale][key]`. `setMeta` also writes
  `<html lang>` and injects hreflang `<link>`s (see §4.5).

### 4.4 Learn articles — translated content, not just strings (PR I6)

The 6 articles (`pages/articles/*.jsx`) are long-form editorial JSX, not
UI labels. Don't shove paragraphs into JSON. Instead:

- Move article bodies into per-locale content modules:
  `pages/articles/es-419/IsItLegal.jsx` (etc.), or a content-map keyed by
  locale that the shared article shell renders.
- These are **adapted**, not literally translated — and note the legal
  primer (`IsItLegal`) is US-state-specific; the es version should speak
  to LATAM access/legality, not US states. Flag for editorial review.

This is the single largest manual chunk of the whole effort. Scope it as
its own PR.

### 4.5 SEO for the SPA (PR I7)

There is a known SPA SEO gap — see `SEO_MATCH_PAGES_NOTE.md` (referenced in
`OpApp.jsx`): client-set title/description is only a partial win. hreflang
for the React routes needs the same prerender/SSR fix. Until that lands:
- `setMeta` injects `hreflang` + `canonical` `<link>`s client-side
  (partial, but better than nothing).
- Add the React routes to the sitemap (§3.4).
- Pin the full fix to whatever prerender approach `SEO_MATCH_PAGES_NOTE.md`
  lands on — do it once for both languages.

### 4.6 Open dependency — which codebase serves the live site?

`prophet/CLAUDE.md` says oddsprimer.com is Railway-served (static gen +
React op). `market_tips_ai-1/CLAUDE.md` lists `oddsprimer.com` in
`B2C_APEX_HOSTS` on Vercel. **Confirm which actually serves production
before building §4** — if the live editorial site is the Next.js B2C app,
the React i18n work moves there (Next has its own i18n routing) and §4
changes target. §1–§3 (contract + Desk + static gen) are unaffected either
way. *Resolve this first.*

---

## 5. Spanish-language sources (PR I3) — `desk/desk/signals/data/sources_seed.csv`

The registry is already global + tag-driven (`resolve.py`). Adding es
sources helps **both** editions (the extractor produces English `quote` +
`quote_original`/`quote_lang=es`), and unlocks native Spanish quotes for
the es edition.

Add rows with `language=es` and region coverage tags. Candidates (verify
each feed live before committing, per the existing 21-May verification
discipline):

| id | name | feed | band | tags |
|---|---|---|---|---|
| marca | Marca | rss (verify) | ~0.8 | global, sport:football, region:es |
| diario-as | Diario AS | rss (verify) | ~0.8 | global, sport:football, region:es |
| mundo-deportivo | Mundo Deportivo | rss (verify) | ~0.75 | global, sport:football, region:es |
| ole | Olé (AR) | rss (verify) | ~0.75 | sport:football, region:latam, country:ar |
| espn-deportes | ESPN Deportes | rss (verify) | ~0.85 | global, sport:football, region:latam |
| tyc-sports | TyC Sports (AR) | rss (verify) | ~0.75 | sport:football, region:latam, country:ar |
| record-mx | Récord (MX) | rss (verify) | ~0.7 | sport:football, region:latam, country:mx |

- Extend `coverage_tags` vocabulary with `region:*` / `country:*`. Optional
  follow-up: `resolve.py` weights region-matching sources up for the es
  edition (a LATAM reader benefits from LATAM coverage). Pure enhancement;
  not required for v0.1.
- The existing `feed_type=none` trust-only pattern applies — list a source
  for trust weighting even if it has no usable public RSS yet.

---

## 6. PR ladder

| PR | Scope | Owner-area | Gated by |
|---|---|---|---|
| **I1** | Contract: `LocalizedCopy` + `Copy.i18n`, schema regen, ADR-i18n-1 | engine | — |
| **I2** | Desk es generation: `VOICE.es.md`, Haiku locale param, es stub, es voice rules, `DESK_LOCALES` | engine | I1 |
| **I3** | es source registry rows + region tags | engine | — (parallel) |
| **I4** | Static gen: locale tree, hreflang, chrome strings, es dates | site | I1 |
| **I5** | React app: i18next, `/es` routing, UI string extraction, language switcher | site | §4.6 resolved |
| **I6** | Translate/adapt the 6 Learn articles + long-form copy (es) | site/editorial | I5 |
| **I7** | SEO: hreflang/x-default both surfaces, per-locale sitemap, SPA prerender fix | site | I4, I5 |

Ship order: **resolve §4.6 → I1 → (I2 ∥ I3 ∥ I4) → I5 → I6 → I7.**
I1–I4 deliver Spanish *match/outright pages* (the Desk product) end-to-end
before the editorial-site translation lands.

---

## 7. Verification / test plan

**Contract (I1)**
- `contract.schema.json` in-sync test stays green after regen.
- Round-trip: a `MatchOutput` with `copy.i18n["es-419"]` validates;
  unknown sub-keys rejected (`extra="forbid"`); legacy JSON without `i18n`
  still validates (additive).

**Desk generation (I2)**
- With `DESK_LOCALES=en,es-419` + Haiku on (faked extractor), output has a
  populated `copy.i18n["es-419"]`.
- Haiku failure for es → es stub used, pipeline still succeeds, English
  unaffected.
- es voice-clean: exclamation/emoji rejected; es banned phrase rejected;
  es attribution to an outlet not in `editorial_citations` → fallback.
- es word-count window enforced.

**Sources (I3)**
- `desk signals validate` passes with new rows (fail-loud per row).
- New `region:*` tags resolve.

**Static site (I4)**
- Snapshot: `es/` tree emitted with all five page types.
- Each es page has `<html lang="es-419">` + the three hreflang links;
  en page has the reciprocal alternates.
- Quote rule (§1.1): es page shows `quote_original` for a Spanish source,
  English `quote` for an English-only source.

**React (I5/I6)**
- i18n key-coverage test: no key present in `en.json` missing from
  `es-419.json` (and vice versa).
- E2E (Playwright): visit `/es`, assert Spanish chrome; toggle switcher,
  assert path flips `/learn` ↔ `/es/learn` and content language changes.

**Final gate (subagent review):** before merge, run a verification pass
that (a) confirms every file path/symbol cited in the touched PRs exists,
(b) confirms no localized path can throw — every locale lookup has an
English fallback, (c) spot-checks 3 es blurbs against `VOICE.es.md` by eye.

---

## 8. Non-goals (v0.1)

- Right-to-left languages (no Arabic/Hebrew yet — would need CSS work).
- Locale-aware currency/number *parsing* (display only, per design system).
- Auto language detection / redirect by `Accept-Language` — explicit
  `/es` prefix + switcher only. (Revisit once both trees rank.)
- Translating the legacy Prophet trading dashboard (`/dashboard`) or
  Ledger — out of scope until the editorial surfaces are done.
