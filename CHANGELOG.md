# Changelog

All notable changes to TracEpicPlugin are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/)
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.2.0] - 2026-08-07

### Changed
- **Enhanced visual styling** to match Trac's default ticket UI:
  - Epic/Linked-Tickets sections now have the same pale-yellow background,
    border and rounded corners as the ticket Description box (`#ticketbox`).
  - Section title now matches the "Description" heading style (color `#663`,
    bottom border `#dd9`).
- **Ticket table rows are now colour-coded by priority**, matching Trac's
  default report/query scheme:
  - `blocker` → light red (`#fdc`/`#fed`)
  - `critical` → yellow (`#ffb`/`#ffd`)
  - `major` → pale grey (`#fbfbfb`/`#f6f6f6`)
  - `minor` → cyan (`#e7ffff`/`#dff`)
  - `trivial` → blue (`#e7eeff`/`#dde7ff`)
  - Alternating odd/even row shading remains.
- **Closed tickets** now display with a line-through strike on the ticket ID
  link (CSS `a.closed`, as elsewhere in Trac).
- `EpicLinkSystem.get_ticket_summary()` now also returns `priority` and
  `priority_value` (the numeric enum value) so the web UI can apply the
  correct `prioN` CSS class to each row.
- `EpicWebUI._decorate()` normalises `priority_value` to a string (e.g. `'1'`
  for blocker) or empty string when undefined.
- Template (`epic_section.html`) and JavaScript (`epic.js`) assign row classes
  `odd`/`even` + `prioN` and conditionally add `class="closed"` to ticket
  links when `status == 'closed'`.
- `epic.css` now defines the full `prioN` colour palette scoped to
  `#epic-links` (as `report.css` is not loaded on the ticket page).
- Added `tests/test_api.py::test_get_ticket_summary_priority_value` to verify
  priority-value lookup logic.

## [1.1.0] - 2026-08-07

### Changed
- **Expanded the linked-tickets table** in both the "Epics" section (on
  regular tickets) and the "Linked Tickets" section (on epic tickets). The
  columns are now displayed in this order:
  **Ticket · Summary · Component · Type · Status · Owner · Modified · (Remove)**.
- `EpicLinkSystem.get_ticket_summary()` now also returns `component`,
  `owner` and the raw `changetime` alongside `summary`, `type` and `status`.
- The web UI formats `changetime` into a localized **Modified** string using
  the viewer's timezone (`user_time` + `format_datetime`) and normalises
  empty `component`/`owner` values so cells never render `None`.
- Server-rendered template (`epic_section.html`) and the AJAX re-render path
  (`epic.js`) both build the new column set, so the table stays consistent
  after adding/removing links without a page reload.
- Added per-column CSS classes (`epic-col-component`, `epic-col-owner`,
  `epic-col-modified`, …) in `epic.css`.

## [1.0.2] - 2026-08-07

### Changed
- **Migrated packaging to `pyproject.toml` (PEP 621 / PEP 517/518)** — the
  project now declares its metadata, build backend and entry points in a
  single standards-based file; `setup.cfg` has been removed.
- License is now declared as an SPDX expression (`License-Expression:
  BSD-3-Clause`, PEP 639) instead of the deprecated license classifier.

### Fixed
- Silenced the `Package 'tracepic.htdocs' / 'tracepic.templates' is absent
  from the packages configuration` warnings by enabling namespace discovery
  (`[tool.setuptools.packages.find] namespaces = true`). The data
  directories are packaged correctly and no longer trigger discovery
  warnings under modern setuptools (>= 77).
- `python -m build` now produces a **warning-free** universal wheel and sdist.

### Notes
- Building an `*.egg` for Trac's `plugins/` directory still uses the legacy
  `setup.py bdist_egg` command, which emits a single unavoidable
  `setup.py install is deprecated` notice. This is intrinsic to the egg
  format (which Trac requires for drop-in plugins) and is harmless. For
  virtual-environment installs use the wheel produced by `python -m build`,
  which is completely warning-free.

## [1.0.1] - 2026-08-07

### Fixed
- Removed deprecated `License :: OSI Approved :: BSD License` classifier in favor of SPDX `BSD-3-Clause` license expression
- Fixed packaging warnings about missing `tracepic.htdocs` and `tracepic.templates` by using `packages = find:` in setup.cfg
- Added explicit `LICENSE` file to package distribution
- Updated build instructions to use `python3 -B setup.py bdist_egg` to avoid byte-compilation permission issues

### Changed
- Enhanced Python version classifiers to explicitly list 3.9 through 3.13

## [1.0.0] - 2026-08-07

### Added
- Initial release of **TracEpicPlugin** for Trac 1.6 (Python 3.13,
  PostgreSQL 13).
- `epic_links` table with an M:N relationship between epic tickets and
  regular tickets (`UNIQUE(epic_id, ticket_id)`).
- `EpicLinkSystem` (`IEnvironmentSetupParticipant`): schema creation,
  versioned upgrade, and one-time migration of legacy `epic` /
  `parent_epic` custom fields.
- Query/mutation API: `get_epics_for_ticket`, `get_tickets_for_epic`,
  `add_link`, `remove_link` with changelog writes for both tickets.
- `EpicWebUI` (`IRequestFilter`, `ITemplateProvider`, `IRequestHandler`):
  injects an "Epics" / "Linked Tickets" section into the ticket page.
- AJAX endpoints `/epic/link` (add/remove) and `/epic/search`
  (autocomplete) with CSRF (form token) protection.
- Jinja2 fragment `epic_section.html`, client logic `epic.js`
  (jQuery 3.7.1), and styles `epic.css`.
- XML-RPC API via `tracrpc` (`EpicXmlRpc`): `ticket.getEpics`,
  `ticket.getEpicLinkedTickets`, `ticket.addEpicLink`,
  `ticket.removeEpicLink` with permission checks.
- Bilingual (RU/EN) documentation and unit tests.
