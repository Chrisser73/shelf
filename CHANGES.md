# Shelf – Changes in This Fork

This file is the central record of customizations in this fork. The upstream
[`README.md`](README.md) continues to document Shelf itself; this file covers
only added or changed fork-specific features.

## V1.2.3 — Upgrade V1.2.3

- **Game metadata is configurable where it matters.** Settings now lets an
  administrator choose which empty game fields make an item count as *Missing
  game data*. The Home tile and Browse filter use exactly that selection.
  Platform also has an **Unknown** tile and filter for games with no assigned
  platform.
- **Browse is easier to tailor.** Users can choose the visible filters,
  including Lent out, Platform, Tag and Author. Grid density can be adjusted
  with **Grid**, **Grid +1**, **Grid +2** or **Grid +3** at every screen size.
- **Editing games needs fewer page changes.** Developer, Publisher, Language
  and Year can be edited inline from the item page with consistent icon-only
  save controls. Region, Platform and Collector state remain controlled
  dropdowns in the details form; Language now includes Unknown.
- **Bulk editing covers more collection work.** Platform and Collector state
  can be applied to a selection, and the page reserves space below the bulk
  action bar so it no longer covers the last items.
- **Photo Intake identifies game collections more carefully.** Recognition
  now reads shelves and spines as shared platform context, avoids treating
  logos as titles, checks rotated spines, improves PAL/USK/PEGI and language
  inference, and fills developer, publisher and year once a game is securely
  identified. Confirmed IGDB lookups now retain the developer as well as
  publisher and year before cover recovery begins.
- **Long-running intake actions are easier to follow.** Photo analysis and
  item confirmation show their current Shelf phase and a progress indicator,
  from image preparation through recognition, metadata matching and saving.
- **Metadata maintenance filters now follow their configuration exactly.**
  The Name checkbox checks the actual catalogue title rather than the optional
  alternate title, and existing saved selections are migrated automatically.
  Browse also offers one **Missing** filter for unset name, alternate name,
  developer, publisher, platform, region, language, year or collector state.
- **Collection cards are less noisy when desired.** The per-user Appearance
  settings can hide the New label. The Home **Unknown platform** tile appears
  only when at least one game needs a platform.
- **Maintenance links land in the right place.** Reviewing missing game
  metadata now opens the Library settings tab and scrolls directly to its
  configuration section.
- **Browse filter choices now persist after every result refresh.** Missing
  cover is part of the central Missing filter, and the Home tile opens that
  same filter instead of a separate control.
- **Missing values can be combined.** The Missing filter is now a checkbox
  menu, so one Browse view can include several empty metadata fields at once.
  Opening it from the Missing game metadata tile preselects the configured
  fields in that menu.
- **The Missing menu behaves like the other custom menus.** It has a Lucide
  chevron that rotates with its state and closes when clicking outside it.
- **List sorting uses consistent Lucide controls.** Neutral, ascending and
  descending sort states use the same icon set as the Browse toolbar.
  Those icons now also render after asynchronous sorting and filtering.
- **Wishlist status is clearer in the collection.** Wishlisted items use a
  filled primary-colour heart beside the list cover and before the collector
  state on grid cards. Their detail page now has a direct add/remove button.
  Appearance settings can hide those collection hearts per user.

## V1.2.2 — Upgrade V1.2.2

- Photo Intake is more useful for games and international releases: it now
  captures language, region, alternate searchable names, publisher, developer
  and release year, while preserving titles in their original script. The
  review screen makes those fields easy to correct before saving.
- AI recognition prompts and validation were strengthened for front-cover
  scans. Recognized titles retain their exact edition name, alternate names
  are normalized for searching, and malformed legacy Unicode escapes are
  repaired on display and on future saves.
- Collection browsing is more practical on desktop and mobile: list columns
  can be selected and sorted, filters include region and missing covers, text
  matches are highlighted, and filter state survives opening an item and
  returning to the collection.
- Item pages and bulk editing now support alternate names, language and region
  alongside existing collection metadata. The inline alternate-name editor
  gives clear save feedback and returns to its normal read-only view.
