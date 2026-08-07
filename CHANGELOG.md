# Changelog

All notable changes to TracEpicPlugin are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/)
and this project adheres to [Semantic Versioning](https://semver.org/).

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
