# -*- coding: utf-8 -*-
"""XML-RPC API for TracEpicPlugin.

Exposes epic linking operations through the ``tracrpc`` (XmlRpcPlugin)
framework.  The methods are registered in the ``ticket`` namespace so they
are reachable as::

    ticket.getEpics(ticket_id)              -> list of epic ids
    ticket.getEpicLinkedTickets(epic_id)    -> list of ticket ids
    ticket.addEpicLink(ticket_id, epic_id)  -> bool
    ticket.removeEpicLink(ticket_id, epic_id) -> bool

This module degrades gracefully: if the ``tracrpc`` package is not
installed, the component is simply not defined and the rest of the plugin
keeps working.
"""

from trac.core import Component, implements, TracError
from trac.resource import Resource

from tracepic import _, add_domain
from tracepic.api import EpicLinkSystem

try:
    from tracrpc.api import IXMLRPCHandler
    HAS_TRACRPC = True
except ImportError:  # pragma: no cover - depends on optional XmlRpcPlugin
    IXMLRPCHandler = None
    HAS_TRACRPC = False


if HAS_TRACRPC:

    class EpicXmlRpc(Component):
        """XML-RPC handler exposing epic link operations."""

        implements(IXMLRPCHandler)

        def __init__(self):
            from pkg_resources import resource_filename
            add_domain(self.env.path, resource_filename('tracepic', 'locale'))
            self.epics = EpicLinkSystem(self.env)

        # -- IXMLRPCHandler --------------------------------------------
        def xmlrpc_namespace(self):
            return 'ticket'

        def xmlrpc_methods(self):
            """Yield ``(permission, signatures, method)`` tuples.

            Each method receives the Trac ``req`` object as its first
            argument (after ``self``), as required by tracrpc.
            """
            yield ('TICKET_VIEW',
                   ((list, int),),
                   self.getEpics)
            yield ('TICKET_VIEW',
                   ((list, int),),
                   self.getEpicLinkedTickets)
            yield ('TICKET_MODIFY',
                   ((bool, int, int),),
                   self.addEpicLink)
            yield ('TICKET_MODIFY',
                   ((bool, int, int),),
                   self.removeEpicLink)

        # -- RPC methods -----------------------------------------------
        def getEpics(self, req, ticket_id):
            """Return the list of epic ids the given ticket belongs to."""
            self._require_view(req, ticket_id)
            return self.epics.get_epics_for_ticket(self.env, int(ticket_id))

        def getEpicLinkedTickets(self, req, epic_id):
            """Return the list of ticket ids linked to the given epic."""
            self._require_view(req, epic_id)
            return self.epics.get_tickets_for_epic(self.env, int(epic_id))

        def addEpicLink(self, req, ticket_id, epic_id):
            """Link ``ticket_id`` to ``epic_id``.  Returns ``True`` if a new
            link was created, ``False`` if it already existed."""
            self._require_modify(req, ticket_id)
            self._require_modify(req, epic_id)
            author = req.authname or 'anonymous'
            return self.epics.add_link(
                self.env, int(epic_id), int(ticket_id), author)

        def removeEpicLink(self, req, ticket_id, epic_id):
            """Remove the link between ``ticket_id`` and ``epic_id``.
            Returns ``True`` if a link was removed.

            Consistent with :meth:`addEpicLink`, this requires
            ``TICKET_MODIFY`` on *both* tickets: mutating a link changes the
            changelog of each, so a caller denied on either ticket must not
            be able to remove the link."""
            self._require_modify(req, ticket_id)
            self._require_modify(req, epic_id)
            author = req.authname or 'anonymous'
            return self.epics.remove_link(
                self.env, int(epic_id), int(ticket_id), author)

        # -- permission helpers ----------------------------------------
        def _require_view(self, req, ticket_id):
            # A proper Resource (not the 'ticket:N' string) is required for
            # per-ticket permission policies to match correctly.
            resource = Resource('ticket', int(ticket_id))
            if 'TICKET_VIEW' not in req.perm(resource):
                raise TracError(_("TICKET_VIEW permission required for #%(id)s")
                                % {'id': ticket_id})

        def _require_modify(self, req, ticket_id):
            resource = Resource('ticket', int(ticket_id))
            if 'TICKET_MODIFY' not in req.perm(resource):
                raise TracError(_("TICKET_MODIFY permission required for #%(id)s")
                                % {'id': ticket_id})