- The installable web app and sign-in experience were polished for mobile,
  including updated app icons, a persistent Remember me option, and reliable
  navigation back to the collection when Store Mode is disabled.
- Platform coverage and metadata tooling were extended with Nintendo Switch 2,
  additional platform-logo mappings, provider connection status, and more
  resilient IGDB cover and game-metadata lookups.
- Photo Intake now treats releases for different game platforms as distinct
  physical editions when checking for an existing item. A Nintendo Switch scan
  therefore cannot offer an identically named Nintendo Switch 2 entry for
  replacement.

## V1.2.0.1 — Upgrade V1.2.1

- Locations can be made the current user's default while creating or editing
  them; Photo Intake selects that location automatically. Browse list view
  now starts with Platform, Publisher, Year and Collector state after Title.
- Photo Intake exposes an **Edit Config** shortcut to its Settings card and
  displays the last Ollama connection check beside Provider. Settings can run
  that check with toast and inline success/error feedback. Mac defaults to
  the bundled Apple Macintosh platform logo.
- Photo Intake now offers **Cancel** for a running analysis. Replacing a
  photo, leaving the page, or a client-side analysis error also cancels the
  active Shelf task, which closes the outstanding Ollama request instead of
  leaving it to continue in the background. Intake and add failures now also
  appear as error toasts.
- Cancelled analyses return a clear confirmation instead of an invalid JSON
  error. The recognition prompt explicitly preserves titles in Japanese and
  other non-Latin scripts rather than translating or romanizing them.
- A single slow Ollama vision request may now run for just over 18 minutes,
  leaving headroom below the documented 20-minute reverse-proxy setting.
- Settings can retrieve the models installed on the configured Ollama server
  and presents them in a selectable list, marking models which report vision
  capability. The refresh control re-reads the server after a model is pulled.
- The global **Features** controls now consistently govern the matching UI.
  When Lending is off, Scan no longer offers Lend or Return, the Home "Lent
  out" tile and its personal Appearance option are hidden, and the Lending
  settings card points to Features instead of exposing inactive controls.
  A browser that remembered Lend or Return automatically returns to Add.
- When Statistics is off, its direct Home link is hidden too.
- These are availability rules for the whole Shelf; personal Appearance
  preferences are deliberately retained and become visible again when the
  feature is enabled. No collection or lending data is deleted.
- Browse now supplies platform labels consistently to both first-page and
  asynchronously refreshed list views, including the optional Platform
  column.
- The current default location is marked with a blue **Default** badge in
  Settings and with `(default)` in both Photo Intake location selectors.
- In Collection list view, data columns can be sorted directly from their
  headers. The active direction is shown with an arrow and uses the same
  single server-side sort as the standard Sort by control.
- The Photo Intake Settings card owns its stable `#photo-intake-vision` link
  and connection test; the Discogs integration card now keeps the same visual
  spacing as the other integrations. The bundled platform list also adds Mac
  on startup without altering user-created platforms.
- Photo Intake offers provider-specific model and reasoning selectors for
  Anthropic and OpenAI. The defaults prioritize efficient image recognition:
  Claude Haiku 4.5 with no forced thinking, or GPT-6 Luna at low reasoning.
  API-key expiry is explicitly marked as unavailable where the providers do
  not expose it through the ordinary key.

## V1.0.0 — Upgrade V1

This first fork release bundles the platform-aware game catalogue, Lucide UI
icons, enhanced photo intake and metadata retrieval, collector states, cover
recovery, configurable Home tiles, and ARM64 container publishing described
below. Use the Git tag `v1.0.0`; its human-readable release title is **Upgrade V1**.

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

The Shelf favicon and installable web-app icon are based on
[Papirus icon theme](https://github.com/PapirusDevelopmentTeam/papirus-icon-theme)
by [PapirusDevelopmentTeam](https://github.com/PapirusDevelopmentTeam).

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

- Non-book physical collection items can be marked as **CIB**, **Boxed**, or **Loose** during manual add, photo intake,
  or editing. Browse can filter by
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

- Each user can choose which default Home summary tiles are visible under **Settings → Library → Appearance → Home**.
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
