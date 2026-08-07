# -*- coding: utf-8 -*-
"""Data model and database operations for TracEpicPlugin.

The :class:`EpicLinkSystem` component owns the ``epic_links`` table and
provides all the high level operations used by the web UI and the XML-RPC
handler:

* schema creation / upgrade (``IEnvironmentSetupParticipant``)
* one-time migration of legacy ``epic`` / ``parent_epic`` custom fields
* query helpers (:meth:`get_epics_for_ticket`,
  :meth:`get_tickets_for_epic`)
* mutating helpers (:meth:`add_link`, :meth:`remove_link`) that also write
  ticket changelog entries.

All database access uses ``env.db_transaction`` / ``env.db_query`` so the
code works unchanged on PostgreSQL, MySQL and SQLite.  Placeholders use the
Trac neutral ``%s`` style.
"""

import time

from trac.core import Component, implements, TracError
from trac.env import IEnvironmentSetupParticipant

# Name of the plugin schema entry stored in the ``system`` table.
PLUGIN_NAME = 'tracepic'
# Current schema version owned by this plugin.
PLUGIN_SCHEMA_VERSION = 1

# ``field`` value used for the changelog entries written by this plugin.
CHANGELOG_FIELD = 'epic_link'

# Legacy custom field names that older setups may have used to store a
# textual epic reference.  These are migrated into ``epic_links`` on upgrade.
LEGACY_CUSTOM_FIELDS = ('epic', 'parent_epic')


def _now_us():
    """Return the current time as microseconds since the epoch.

    Trac stores ticket/change timestamps as 64-bit microsecond integers.
    """
    return int(time.time() * 1000000)


