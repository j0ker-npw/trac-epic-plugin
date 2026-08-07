# -*- coding: utf-8 -*-
"""Unit tests for :mod:`tracepic.web_ui` display helpers.

Focuses on ``EpicWebUI._decorate``: the ``modified`` timestamp must be
rendered in Trac's relative "... ago" style, with the absolute date/time
carried separately in ``modified_title`` for the hover tooltip.
"""

import datetime
import unittest

from trac.test import EnvironmentStub, MockRequest
from trac.util.datefmt import to_utimestamp, datetime_now, utc

from tracepic.web_ui import EpicWebUI


class DecorateModifiedTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(
            enable=['trac.*', 'tracepic.*'], default_data=True)
        self.req = MockRequest(self.env)
        self.ui = EpicWebUI(self.env)

    def _decorate_at(self, dt):
        info = {'id': 1, 'summary': 's', 'component': 'c', 'type': 'task',
                'status': 'new', 'owner': 'a', 'priority': 'major',
                'priority_value': '3', 'changetime': to_utimestamp(dt)}
        return self.ui._decorate(self.req, info)

    def test_modified_is_relative_in_the_past(self):
        dt = datetime_now(utc) - datetime.timedelta(hours=3)
        out = self._decorate_at(dt)
        # Relative label ends with "ago" for past timestamps.
        self.assertTrue(out['modified'].endswith('ago'),
                        "expected a '... ago' label, got %r" % out['modified'])
        self.assertIn('hour', out['modified'])
        # The absolute date/time is available for the hover tooltip and is
        # different from the relative label.
        self.assertTrue(out['modified_title'])
        self.assertNotEqual(out['modified'], out['modified_title'])

    def test_modified_is_relative_in_the_future(self):
        dt = datetime_now(utc) + datetime.timedelta(days=2)
        out = self._decorate_at(dt)
        self.assertTrue(out['modified'].startswith('in '),
                        "expected an 'in ...' label, got %r" % out['modified'])
        self.assertTrue(out['modified_title'])

    def test_missing_changetime_yields_empty_strings(self):
        info = {'id': 1, 'summary': 's', 'component': 'c', 'type': 'task',
                'status': 'new', 'owner': 'a', 'priority': 'major',
                'priority_value': '3', 'changetime': None}
        out = self.ui._decorate(self.req, info)
        self.assertEqual('', out['modified'])
        self.assertEqual('', out['modified_title'])


if __name__ == '__main__':
    unittest.main()
