# -*- coding: utf-8 -*-
"""Request-handler / authorization tests for :mod:`tracepic.web_ui`.

These exercise the AJAX endpoints ``/epic/link`` and ``/epic/search``
directly, covering the pieces the model-level tests do not:

* CSRF form-token validation,
* HTTP method enforcement,
* JSON error envelopes / status codes,
* and -- most importantly -- the *per-ticket* ``TICKET_MODIFY`` check that
  guards link mutation (security review 2.1).  ``DenyTicketModifyPolicy``
  below denies ``TICKET_MODIFY`` on one specific ticket so we can assert a
  user who holds the permission globally is still rejected for that ticket.
"""

import json
import unittest

from trac.core import Component, implements
from trac.perm import IPermissionPolicy, PermissionSystem
from trac.test import EnvironmentStub, MockRequest
from trac.ticket.model import Ticket
from trac.web.api import RequestDone

from tracepic.web_ui import EpicWebUI
from tracepic.api import EpicLinkSystem


class DenyTicketModifyPolicy(Component):
    """Permission policy that denies ``TICKET_MODIFY`` on a single ticket.

    The denied ticket id is taken from ``[epic-test] denied_ticket`` so tests
    can point it at whichever ticket they created.
    """

    implements(IPermissionPolicy)

    def check_permission(self, action, username, resource, perm):
        denied = self.env.config.getint('epic-test', 'denied_ticket', 0)
        if (action == 'TICKET_MODIFY' and denied and resource is not None
                and resource.realm == 'ticket'
                and str(resource.id) == str(denied)):
            return False
        return None  # defer to the next policy


class DenyTicketViewPolicy(Component):
    """Permission policy that hides one ticket via denied ``TICKET_VIEW``.

    The hidden ticket id comes from ``[epic-test] hidden_ticket`` so the
    search test can assert per-resource ``TICKET_VIEW`` filtering.
    """

    implements(IPermissionPolicy)

    def check_permission(self, action, username, resource, perm):
        hidden = self.env.config.getint('epic-test', 'hidden_ticket', 0)
        if (action == 'TICKET_VIEW' and hidden and resource is not None
                and resource.realm == 'ticket'
                and str(resource.id) == str(hidden)):
            return False
        return None


def _make_ticket(env, summary, ttype='task', status='new'):
    ticket = Ticket(env)
    ticket['summary'] = summary
    ticket['type'] = ttype
    ticket['status'] = status
    return ticket.insert()


def _call(handler, req):
    """Invoke *handler(req)*, absorbing the ``RequestDone`` it raises, and
    return ``(status_code, parsed_json_body)``."""
    try:
        handler(req)
    except RequestDone:
        pass
    status = req.status_sent[0] if req.status_sent else '200 OK'
    code = int(status.split(' ', 1)[0])
    body = req.response_sent.getvalue()
    data = json.loads(body.decode('utf-8')) if body else None
    return code, data


class LinkEndpointTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(
            enable=['trac.*', 'tracepic.*',
                    'tests.test_handlers.DenyTicketModifyPolicy'],
            default_data=True)
        EpicLinkSystem(self.env).upgrade_environment()
        self.ui = EpicWebUI(self.env)
        self.epic = _make_ticket(self.env, 'Epic', ttype='epic')
        self.task = _make_ticket(self.env, 'Task')

    def tearDown(self):
        self.env.reset_db()

    def _grant(self, user, *perms):
        ps = PermissionSystem(self.env)
        for p in perms:
            ps.grant_permission(user, p)

    def _req(self, **args):
        req = MockRequest(self.env, method='POST', authname='bob', args=args)
        req.args['__FORM_TOKEN'] = req.form_token
        return req

    # -- method / CSRF -------------------------------------------------
    def test_get_is_rejected(self):
        self._grant('bob', 'TICKET_MODIFY')
        req = MockRequest(self.env, method='GET', authname='bob')
        code, data = _call(self.ui._handle_link, req)
        self.assertEqual(405, code)
        self.assertIn('POST', data['error'])

    def test_invalid_form_token_rejected(self):
        self._grant('bob', 'TICKET_MODIFY')
        req = MockRequest(self.env, method='POST', authname='bob',
                          args={'action': 'add', 'epic_id': str(self.epic),
                                'ticket_id': str(self.task),
                                '__FORM_TOKEN': 'wrong'})
        code, data = _call(self.ui._handle_link, req)
        self.assertEqual(400, code)
        self.assertIn('form token', data['error'].lower())

    def test_non_integer_ids_rejected(self):
        self._grant('bob', 'TICKET_MODIFY')
        req = self._req(action='add', epic_id='abc', ticket_id='x')
        code, data = _call(self.ui._handle_link, req)
        self.assertEqual(400, code)
        self.assertIn('integer', data['error'].lower())

    # -- authorization (security review 2.1) ---------------------------
    def test_global_modify_allows_link(self):
        self._grant('bob', 'TICKET_MODIFY', 'TICKET_VIEW')
        req = self._req(action='add', epic_id=str(self.epic),
                        ticket_id=str(self.task))
        code, data = _call(self.ui._handle_link, req)
        self.assertEqual(200, code)
        self.assertTrue(data['ok'])
        self.assertTrue(data['changed'])
        self.assertEqual(
            [self.task],
            EpicLinkSystem(self.env).get_tickets_for_epic(self.env,
                                                          self.epic))

    def test_per_ticket_denied_is_rejected(self):
        # bob holds TICKET_MODIFY globally, but the policy denies it on the
        # task ticket specifically.  The link must NOT be created -- this is
        # the exact gap flagged as review item 2.1.
        self.env.config.set('trac', 'permission_policies',
                            'DenyTicketModifyPolicy,DefaultPermissionPolicy')
        self.env.config.set('epic-test', 'denied_ticket', str(self.task))
        self._grant('bob', 'TICKET_MODIFY', 'TICKET_VIEW')
        req = self._req(action='add', epic_id=str(self.epic),
                        ticket_id=str(self.task))
        code, data = _call(self.ui._handle_link, req)
        self.assertEqual(403, code)
        self.assertIn('error', data)
        # And no link leaked into the database.
        self.assertEqual(
            [],
            EpicLinkSystem(self.env).get_tickets_for_epic(self.env,
                                                          self.epic))

    def test_unknown_action_rejected(self):
        self._grant('bob', 'TICKET_MODIFY', 'TICKET_VIEW')
        req = self._req(action='frobnicate', epic_id=str(self.epic),
                        ticket_id=str(self.task))
        code, data = _call(self.ui._handle_link, req)
        self.assertEqual(400, code)
        self.assertIn('action', data['error'].lower())


class SearchEndpointTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(
            enable=['trac.*', 'tracepic.*',
                    'tests.test_handlers.DenyTicketViewPolicy'],
            default_data=True)
        EpicLinkSystem(self.env).upgrade_environment()
        self.ui = EpicWebUI(self.env)
        self.epic = _make_ticket(self.env, 'Alpha epic', ttype='epic')
        self.task = _make_ticket(self.env, 'Beta task')

    def tearDown(self):
        self.env.reset_db()

    def test_per_ticket_view_denied_is_filtered(self):
        # A ticket the user cannot view (per-resource TICKET_VIEW denied)
        # must not appear in the search results.
        self.env.config.set('trac', 'permission_policies',
                            'DenyTicketViewPolicy,DefaultPermissionPolicy')
        self.env.config.set('epic-test', 'hidden_ticket', str(self.task))
        PermissionSystem(self.env).grant_permission('bob', 'TICKET_VIEW')
        req = MockRequest(self.env, authname='bob',
                          args={'q': 'beta', 'only': 'ticket'})
        code, data = _call(self.ui._handle_search, req)
        self.assertEqual(200, code)
        ids = [r['id'] for r in data['results']]
        self.assertNotIn(self.task, ids)

    def test_search_by_summary(self):
        PermissionSystem(self.env).grant_permission('bob', 'TICKET_VIEW')
        req = MockRequest(self.env, authname='bob',
                          args={'q': 'beta', 'only': 'ticket'})
        code, data = _call(self.ui._handle_search, req)
        self.assertEqual(200, code)
        ids = [r['id'] for r in data['results']]
        self.assertIn(self.task, ids)
        self.assertNotIn(self.epic, ids)  # filtered out by only=ticket

    def test_search_by_numeric_id_is_db_neutral(self):
        # Numeric terms must match the ticket id without CAST(... AS text)
        # (security review 4.3 portability fix).
        PermissionSystem(self.env).grant_permission('bob', 'TICKET_VIEW')
        req = MockRequest(self.env, authname='bob',
                          args={'q': str(self.task)})
        code, data = _call(self.ui._handle_search, req)
        self.assertEqual(200, code)
        ids = [r['id'] for r in data['results']]
        self.assertIn(self.task, ids)

    def test_search_only_epic_filter(self):
        PermissionSystem(self.env).grant_permission('bob', 'TICKET_VIEW')
        req = MockRequest(self.env, authname='bob',
                          args={'q': 'alpha', 'only': 'epic'})
        code, data = _call(self.ui._handle_search, req)
        ids = [r['id'] for r in data['results']]
        self.assertIn(self.epic, ids)
        self.assertNotIn(self.task, ids)


if __name__ == '__main__':
    unittest.main()
