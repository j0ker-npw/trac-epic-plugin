# -*- coding: utf-8 -*-
"""TracEpicPlugin - Epic <-> ticket linking for Trac 1.6.

This package provides an M:N linking mechanism between "epic" tickets and
regular tickets, a web UI integrated into the ticket page, an XML-RPC API
(via the tracrpc / XmlRpcPlugin), and changelog integration.
"""

__version__ = '1.2.2'
__all__ = ['api', 'web_ui', 'xmlrpc']
