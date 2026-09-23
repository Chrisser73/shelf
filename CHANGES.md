# Shelf – Changes in This Fork

This file is the central record of customizations in this fork. The upstream
[`README.md`](README.md) continues to document Shelf itself; this file covers
only added or changed fork-specific features.

## V1.0.0 — Upgrade V1

This first fork release bundles the platform-aware game catalogue, Lucide UI
icons, enhanced photo intake and metadata retrieval, collector states, cover
recovery, configurable Home tiles, and ARM64 container publishing described
below. Use the Git tag `v1.0.0`; its human-readable release title is
**Upgrade V1**.

## Game Platforms on the Home Page

- The Home page shows a tile for every platform with catalogued video games.
- Every tile contains the platform name, game count, and platform logo when
  available.
- Clicking a tile opens Browse already filtered to that platform.
- Counts and filtering use the existing platform metadata (`game_platforms` and
  `items.platform`), not duplicate tags. Only video games are included.

## Platform Filter

- Browse includes a platform filter with dynamic result counts.
- The filter combines with the other Browse filters and only considers video
  games.
- A platform's stored slug can be explicitly chosen when creating it:
  `Testconsole (blubb)` displays **Testconsole** and uses `blubb` for filters,
  game metadata, and logo mappings. Without a non-empty value in parentheses,
  the existing automatic slug generation is retained.

## Platform Logos

- **Settings → Library → Platform Logos** maps a platform to a logo file.
- Creating or changing a mapping is saved directly with **Save mapping**; there
  is no second global save step.
- SVG selection shows readable logo names rather than internal file paths.
  Personal mappings override the built-in first guesses.
- Default mappings are only first guesses and can be changed at any time in
  Settings.
- The pinned source SVGs are downloaded by `make setup` (or
  `make platform-logos`) into ignored `static/icons/platforms`; they are not
  carried in this fork's Git history.

The monochrome platform logos come from
[HVR88/Monochrome-Gaming-Logos](https://github.com/HVR88/Monochrome-Gaming-Logos).
Please observe that project's license and notices when distributing or changing
logos.

## Personal Collection Appearance

- Under **Settings → Library → Appearance**, every user can independently
  choose whether game titles are always visible in the Collection.
- Platform-logo display can also be enabled per user. The logo then appears as
  a 32-px icon at the top-left of applicable game cards.
- The platform-logo checkbox now always reflects its saved per-user value, so
  the Settings control and rendered game cards remain in sync.

## Local Development on Windows/WSL

- `make dev` builds and starts the Docker development instance at
  `https://localhost:18889`.
- Docker Compose explicitly publishes the HTTPS port so the instance is also
  reachable from a Windows browser.
- `make dev-local` starts a local Uvicorn development server with hot reload at
  `http://localhost:8000`.
- Local development also starts Tailwind in watch mode and BrowserSync. The
  development view is `http://localhost:3000`: CSS is injected without a manual
  refresh, while template, JavaScript, and Python changes reload the page.
- Styling uses Tailwind CSS v4 with a CSS-based theme definition in
  `static/css/input.css`; `tailwind.config.js` is no longer needed.

## Feedback and Intake

- Shelf now uses reusable, accessible Success, Error, Warning, and Info toast
  notifications. They slide in, remain visible for 2.5 seconds, then slide
  out; simultaneous notifications stack with a 12-px gap.
- Settings actions now use the same feedback system for their asynchronous
  operations, including connection tests, imports, syncs, and save actions.
- The low-resolution Intake warning includes **Try anyway**, which submits the
  selected photo for analysis without requiring the user to leave the warning.
- Ollama Intake explicitly treats recognizable cartridges, discs, box art, and
  covers as catalog items. This prevents the legacy JSON key `books` from
  making a local model discard recognizable video games.
- Scan review rows now keep each title on its own line, with a separator
  between entries. Video games show **Publisher** rather than Author and ISBN,
  and their detected platform is normalized to the configured Shelf slug (for
  example, `Nintendo 64` and `N64` become `n64`).
- **Fetch & Add to Library** fetches type-specific metadata before saving.
  Games use IGDB with the title, platform, and available year as the lookup
  context; DVDs use TMDb.
- Intake also offers **Just add** for selected rows when the photographed text
  is already correct and no external metadata lookup is wanted.

## Collector States and Cover Recovery

- Non-book physical collection items can be marked as **CIB**, **Boxed**, or
  **Loose** during manual add, photo intake, or editing. Browse can filter by
  the saved state.
- The Home "Missing covers" number opens the matching filtered collection.
  Administrators can retry it directly from the card; book items use the book
  cover flow, games use IGDB, and DVDs use TMDb. Game and DVD retries keep the
  item title as the primary query and pass platform and release year where
  available.
- Vision intake now asks for publisher, release year, platform and a physical
  collector state when those details are visible. All-caps OCR titles are
  converted to readable title case while normally-cased transcriptions remain
  untouched.
- Platform matching first uses exact slugs/names and then the longest contained
  configured platform key. This covers variants such as Nintendo 64 DD without
  hard-coding each console variant.

## Home and Cover Editing

- Each user can choose which default Home summary tiles are visible under
  **Settings → Library → Appearance → Home**.
- Collection cards can optionally show their saved collector state below the
  title.
- Cover controls use the consistent name **Edit cover**. The item edit page
  includes upload, public URL, provider search, and remove actions.

## ARM64 Container Publishing

- `.github/workflows/docker-publish.yml` builds and publishes an ARM64 image
  to `ghcr.io/chrisser73/shelf` on every push to `main` and `feature/**`, as
  well as through a manual workflow run.

## Small Interface Improvements

- Select controls, buttons, and links use the pointer cursor consistently.
- The Platform Logos selector has padded space for its chevron and flips the
  chevron while open, resetting it as soon as a selection changes.
- Infinite-scroll spinners are centered as an overlay in their loading space.
- The photo-intake flow uses generic item terminology and asks the vision model
  to classify books, audiobooks, movies, music, comics, and video games.
- Toast notifications are centered at the top of the viewport.
- The navigation uses 20-px Lucide icons that inherit the active or hover text
  color. It uses Lucide's official `data-lucide` and `createIcons` API with a
  locally served, pinned package bundle; `make setup` prepares that bundle.
