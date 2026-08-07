# -*- coding: utf-8 -*-
"""Web UI for TracEpicPlugin.

This module wires the epic linking model into the Trac web interface:

* :class:`EpicWebUI` implements ``IRequestFilter`` to inject an "Epics" /
  "Linked Tickets" section into the ticket page, ``ITemplateProvider`` to
  publish the Jinja2 fragment and static resources, and
  ``IRequestHandler`` to serve the AJAX endpoints ``/epic/link`` and
  ``/epic/search``.

Because Trac 1.6 renders pages with Jinja2 (there is no Genshi stream
filter anymore), the ticket section is produced by rendering the
``epic_section.html`` fragment server side into an HTML string which is
handed to the browser via ``add_script_data``.  ``epic.js`` then injects it
into the ticket page and keeps it in sync over AJAX.
"""

import json
import re

from trac.core import Component, implements, TracError
from trac.perm import PermissionError
from trac.web.api import IRequestFilter, IRequestHandler, RequestDone
from trac.web.chrome import (ITemplateProvider, Chrome, add_script,
                             add_script_data, add_stylesheet)

from tracepic.api import EpicLinkSystem

EPIC_TYPE = 'epic'

_TICKET_PATH_RE = re.compile(r'^/ticket/(\d+)$')


class EpicWebUI(Component):
    """Ticket page integration and AJAX endpoints for epic links."""

    implements(IRequestFilter, IRequestHandler, ITemplateProvider)

    def __init__(self):
        self.epics = EpicLinkSystem(self.env)

    # ------------------------------------------------------------------
    # IRequestFilter
    # ------------------------------------------------------------------
    def pre_process_request(self, req, handler):
        return handler

    def post_process_request(self, req, template, data, metadata=None):
        """Inject the epic section into the ticket page.

        The signature accepts the optional ``metadata`` argument used by
        Trac 1.4+/1.6.  Older 5-tuple returning code paths are not needed.
        """
        match = _TICKET_PATH_RE.match(req.path_info or '')
        if match and data is not None and 'TICKET_VIEW' in req.perm:
            ticket = data.get('ticket')
            if ticket is not None and ticket.exists:
                try:
                    self._inject_epic_section(req, ticket)
                except Exception:
                    self.log.exception(
                        "TracEpicPlugin failed to render epic section for "
                        "ticket #%s", getattr(ticket, 'id', '?'))
        return template, data, metadata

    def _inject_epic_section(self, req, ticket):
        """Render the fragment and expose it to the browser."""
        ticket_id = int(ticket.id)
        is_epic = (ticket['type'] == EPIC_TYPE)
        can_modify = 'TICKET_MODIFY' in req.perm(ticket.resource)

        if is_epic:
            linked_ids = self.epics.get_tickets_for_epic(self.env, ticket_id)
        else:
            linked_ids = self.epics.get_epics_for_ticket(self.env, ticket_id)

        linked = []
        for lid in linked_ids:
            info = self.epics.get_ticket_summary(self.env, lid)
            if info:
                linked.append(info)

        frag_data = {
            'ticket_id': ticket_id,
            'is_epic': is_epic,
            'can_modify': can_modify,
            'linked': linked,
        }
        # render_fragment produces just the fragment (no page skeleton),
        # which is what we hand to the browser for injection.
        html = str(Chrome(self.env).render_fragment(
            req, 'epic_section.html', frag_data))

        add_script_data(req, {'tracepic': {
            'ticket_id': ticket_id,
            'is_epic': is_epic,
            'can_modify': can_modify,
            'html': html,
            'form_token': req.form_token,
            'base_url': req.href.epic(),
        }})
        add_stylesheet(req, 'tracepic/epic.css')
        add_script(req, 'tracepic/epic.js')

    # ------------------------------------------------------------------
    # ITemplateProvider
    # ------------------------------------------------------------------
    def get_templates_dirs(self):
        from pkg_resources import resource_filename
        return [resource_filename('tracepic', 'templates')]

    def get_htdocs_dirs(self):
        from pkg_resources import resource_filename
        return [('tracepic', resource_filename('tracepic', 'htdocs'))]

    # ------------------------------------------------------------------
    # IRequestHandler
    # ------------------------------------------------------------------
    def match_request(self, req):
        return req.path_info in ('/epic/link', '/epic/search')

    def process_request(self, req):
        if req.path_info == '/epic/link':
            return self._handle_link(req)
        elif req.path_info == '/epic/search':
            return self._handle_search(req)
        raise TracError("Unknown epic endpoint: %s" % req.path_info)

    # -- endpoint: /epic/link (POST) -----------------------------------
    def _handle_link(self, req):
        """Add or remove a link.  Expects a POST with ``action``,
        ``epic_id`` and ``ticket_id``.  Returns JSON."""
        if req.method != 'POST':
            return self._send_json(req, {'error': 'POST required'}, status=405)

        # CSRF protection: validate Trac's form token explicitly.
        req.perm.require('TICKET_MODIFY')
        token = req.args.get('__FORM_TOKEN')
        if token != req.form_token:
            return self._send_json(
                req, {'error': 'Invalid form token'}, status=400)

        action = req.args.get('action')
        try:
            epic_id = int(req.args.get('epic_id'))
            ticket_id = int(req.args.get('ticket_id'))
        except (TypeError, ValueError):
            return self._send_json(
                req, {'error': 'epic_id and ticket_id must be integers'},
                status=400)

        author = req.authname or 'anonymous'
        try:
            if action == 'add':
                changed = self.epics.add_link(
                    self.env, epic_id, ticket_id, author)
            elif action == 'remove':
                changed = self.epics.remove_link(
                    self.env, epic_id, ticket_id, author)
            else:
                return self._send_json(
                    req, {'error': 'Unknown action: %r' % action},
                    status=400)
        except TracError as exc:
            return self._send_json(req, {'error': str(exc)}, status=400)

        # Return the refreshed link list for the ticket that the user is
        # currently viewing (identified by ``view_id``, defaulting to the
        # ticket that is not the epic when unspecified).
        view_id = req.args.getint('view_id', ticket_id)
        links = self._links_payload(req, view_id)
        return self._send_json(req, {
            'ok': True,
            'changed': bool(changed),
            'action': action,
            'links': links,
        })

    # -- endpoint: /epic/search (GET) ----------------------------------
    def _handle_search(self, req):
        """Autocomplete search over ticket summaries.  Returns JSON list."""
        req.perm.require('TICKET_VIEW')
        term = (req.args.get('q') or req.args.get('term') or '').strip()
        only = req.args.get('only')  # 'epic' | 'ticket' | None
        exclude = req.args.getint('exclude', 0)

        results = self._search_tickets(req, term, only, exclude)
        return self._send_json(req, {'results': results})

    def _search_tickets(self, req, term, only, exclude):
        """Run the summary/id search honouring ``TICKET_VIEW`` permission."""
        clauses = []
        params = []

        if term:
            if term.lstrip('#').isdigit():
                clauses.append("(CAST(id AS text) LIKE %s OR "
                               "LOWER(summary) LIKE %s)")
                like = '%' + term.lstrip('#').lower() + '%'
                params.extend([like, like])
            else:
                clauses.append("LOWER(summary) LIKE %s")
                params.append('%' + term.lower() + '%')

        if only == 'epic':
            clauses.append("type=%s")
            params.append(EPIC_TYPE)
        elif only == 'ticket':
            clauses.append("type!=%s")
            params.append(EPIC_TYPE)

        if exclude:
            clauses.append("id!=%s")
            params.append(exclude)

        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        sql = ("SELECT id, summary, status, type FROM ticket" + where +
               " ORDER BY id DESC")

        results = []
        for tid, summary, status, ttype in \
                self.env.db_query(sql, tuple(params)):
            resource = 'ticket:%d' % tid
            # Respect fine grained permission policies.
            if 'TICKET_VIEW' not in req.perm(resource):
                continue
            results.append({
                'id': tid,
                'summary': summary,
                'status': status,
                'type': ttype,
                'label': '#%d: %s' % (tid, summary),
            })
            if len(results) >= 20:
                break
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _links_payload(self, req, view_id):
        """Return the current links for *view_id* as JSON-ready dicts."""
        info = self.epics.get_ticket_summary(self.env, view_id)
        if info is None:
            return []
        is_epic = (info['type'] == EPIC_TYPE)
        if is_epic:
            ids = self.epics.get_tickets_for_epic(self.env, view_id)
        else:
            ids = self.epics.get_epics_for_ticket(self.env, view_id)
        payload = []
        for lid in ids:
            linfo = self.epics.get_ticket_summary(self.env, lid)
            if linfo:
                payload.append(linfo)
        return payload

    def _send_json(self, req, obj, status=200):
        """Serialise *obj* to JSON and end the request."""
        body = json.dumps(obj).encode('utf-8')
        req.send_response(status)
        req.send_header('Content-Type', 'application/json;charset=utf-8')
        req.send_header('Content-Length', str(len(body)))
        req.end_headers()
        req.write(body)
        raise RequestDone
