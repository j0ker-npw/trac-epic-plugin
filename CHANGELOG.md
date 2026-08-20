# Changelog

All notable changes to TracEpicPlugin are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/)
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.4.2] - 2026-08-20

This is a localization release adding full internationalization (i18n) support.

### Added
- **Internationalization (i18n)** with Babel/gettext integration. The plugin now follows the user's 
  Trac `Localization` settings, with automatic fallback to English (US) when translations are unavailable.
- **Russian (ru) translations** for all user-facing strings: UI labels, error messages, form placeholders, 
  pagination controls, and XML-RPC permission errors (36 strings total).
- **Translation domain** `tracepic` registered in all components (`EpicLinkSystem`, `EpicWebUI`, `EpicXmlRpc`) 
  via `domain_functions()` and `add_domain()`.
- Native Jinja2 template localization: all strings in `epic_section.html` use `{{ _('...') }}` syntax.
- Client-side (JavaScript) localization: server translates UI strings and passes them to `epic.js` via 
  `add_script_data` as `i18n` dictionary (prev/next buttons, confirmation dialogs, error messages).
- Babel configuration: `babel.cfg`, `message_extractors` in `setup.py`, `locale/` package data in 
  `pyproject.toml`.
- Complete translation catalog: `tracepic/locale/messages.pot` (template), `tracepic/locale/ru/LC_MESSAGES/tracepic.po` 
  (source), `tracepic/locale/ru/LC_MESSAGES/tracepic.mo` (compiled).

### Changed
- **Template syntax**: converted `epic_section.html` from Genshi-style comments (`##`) and variable 
  interpolation (`${}`) to proper Jinja2 syntax (`{# ... #}`, `{{ ... }}`).
- **Column labels** in `FIELD_LABELS` dictionary now wrapped in `N_()` for deferred translation 
  (actual translation happens in `_columns()` method when request context is available).
- **Date formatting**: `_decorate()` method now uses `trac_()` (Trac core domain) for relative 
  date strings ("in X", "X ago") to maintain consistency with Trac's own formatting.

### Technical
- Build dependency: `Babel>=2.9` added to `pyproject.toml` `requires`.
- Babel workflow commands available: `python setup.py extract_messages`, `init_catalog`, 
  `update_catalog`, `compile_catalog`.
- All 49 tests pass (47 Python + 2 JavaScript).

## [1.4.1] - 2026-08-20

This is a maintenance release addressing notification side-effects of epic link changes.

### Fixed
- **ITicketChangeListener notifications** are now fired after `add_link()` and `remove_link()` 
  operations. Previously, epic link changes were written directly to `ticket_change` via raw SQL, 
  bypassing `Ticket.save_changes()` and thus suppressing email notifications and other listener-based 
  side effects (timeline entries, webhook triggers, etc.).
- Both the epic and the linked ticket now receive a `ticket_changed` notification with appropriate 
  `old_values` (`{'epic_link': ''}` for add operations, `{'epic_link': '#<ticket_id>'}` for 
  remove operations).
- Individual listener failures are caught and logged, ensuring one misbehaving listener does not 
  prevent others from running or roll back the already-committed transaction.
- Ticket objects are loaded **after** the database transaction commits, guaranteeing listeners 
  receive the current ticket state.
- The `comment` argument from `add_link()` / `remove_link()` is now correctly forwarded to 
  `ticket_changed()` (previously was not passed).

### Technical
- Added private method `_notify_listeners()` in `EpicLinkSystem` (`tracepic/api.py`).
- Added imports: `TicketSystem` from `trac.ticket.api`, `Ticket` from `trac.ticket.model`.
- Extended test suite: `test_listeners_called_on_add_link` and `test_listeners_called_on_remove_link` 
  in `tests/test_api.py` verify two `ticket_changed` calls with correct `old_values` for each operation.
- All 49 tests pass (47 Python + 2 JavaScript).

## [1.4.0] - 2026-08-14

This release addresses the findings of a security & code review, hardening
authorization, database access and orphan cleanup, and adds automated CI.

### Security
- **Per-ticket authorization** on the link/unlink endpoint: instead of a single
  global `TICKET_MODIFY` check, the web handler now requires `TICKET_MODIFY` on
  *both* the epic and the ticket being linked (checked per-resource via
  `Resource('ticket', id)`), returning a proper `403` JSON response on denial.
- **RPC `removeEpicLink`** now requires `TICKET_MODIFY` on *both* the ticket and
  the epic before removing a link (previously only one side was checked).
- **Safe table-existence check**: `_table_exists` now validates names against a
  known-tables whitelist instead of interpolating arbitrary identifiers into SQL.
