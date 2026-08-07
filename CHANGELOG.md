# Changelog

All notable changes to TracEpicPlugin are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/)
and this project adheres to [Semantic Versioning](https://semver.org/).

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
