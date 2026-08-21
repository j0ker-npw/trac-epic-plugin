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
from trac.ticket.api import ITicketChangeListener, TicketSystem
from trac.ticket.model import Ticket

from tracepic import _, add_domain

# Name of the plugin schema entry stored in the ``system`` table.
PLUGIN_NAME = 'tracepic'
# Current schema version owned by this plugin.
PLUGIN_SCHEMA_VERSION = 1

# ``field`` value used for the changelog entries written by this plugin.
CHANGELOG_FIELD = 'epic_link'

# Legacy custom field names that older setups may have used to store a
# textual epic reference.  These are migrated into ``epic_links`` on upgrade.
LEGACY_CUSTOM_FIELDS = ('epic', 'parent_epic')


class _LinkAlreadyExists(Exception):
    """Internal sentinel: a concurrent INSERT already created the link.

    Raised inside the :meth:`EpicLinkSystem.add_link` transaction so the
    transaction rolls back, then caught by the method to return ``False``
    (idempotent "already linked").  Never propagates to callers.
    """


def _now_us():
    """Return the current time as microseconds since the epoch.

    Trac stores ticket/change timestamps as 64-bit microsecond integers.
    """
    return int(time.time() * 1000000)


class EpicLinkSystem(Component):
    """Central component managing epic <-> ticket links."""

    implements(IEnvironmentSetupParticipant, ITicketChangeListener)

    def __init__(self):
        from pkg_resources import resource_filename
        add_domain(self.env.path, resource_filename('tracepic', 'locale'))

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
    # ITicketChangeListener
    # ------------------------------------------------------------------
    # The plugin only cares about ticket deletion (to clean up orphaned
    # links); the create/change hooks are required by the interface but are
    # intentional no-ops.
    def ticket_created(self, ticket):
        pass

    def ticket_changed(self, ticket, comment, author, old_values):
        pass

    def ticket_deleted(self, ticket):
        """Remove any ``epic_links`` rows referencing the deleted ticket.

        Without this, deleting a ticket would leave dangling link rows whose
        ``epic_id`` or ``ticket_id`` no longer resolves to a real ticket.
        They accumulate over time (the UI tolerates them because
        :meth:`get_ticket_summary` returns ``None``), so we delete them
        eagerly when Trac fires the deletion event.
        """
        try:
            tid = int(ticket.id)
        except (TypeError, ValueError, AttributeError):
            return
        with self.env.db_transaction as db:
            db("""
                DELETE FROM epic_links
                WHERE epic_id=%s OR ticket_id=%s
                """, (tid, tid))
        self.log.debug("TracEpicPlugin removed epic links for deleted "
                       "ticket #%d", tid)

    def ticket_comment_modified(self, ticket, cdate, author, comment,
                                old_comment):
        pass

    def ticket_change_deleted(self, ticket, cdate, changes):
        pass

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

    # Tables this plugin is ever allowed to probe.  Restricting the fallback
    # path to a fixed whitelist means the table name can never originate from
    # untrusted input, so no identifier is interpolated into SQL from an
    # external source (see security review 2.3).
    _KNOWN_TABLES = ('epic_links',)

    def _table_exists(self, db, table_name):
        """Return ``True`` if *table_name* exists in the connected database.

        The backend-neutral ``DatabaseManager.get_table_names`` path is the
        primary (and normally the only) mechanism used.  A direct probe is
        kept purely as a defensive fallback and is guarded by a hardcoded
        whitelist (:data:`_KNOWN_TABLES`): a table name that is not a known
        plugin table is reported as missing rather than interpolated into a
        query, eliminating the identifier-injection sink flagged in the code
        review.
        """
        # ``DatabaseManager.get_table_names`` gives a backend neutral answer.
        try:
            from trac.db.api import DatabaseManager
            tables = DatabaseManager(self.env).get_table_names()
            return table_name in tables
        except Exception:
            # Fallback: probe the table directly, but only for known plugin
            # tables so the identifier is never attacker controlled.
            if table_name not in self._KNOWN_TABLES:
                return False
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
        """Return a dict describing *ticket_id*, or ``None`` if it is gone.

        The returned mapping contains the columns needed to render the
        epic/linked-tickets table: ``id``, ``summary``, ``component``,
        ``type``, ``status``, ``owner`` and the raw ``changetime`` (64-bit
        microsecond integer, may be ``None``).  The web UI formats
        ``changetime`` into a human readable ``modified`` string using the
        viewer's timezone.

        It also returns ``priority`` (the priority name) and
        ``priority_value`` (the priority's position in the ``enum`` table as
        a string, e.g. ``'1'`` for the highest priority) so the web UI can
        colour table rows exactly like Trac's default report/query views
        (``prio1`` .. ``prioN`` CSS classes).  ``priority_value`` is ``None``
        when the ticket has no priority or the value is not defined.
        """
        for (summary, component, ttype, status, owner, changetime,
             priority, priority_value) in env.db_query("""
                SELECT t.summary, t.component, t.type, t.status, t.owner,
                       t.changetime, t.priority, e.value
                FROM ticket t
                LEFT JOIN enum e ON e.type=%s AND e.name=t.priority
                WHERE t.id=%s
                """, ('priority', int(ticket_id))):
            return {'id': int(ticket_id),
                    'summary': summary,
                    'component': component,
                    'type': ttype,
                    'status': status,
                    'owner': owner,
                    'changetime': changetime,
                    'priority': priority,
                    'priority_value': priority_value}
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
            raise TracError(_("A ticket cannot be linked to itself."))

        try:
            with env.db_transaction as db:
                self._assert_ticket_exists(db, epic_id, "epic")
                self._assert_ticket_exists(db, ticket_id, "ticket")

                already = list(db("""
                    SELECT 1 FROM epic_links
                    WHERE epic_id=%s AND ticket_id=%s
                    """, (epic_id, ticket_id)))
                if already:
                    return False

                when = _now_us()
                try:
                    db("""
                        INSERT INTO epic_links
                            (epic_id, ticket_id, author, created)
                        VALUES (%s, %s, %s, %s)
                        """, (epic_id, ticket_id, author, when))
                except env.db_exc.IntegrityError:
                    # The check-then-insert above can still lose a race with
                    # a concurrent identical add_link: the unique index on
                    # (epic_id, ticket_id) then rejects the duplicate INSERT.
                    # Re-raise as a sentinel so the enclosing transaction is
                    # rolled back cleanly (the link the winning transaction
                    # created stays), and report "already linked" to the
                    # caller for an idempotent result.
                    raise _LinkAlreadyExists()

                # Changelog for the epic ticket: gained a linked ticket.
                self._write_change(db, epic_id, author, when,
                                   oldvalue='', newvalue='#%d' % ticket_id)
                # Changelog for the regular ticket: gained an epic.
                self._write_change(db, ticket_id, author, when,
                                   oldvalue='', newvalue='#%d' % epic_id)
        except _LinkAlreadyExists:
            return False
        self.log.debug("TracEpicPlugin linked epic #%d <-> ticket #%d by %s",
                       epic_id, ticket_id, author)
        # The transaction has committed successfully at this point.  Fire the
        # ITicketChangeListener notifications that ``_write_change`` cannot
        # produce (see its docstring).  Both tickets went from "no link" to
        # "linked", so their previous ``epic_link`` value was empty.
        self._notify_listeners(env, epic_id, ticket_id, author, comment,
                               old_epic={CHANGELOG_FIELD: ''},
                               old_ticket={CHANGELOG_FIELD: ''})
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
        # The transaction has committed successfully at this point.  Fire the
        # ITicketChangeListener notifications for both tickets.  The previous
        # ``epic_link`` value reflected the link that was just removed: the
        # epic used to reference the ticket, and the ticket used to reference
        # the epic.
        self._notify_listeners(env, epic_id, ticket_id, author, comment,
                               old_epic={CHANGELOG_FIELD: '#%d' % ticket_id},
                               old_ticket={CHANGELOG_FIELD: '#%d' % epic_id})
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _notify_listeners(self, env, epic_id, ticket_id, author, comment,
                          old_epic, old_ticket):
        """Fire ``ITicketChangeListener.ticket_changed`` for both tickets.

        This is called *after* the ``epic_links`` transaction has committed,
        so listeners see the up-to-date database state (R-1, R-4).  It works
        around the limitation documented on :meth:`_write_change`: because the
        changelog is written with raw SQL rather than through the ``Ticket``
        model, Trac never fires the standard change notifications for the two
        affected tickets.  Re-emitting them here restores e-mail
        notifications and third-party ``ITicketChangeListener`` side effects.

        :param old_epic: ``old_values`` mapping for the epic ticket, i.e. the
            ``epic_link`` value *before* the change.
        :param old_ticket: ``old_values`` mapping for the linked ticket.

        Robustness guarantees:

        * The ``Ticket`` object is loaded *after* the commit; if it cannot be
          loaded (e.g. deleted concurrently) the ticket is skipped with a
          warning rather than aborting the notification of the other one
          (R-4).
        * An exception raised by any individual listener is caught and logged
          so it neither interrupts the remaining listeners nor propagates back
          to the caller (the data transaction is already committed) (R-3).
        """
        listeners = TicketSystem(env).change_listeners
        for tid, old_values in ((epic_id, old_epic), (ticket_id, old_ticket)):
            try:
                ticket_obj = Ticket(env, tid)
            except Exception:
                self.log.warning(
                    "TracEpicPlugin: could not load ticket #%s for "
                    "ITicketChangeListener notification", tid)
                continue
            for listener in listeners:
                try:
                    listener.ticket_changed(ticket_obj, comment, author,
                                            old_values)
                except Exception:
                    self.log.exception(
                        "TracEpicPlugin: error in listener "
                        "%s.ticket_changed", type(listener).__name__)

    def _assert_ticket_exists(self, db, ticket_id, role):
        """Raise :class:`TracError` if *ticket_id* does not exist."""
        for _row in db("SELECT 1 FROM ticket WHERE id=%s", (int(ticket_id),)):
            return
        raise TracError(_("The %(role)s ticket #%(id)d does not exist.")
                        % {'role': role, 'id': int(ticket_id)})

    def _write_change(self, db, ticket_id, author, when, oldvalue, newvalue):
        """Insert changelog rows for one epic-link change.

        Writes both the ``epic_link`` field row and a sequential ``comment``
        row (matching what ``Ticket.save_changes`` always does) so that
        deep-links like ``#comment:N`` work correctly and
        ``ITicketChangeListener`` consumers can locate the change by its
        comment number.

        Also bumps the ticket's ``changetime`` so the change is reflected in
        the ticket listing / timeline.

        .. note::
           This deliberately writes straight to ``ticket_change`` and
           ``ticket.changetime`` instead of going through Trac's ``Ticket``
           model.  The trade-off is intentional (documented in the security
           review, item 2.2):

           * **Pro** — the link row and both changelog rows are written in a
             single ``epic_links`` transaction, so the link and its audit
             trail are always consistent and cheap to write.
           * **Con** — The manual ``changetime`` bump could in principle
             race with a concurrent legitimate ticket edit.

           ``ITicketChangeListener`` notifications are fired by ``add_link``
           and ``remove_link`` after the transaction commits.

           All values here are parameterized, so this is not an injection
           vector.
        """
        # Compute the next sequential comment number for this ticket.
        # Algorithm matches Ticket.save_changes() exactly.
        num = 0
        for ts, old in db("""
                SELECT DISTINCT tc1.time, COALESCE(tc2.oldvalue, '')
                FROM ticket_change AS tc1
                LEFT OUTER JOIN ticket_change AS tc2
                  ON tc2.ticket=%s AND tc2.time=tc1.time
                     AND tc2.field='comment'
                WHERE tc1.ticket=%s ORDER BY tc1.time DESC
                """, (int(ticket_id), int(ticket_id))):
            try:
                num += int(old.rsplit('.', 1)[-1])
                break
            except ValueError:
                num += 1
        cnum = str(num + 1)

        # Comment row — same timestamp as the epic_link row.
        db("""
            INSERT INTO ticket_change
                (ticket, time, author, field, oldvalue, newvalue)
            VALUES (%s, %s, %s, 'comment', %s, %s)
            """, (int(ticket_id), when, author, cnum, ''))

        # Epic-link row — unchanged.
        db("""
            INSERT INTO ticket_change
                (ticket, time, author, field, oldvalue, newvalue)
            VALUES (%s, %s, %s, %s, %s, %s)
            """, (int(ticket_id), when, author, CHANGELOG_FIELD,
                  oldvalue, newvalue))

        db("UPDATE ticket SET changetime=%s WHERE id=%s",
           (when, int(ticket_id)))