- Fixed per-resource permission checks that passed a `'ticket:N'` string where a
  real `Resource('ticket', N)` object was required, so fine-grained ticket
  policies are now actually enforced in the search and RPC paths.

### Added
- **Orphan cleanup**: the plugin now implements `ITicketChangeListener` and
  removes any `epic_links` rows referencing a ticket when that ticket is deleted.
- **GitHub Actions CI**: Python test matrix (3.9–3.13) plus a JavaScript logic
  test job.
- Expanded test suite: endpoint authorization/CSRF/validation tests and
  migration idempotency / multi-token tests.
- README documentation for the security & permissions model and the changelog
  field integration (English and Russian).

### Changed
- **DB-neutral search**: numeric search terms now match `id = %s OR
  LOWER(summary) LIKE %s` (no database-specific `CAST`), and the query is bounded
  by a SQL `LIMIT` in addition to the result-count cap.
- `add_link` now handles a concurrent-insert race gracefully (integrity errors
  are caught and reported as "link already exists" rather than raising).
- The jQuery-missing fallback in `epic.js` now emits a `console.warn` before
  degrading to a no-op stub.

## [1.3.0] - 2026-08-08

### Added
- **Configurable columns** via the new `[epic] linked_fields` option: a
  comma-separated, ordered list of the fields shown in the *Linked Tickets* /
  *Epics* table.  Available fields: `ticket`, `summary`, `component`, `type`,
  `status`, `owner`, `modified` and `priority`.  Unknown tokens are ignored
  and duplicates collapsed (first occurrence kept).  Defaults to
  `ticket,summary,type,status`.  The **Remove** button is always rendered as
  the last column, independently of this option.

### Changed
- **Closed tickets** now have their whole row greyed out (Trac-style),
  overriding the priority row colour, with muted text — in addition to the
  existing strike-through on the ticket-id link.  This makes finished work
  visually recede from the still-open, priority-coloured rows.

## [1.2.2] - 2026-08-08

### Added
- **Sortable columns** in the *Linked Tickets* / *Epics* table, exactly like
  Trac's report / query views: click a column header to sort by it; click the
  same header again to toggle ascending / descending.  The active column shows
  a `▴` / `▾` arrow.  Sortable columns: Ticket, Summary, Component, Type,
  Status, Owner, Modified and Priority.
- **Default sort** is configurable via the new `[epic] linked_default_sort`
  option, given as `<field>/<order>` (e.g. `priority/desc`, `modified/desc`).
  When unset it defaults to `priority/desc` (most severe tickets first).
- **Pagination**: when the number of linked tickets exceeds
  `[epic] linked_page_size` (default 10) the table is split into pages with
  Trac-style page buttons (« Prev / 1 2 3 … / Next »).  Paging preserves the
  current sort and shows a `Showing X–Y of N` summary.
- **Priority column**: a compact colour-coded badge (dot) whose colour matches
  the row priority, with the priority name shown on hover.  This keeps the
  Summary column wide instead of spending space on a text column.

### Changed
- **Priority column header** is now compact — a single letter "P" instead of
  the full word "Priority".  This saves horizontal space and gives more room to
  the Summary column.  The full label "Priority" is still shown in the sort
  link's `title` attribute (hover tooltip).
- The table body, sortable headers and pager are now rendered entirely by
  `epic.js` from the link data handed over via `add_script_data`.  The Jinja2
  fragment (`epic_section.html`) is now just the shell (title, header, empty
  body, pager container and add form).  This removes the previous duplication
  of row-rendering logic between the template and the JavaScript.

### Configuration
- New `[epic]` options in `trac.ini`:
  - `linked_default_sort` — default `<field>/<order>` sort (default
    `priority/desc`).
  - `linked_page_size` — rows per page before paginating (default `10`).

## [1.2.1] - 2026-08-07

### Changed
- **The "Modified" column now uses Trac's relative date style** in both the
  "Epics" and "Linked Tickets" tables: it shows a relative label such as
  `3 hours ago` (or `in 2 days`), with the full localized date/time revealed
  as a tooltip on hover -- matching Trac's own `pretty_dateinfo` output.
- `EpicWebUI._decorate()` now emits two fields for the modified timestamp:
  `modified` (the relative "... ago" label) and `modified_title` (the
  absolute date/time used for the hover tooltip).
- Template (`epic_section.html`) and JavaScript (`epic.js`) wrap the value in
  a `<span title="...">` so both the server-rendered and AJAX-updated rows
  display the tooltip identically.
- `epic.css` adds a `cursor: help` hint on the modified cell's span.

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
