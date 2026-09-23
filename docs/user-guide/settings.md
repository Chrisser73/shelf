# Settings

Open the menu under your username and choose **Settings**. Settings is available to administrators; account profile and password controls remain under **Account** in the same menu.

The Settings page is organised into four sections, listed in a sidebar on a wide screen and as a row of buttons above the content on a narrow one:

- **Library** — collection display, lending, locations, **tags**, game platforms, navigation preferences and **Trash** retention.
- **Integrations** — Audiobookshelf, Hardcover, metadata providers, valuation and vision services.
- **Data** — CSV and portable-archive import/export, backups and maintenance tools.
- **Users** — accounts, roles and access administration.

The selected section is remembered in the browser, so returning to Settings opens the area you were working in. The redesign changes navigation and presentation only: existing settings forms, endpoints and stored values keep their current behaviour.

## Trash retention

Settings → Library → **Trash** sets **Prompt to empty Trash after** — how many
days a deleted item or copy stays in [Trash](items.md#trash) before it counts
as *expired*. The default is **180**; **0** means nothing ever expires and the
prompt never appears.

Nothing is deleted on a timer. When rows pass the window, every admin sees a
banner across the top of each page — *N items in Trash have been there longer
than your retention window* — linking to the expired rows, where **Empty
expired** deletes them permanently. **Dismiss** hides the banner on every
device until more rows expire. Changing the setting takes effect at once.

## Tags

Settings → Library → **Tags** lists every tag with the number of items that
carry it (items in Trash are not counted). Admin only. A tag is created by
applying it to an item — on the item page, the edit page, the Browse bulk bar
or through [Default tags](scanning.md#default-tags) — so there is no **Add**
here.

- **Rename** — open **Edit**, change the name, **Save tag**. Every item keeps
  the tag under its new name. Renaming onto a name another tag already has
  (in any case) is refused: merging two tags is not supported yet. Changing
  only the case, `signed` → `Signed`, is fine.
- **Scope** — the same **Edit** form sets a media type, or **All types**. A
  scope only narrows the suggestions a tag appears in (the item pages, the
  Default tags field); it never removes the tag from an item of another
  type, and nothing stops you adding it to one. A scoped tag shows how many
  of its items fall outside the scope — *3 outside Book* — so a mismatch is
  visible rather than silent.
- **Delete** — removes the tag from every item carrying it, including items
  in Trash, after a confirmation. It cannot be undone.

Saved **Default tags** are not updated. Renaming or deleting a tag leaves the
old name in any Default tags field on Scan, Shelf Fill or Photo Intake that
still holds it, on this device and on others — and the next item filed there
creates the old tag again. Clear or retype those fields after a rename.
