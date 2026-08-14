# -*- coding: utf-8 -*-
"""Unit tests for :mod:`tracepic.api`.

The tests use Trac's :class:`~trac.test.EnvironmentStub`, an in-memory
SQLite environment, so no external database is required.
"""

import unittest

from trac.test import EnvironmentStub
from trac.ticket.model import Ticket
from trac.core import TracError

from tracepic.api import (EpicLinkSystem, CHANGELOG_FIELD,
                          PLUGIN_SCHEMA_VERSION)


def _make_ticket(env, summary, ttype='task', status='new'):
    """Create and insert a ticket, returning its id."""
    ticket = Ticket(env)
    ticket['summary'] = summary
    ticket['type'] = ttype
    ticket['status'] = status
    return ticket.insert()


class EpicLinkSystemTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(
            enable=['trac.*', 'tracepic.*'], default_data=True)
        self.epics = EpicLinkSystem(self.env)
        # Create the plugin schema.
        self.epics.upgrade_environment()

    def tearDown(self):
        self.env.reset_db()

    # -- schema / setup participant ------------------------------------
    def test_schema_created(self):
        from trac.db.api import DatabaseManager
        tables = DatabaseManager(self.env).get_table_names()
        self.assertIn('epic_links', tables)
        self.assertFalse(self.epics.environment_needs_upgrade())
        self.assertEqual(PLUGIN_SCHEMA_VERSION,
                         self.epics._get_installed_version())

    def test_upgrade_is_idempotent(self):
        # Running upgrade again must not raise or duplicate anything.
        self.epics.upgrade_environment()
        self.assertFalse(self.epics.environment_needs_upgrade())

    # -- add_link ------------------------------------------------------
    def test_add_link_and_queries(self):
        epic = _make_ticket(self.env, 'Epic A', ttype='epic')
        t1 = _make_ticket(self.env, 'Task 1')
        t2 = _make_ticket(self.env, 'Task 2')

        self.assertTrue(self.epics.add_link(self.env, epic, t1, 'alice'))
        self.assertTrue(self.epics.add_link(self.env, epic, t2, 'alice'))

        self.assertEqual([t1, t2],
                         self.epics.get_tickets_for_epic(self.env, epic))
        self.assertEqual([epic],
                         self.epics.get_epics_for_ticket(self.env, t1))
        self.assertTrue(self.epics.link_exists(self.env, epic, t1))

    def test_add_link_duplicate_returns_false(self):
        epic = _make_ticket(self.env, 'Epic', ttype='epic')
        t1 = _make_ticket(self.env, 'Task')
        self.assertTrue(self.epics.add_link(self.env, epic, t1, 'bob'))
        self.assertFalse(self.epics.add_link(self.env, epic, t1, 'bob'))
        self.assertEqual([t1],
                         self.epics.get_tickets_for_epic(self.env, epic))

    def test_ticket_can_belong_to_multiple_epics(self):
        epic1 = _make_ticket(self.env, 'Epic 1', ttype='epic')
        epic2 = _make_ticket(self.env, 'Epic 2', ttype='epic')
        t1 = _make_ticket(self.env, 'Task')
        self.epics.add_link(self.env, epic1, t1, 'bob')
        self.epics.add_link(self.env, epic2, t1, 'bob')
        self.assertEqual([epic1, epic2],
                         self.epics.get_epics_for_ticket(self.env, t1))

    def test_add_link_self_reference_rejected(self):
        t1 = _make_ticket(self.env, 'Task')
        self.assertRaises(TracError,
                          self.epics.add_link, self.env, t1, t1, 'bob')

    def test_add_link_missing_ticket_rejected(self):
        epic = _make_ticket(self.env, 'Epic', ttype='epic')
        self.assertRaises(TracError,
                          self.epics.add_link, self.env, epic, 9999, 'bob')

    # -- remove_link ---------------------------------------------------
    def test_remove_link(self):
        epic = _make_ticket(self.env, 'Epic', ttype='epic')
        t1 = _make_ticket(self.env, 'Task')
        self.epics.add_link(self.env, epic, t1, 'bob')
        self.assertTrue(self.epics.remove_link(self.env, epic, t1, 'bob'))
        self.assertEqual([], self.epics.get_tickets_for_epic(self.env, epic))
        # Removing a non-existent link returns False.
        self.assertFalse(self.epics.remove_link(self.env, epic, t1, 'bob'))

    # -- changelog -----------------------------------------------------
    def test_changelog_written_for_both_tickets(self):
        epic = _make_ticket(self.env, 'Epic', ttype='epic')
        t1 = _make_ticket(self.env, 'Task')
        self.epics.add_link(self.env, epic, t1, 'carol')

        rows = list(self.env.db_query("""
            SELECT ticket, author, field, oldvalue, newvalue
            FROM ticket_change WHERE field=%s ORDER BY ticket
            """, (CHANGELOG_FIELD,)))
        # One row for the epic ticket, one for the regular ticket.
        tickets_changed = sorted(r[0] for r in rows)
        self.assertEqual(sorted([epic, t1]), tickets_changed)
        for _, author, field, oldv, newv in rows:
            self.assertEqual('carol', author)
            self.assertEqual(CHANGELOG_FIELD, field)
            self.assertEqual('', oldv)
            self.assertTrue(newv.startswith('#'))

    def test_changelog_written_on_remove(self):
        epic = _make_ticket(self.env, 'Epic', ttype='epic')
        t1 = _make_ticket(self.env, 'Task')
        self.epics.add_link(self.env, epic, t1, 'dave')
        self.epics.remove_link(self.env, epic, t1, 'dave')
        removals = list(self.env.db_query("""
            SELECT ticket FROM ticket_change
            WHERE field=%s AND newvalue=%s
            """, (CHANGELOG_FIELD, '')))
        self.assertEqual(2, len(removals))

    # -- summary helper ------------------------------------------------
    def test_get_ticket_summary(self):
        t1 = _make_ticket(self.env, 'A summary', ttype='epic', status='new')
        info = self.epics.get_ticket_summary(self.env, t1)
        self.assertEqual('A summary', info['summary'])
        self.assertEqual('epic', info['type'])
        self.assertEqual('new', info['status'])
        # The extended field set must be present so the web UI can render
        # the Component / Owner / Modified columns and colour rows by
        # priority (prioN classes).
        for key in ('id', 'summary', 'component', 'type', 'status',
                    'owner', 'changetime', 'priority', 'priority_value'):
            self.assertIn(key, info)
        self.assertIsNone(self.epics.get_ticket_summary(self.env, 8888))

    def test_get_ticket_summary_priority_value(self):
        # A ticket with an explicit priority must report the matching enum
        # value so the UI can apply the Trac prioN row-colour class.
        ticket = Ticket(self.env)
        ticket['summary'] = 'High prio'
        ticket['type'] = 'task'
        ticket['priority'] = 'blocker'  # highest priority -> enum value '1'
        tid = ticket.insert()
        info = self.epics.get_ticket_summary(self.env, tid)
        self.assertEqual('blocker', info['priority'])
        self.assertEqual('1', str(info['priority_value']))

    # -- migration -----------------------------------------------------
    def test_migration_from_legacy_custom_field(self):
        epic = _make_ticket(self.env, 'Legacy Epic', ttype='epic')
        t1 = _make_ticket(self.env, 'Legacy Task')
        # Simulate a legacy 'epic' custom field on t1 pointing to `epic`.
        with self.env.db_transaction as db:
            db("""INSERT INTO ticket_custom (ticket, name, value)
                  VALUES (%s, %s, %s)""", (t1, 'epic', '#%d' % epic))
        # Force a re-migration by resetting the stored version.
        self.epics._set_installed_version(0)
        self.epics.upgrade_environment()

        self.assertEqual([epic],
                         self.epics.get_epics_for_ticket(self.env, t1))

    def test_migration_ignores_invalid_references(self):
        t1 = _make_ticket(self.env, 'Task')
        with self.env.db_transaction as db:
            db("""INSERT INTO ticket_custom (ticket, name, value)
                  VALUES (%s, %s, %s)""", (t1, 'parent_epic', '9999'))
        self.epics._set_installed_version(0)
        self.epics.upgrade_environment()
        # Referenced epic 9999 does not exist -> no link created.
        self.assertEqual([], self.epics.get_epics_for_ticket(self.env, t1))

    def test_migration_multi_token_and_hash_prefix(self):
        # A single legacy field may carry several references separated by
        # commas/spaces, each optionally '#'-prefixed.  All valid ones must
        # become links.
        epic1 = _make_ticket(self.env, 'Epic 1', ttype='epic')
        epic2 = _make_ticket(self.env, 'Epic 2', ttype='epic')
        t1 = _make_ticket(self.env, 'Multi task')
        with self.env.db_transaction as db:
            db("""INSERT INTO ticket_custom (ticket, name, value)
                  VALUES (%s, %s, %s)""",
               (t1, 'epic', '#%d, %d' % (epic1, epic2)))
        self.epics._set_installed_version(0)
        self.epics.upgrade_environment()
        self.assertEqual([epic1, epic2],
                         self.epics.get_epics_for_ticket(self.env, t1))

    def test_second_upgrade_after_data_is_idempotent(self):
        # Once links exist, forcing a re-migration must neither raise nor
        # duplicate the existing links.
        epic = _make_ticket(self.env, 'Epic', ttype='epic')
        t1 = _make_ticket(self.env, 'Task')
        with self.env.db_transaction as db:
            db("""INSERT INTO ticket_custom (ticket, name, value)
                  VALUES (%s, %s, %s)""", (t1, 'epic', '#%d' % epic))
        self.epics._set_installed_version(0)
        self.epics.upgrade_environment()
        self.assertEqual([epic],
                         self.epics.get_epics_for_ticket(self.env, t1))
        # Re-run migration a second time.
        self.epics._set_installed_version(0)
        self.epics.upgrade_environment()
        self.assertEqual([epic],
                         self.epics.get_epics_for_ticket(self.env, t1))

    # -- orphan cleanup on ticket deletion -----------------------------
    def test_ticket_deleted_removes_links(self):
        epic = _make_ticket(self.env, 'Epic', ttype='epic')
        t1 = _make_ticket(self.env, 'Task 1')
        t2 = _make_ticket(self.env, 'Task 2')
        self.epics.add_link(self.env, epic, t1, 'alice')
        self.epics.add_link(self.env, epic, t2, 'alice')

        # Deleting t1 through Trac fires ITicketChangeListener.ticket_deleted,
        # which must remove the (epic, t1) link but leave (epic, t2) intact.
        Ticket(self.env, t1).delete()
        self.assertEqual([t2],
                         self.epics.get_tickets_for_epic(self.env, epic))

        # Deleting the epic itself removes its remaining links too.
        Ticket(self.env, epic).delete()
        self.assertEqual([],
                         self.epics.get_epics_for_ticket(self.env, t2))

    def test_ticket_deleted_listener_registered(self):
        # The component must advertise ITicketChangeListener so Trac invokes
        # the cleanup hook on ticket deletion.
        from trac.ticket.api import TicketSystem
        listeners = list(TicketSystem(self.env).change_listeners)
        self.assertTrue(
            any(isinstance(l, EpicLinkSystem) for l in listeners),
            "EpicLinkSystem must be registered as an ITicketChangeListener")


if __name__ == '__main__':
    unittest.main()