class EpicLinkSystem(Component):
    """Central component managing epic <-> ticket links."""

    implements(IEnvironmentSetupParticipant)

    # ------------------------------------------------------------------
    # IEnvironmentSetupParticipant
    # ------------------------------------------------------------------
    def environment_created(self):
        """Create the plugin schema in a freshly created environment."""
        self.upgrade_environment()

    def environment_needs_upgrade(self, db=None):
        """Return ``True`` when the plugin schema must be (re)created.

        The ``db`` argument is accepted for compatibility with older Trac
        releases but is not used; modern Trac (1.3.2+/1.6) calls this method
        without arguments.
        """
        return self._get_installed_version() < PLUGIN_SCHEMA_VERSION

    def upgrade_environment(self, db=None):
        """Create the ``epic_links`` table and run data migration."""
        installed = self._get_installed_version()
        if installed >= PLUGIN_SCHEMA_VERSION:
            return

        if installed < 1:
            self._create_schema()
            self._migrate_legacy_custom_fields()

        self._set_installed_version(PLUGIN_SCHEMA_VERSION)
        self.log.info("TracEpicPlugin schema upgraded to version %d",
                      PLUGIN_SCHEMA_VERSION)

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------
    def _get_installed_version(self):
        """Return the installed plugin schema version (0 if not installed)."""
        for value, in self.env.db_query("""
                SELECT value FROM system WHERE name=%s
                """, (PLUGIN_NAME + '_version',)):
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
        return 0

    def _set_installed_version(self, version):
        """Persist the plugin schema version in the ``system`` table."""
        with self.env.db_transaction as db:
            key = PLUGIN_NAME + '_version'
            existing = list(db("SELECT value FROM system WHERE name=%s",
                               (key,)))
            if existing:
                db("UPDATE system SET value=%s WHERE name=%s",
                   (str(version), key))
            else:
                db("INSERT INTO system (name, value) VALUES (%s, %s)",
                   (key, str(version)))

    def _table_exists(self, db, table_name):
        """Return ``True`` if *table_name* exists in the connected database."""
        # ``DatabaseManager.get_table_names`` gives a backend neutral answer.
        try:
            from trac.db.api import DatabaseManager
            tables = DatabaseManager(self.env).get_table_names()
            return table_name in tables
        except Exception:
            # Fallback: probe the table directly.
            try:
                db("SELECT 1 FROM %s WHERE 1=0" % table_name)
                return True
            except Exception:
                return False

    def _create_schema(self):
        """Create the ``epic_links`` table using a portable schema object."""
        from trac.db import Table, Column, Index
        from trac.db.api import DatabaseManager

        table = Table('epic_links', key='id')[
            Column('id', auto_increment=True),
            Column('epic_id', type='int'),
            Column('ticket_id', type='int'),
            Column('author'),
            Column('created', type='int64'),
            Index(['epic_id', 'ticket_id'], unique=True),
            Index(['ticket_id']),
        ]

        with self.env.db_transaction as db:
            if self._table_exists(db, 'epic_links'):
                return
            db_connector, _ = DatabaseManager(self.env).get_connector()
            for stmt in db_connector.to_sql(table):
                db(stmt)
        self.log.info("TracEpicPlugin created table 'epic_links'")

    def _migrate_legacy_custom_fields(self):
        """Copy legacy ``epic`` / ``parent_epic`` custom fields into links.

        For every value found in ``ticket_custom`` whose ``name`` is one of
        :data:`LEGACY_CUSTOM_FIELDS`, the value is interpreted as an epic
        ticket id.  A link ``(epic_id, ticket_id)`` is created only when both
        tickets actually exist and the link is not already present.
        """
        migrated = 0
        with self.env.db_transaction as db:
            # Collect the set of existing ticket ids once.
            existing_ids = set(
                row[0] for row in db("SELECT id FROM ticket"))
            if not existing_ids:
                return

            placeholders = ','.join(['%s'] * len(LEGACY_CUSTOM_FIELDS))
            rows = list(db("""
                SELECT ticket, value FROM ticket_custom
                WHERE name IN (%s)
                """ % placeholders, LEGACY_CUSTOM_FIELDS))

            for ticket_id, value in rows:
                if not value:
                    continue
                # A legacy field may contain one or more comma/space
                # separated epic references.
                for token in str(value).replace(',', ' ').split():
                    token = token.strip().lstrip('#')
                    if not token.isdigit():
                        continue
                    epic_id = int(token)
                    if epic_id not in existing_ids:
                        continue
                    if int(ticket_id) not in existing_ids:
                        continue
                    if epic_id == int(ticket_id):
                        continue
                    already = list(db("""
                        SELECT 1 FROM epic_links
                        WHERE epic_id=%s AND ticket_id=%s
                        """, (epic_id, int(ticket_id))))
                    if already:
                        continue
                    db("""
                        INSERT INTO epic_links
                            (epic_id, ticket_id, author, created)
                        VALUES (%s, %s, %s, %s)
                        """, (epic_id, int(ticket_id), 'migration',
                              _now_us()))
                    migrated += 1
        if migrated:
            self.log.info("TracEpicPlugin migrated %d legacy epic link(s)",
                          migrated)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def get_epics_for_ticket(self, env, ticket_id):
        """Return the list of epic ids linked to *ticket_id* (sorted)."""
        ticket_id = int(ticket_id)
        return [row[0] for row in env.db_query("""
            SELECT epic_id FROM epic_links WHERE ticket_id=%s
            ORDER BY epic_id
            """, (ticket_id,))]

    def get_tickets_for_epic(self, env, epic_id):
        """Return the list of ticket ids linked to *epic_id* (sorted)."""
        epic_id = int(epic_id)
        return [row[0] for row in env.db_query("""
            SELECT ticket_id FROM epic_links WHERE epic_id=%s
            ORDER BY ticket_id
            """, (epic_id,))]

    def link_exists(self, env, epic_id, ticket_id):
        """Return ``True`` if a link between *epic_id* and *ticket_id* exists."""
        for _ in env.db_query("""
                SELECT 1 FROM epic_links WHERE epic_id=%s AND ticket_id=%s
                """, (int(epic_id), int(ticket_id))):
            return True
        return False

    def get_ticket_summary(self, env, ticket_id):
        """Return ``(summary, status, type)`` for *ticket_id* or ``None``."""
        for summary, status, ttype in env.db_query("""
                SELECT summary, status, type FROM ticket WHERE id=%s
                """, (int(ticket_id),)):
            return {'id': int(ticket_id), 'summary': summary,
                    'status': status, 'type': ttype}
        return None

    # ------------------------------------------------------------------
    # Mutating helpers
    # ------------------------------------------------------------------
    def add_link(self, env, epic_id, ticket_id, author, comment=''):
        """Create a link between *epic_id* and *ticket_id*.

        Both tickets must exist and must be different.  A changelog entry is
        written for both tickets.  Returns ``True`` if a new link was
        created, ``False`` if the link already existed.

        :raises TracError: if the tickets are invalid.
        """
        epic_id = int(epic_id)
        ticket_id = int(ticket_id)

        if epic_id == ticket_id:
            raise TracError("A ticket cannot be linked to itself.")

        with env.db_transaction as db:
            self._assert_ticket_exists(db, epic_id, "epic")
            self._assert_ticket_exists(db, ticket_id, "ticket")

            already = list(db("""
                SELECT 1 FROM epic_links WHERE epic_id=%s AND ticket_id=%s
                """, (epic_id, ticket_id)))
            if already:
                return False

            when = _now_us()
            db("""
                INSERT INTO epic_links (epic_id, ticket_id, author, created)
                VALUES (%s, %s, %s, %s)
                """, (epic_id, ticket_id, author, when))

            # Changelog for the epic ticket: gained a linked ticket.
            self._write_change(db, epic_id, author, when,
                               oldvalue='', newvalue='#%d' % ticket_id)
            # Changelog for the regular ticket: gained an epic.
            self._write_change(db, ticket_id, author, when,
                               oldvalue='', newvalue='#%d' % epic_id)
        self.log.debug("TracEpicPlugin linked epic #%d <-> ticket #%d by %s",
                       epic_id, ticket_id, author)
        return True

    def remove_link(self, env, epic_id, ticket_id, author, comment=''):
        """Remove the link between *epic_id* and *ticket_id*.

        Returns ``True`` if a link was removed, ``False`` if none existed.
        A changelog entry is written for both tickets when a link is removed.
        """
        epic_id = int(epic_id)
        ticket_id = int(ticket_id)

        with env.db_transaction as db:
            already = list(db("""
                SELECT 1 FROM epic_links WHERE epic_id=%s AND ticket_id=%s
                """, (epic_id, ticket_id)))
            if not already:
                return False

            db("""
                DELETE FROM epic_links WHERE epic_id=%s AND ticket_id=%s
                """, (epic_id, ticket_id))

            when = _now_us()
            self._write_change(db, epic_id, author, when,
                               oldvalue='#%d' % ticket_id, newvalue='')
            self._write_change(db, ticket_id, author, when,
                               oldvalue='#%d' % epic_id, newvalue='')
        self.log.debug("TracEpicPlugin unlinked epic #%d <-> ticket #%d by %s",
                       epic_id, ticket_id, author)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _assert_ticket_exists(self, db, ticket_id, role):
        """Raise :class:`TracError` if *ticket_id* does not exist."""
        for _ in db("SELECT 1 FROM ticket WHERE id=%s", (int(ticket_id),)):
            return
        raise TracError("The %s ticket #%d does not exist."
                        % (role, int(ticket_id)))

    def _write_change(self, db, ticket_id, author, when, oldvalue, newvalue):
        """Insert a changelog row into ``ticket_change``.

        Also bumps the ticket's ``changetime`` so the change is reflected in
        the ticket listing / timeline.
        """
        db("""
            INSERT INTO ticket_change
                (ticket, time, author, field, oldvalue, newvalue)
            VALUES (%s, %s, %s, %s, %s, %s)
            """, (int(ticket_id), when, author, CHANGELOG_FIELD,
                  oldvalue, newvalue))
        db("UPDATE ticket SET changetime=%s WHERE id=%s",
           (when, int(ticket_id)))
