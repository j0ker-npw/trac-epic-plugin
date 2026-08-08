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


class SortAndPageConfigTestCase(unittest.TestCase):
    """``[epic] linked_default_sort`` and ``linked_page_size`` parsing."""

    def setUp(self):
        self.env = EnvironmentStub(
            enable=['trac.*', 'tracepic.*'], default_data=True)
        self.ui = EpicWebUI(self.env)

    def test_defaults_when_unset(self):
        self.assertEqual(('priority', 'desc'), self.ui._default_sort())
        self.assertEqual(10, self.ui._page_size())

    def test_valid_values_are_honoured(self):
        self.env.config.set('epic', 'linked_default_sort', 'summary/asc')
        self.env.config.set('epic', 'linked_page_size', '25')
        self.assertEqual(('summary', 'asc'), self.ui._default_sort())
        self.assertEqual(25, self.ui._page_size())

    def test_case_insensitive_and_whitespace(self):
        self.env.config.set('epic', 'linked_default_sort', '  Modified / DESC ')
        self.assertEqual(('modified', 'desc'), self.ui._default_sort())

    def test_invalid_field_falls_back(self):
        self.env.config.set('epic', 'linked_default_sort', 'bogus/asc')
        self.assertEqual(('priority', 'asc'), self.ui._default_sort())

    def test_invalid_order_falls_back(self):
        self.env.config.set('epic', 'linked_default_sort', 'owner/sideways')
        self.assertEqual(('owner', 'desc'), self.ui._default_sort())

    def test_non_positive_page_size_falls_back(self):
        self.env.config.set('epic', 'linked_page_size', '0')
        self.assertEqual(10, self.ui._page_size())
        self.env.config.set('epic', 'linked_page_size', '-5')
        self.assertEqual(10, self.ui._page_size())


class ColumnConfigTestCase(unittest.TestCase):
    """``[epic] linked_fields`` parsing into ordered ``(field, label)``."""

    def setUp(self):
        self.env = EnvironmentStub(
            enable=['trac.*', 'tracepic.*'], default_data=True)
        self.ui = EpicWebUI(self.env)

    def test_default_field_set(self):
        # Default is ticket,summary,type,status (ticket -> id internally).
        self.assertEqual(
            [('id', 'Ticket'), ('summary', 'Summary'),
             ('type', 'Type'), ('status', 'Status')],
            self.ui._columns())

    def test_custom_order_is_honoured(self):
        self.env.config.set('epic', 'linked_fields',
                            'priority,summary,ticket')
        self.assertEqual(
            [('priority', 'P'), ('summary', 'Summary'), ('id', 'Ticket')],
            self.ui._columns())

    def test_all_fields(self):
        self.env.config.set(
            'epic', 'linked_fields',
            'ticket,summary,component,type,status,owner,modified,priority')
        self.assertEqual(
            ['id', 'summary', 'component', 'type', 'status', 'owner',
             'modified', 'priority'],
            [f for f, _label in self.ui._columns()])

    def test_id_alias_accepted(self):
        self.env.config.set('epic', 'linked_fields', 'id,summary')
        self.assertEqual(
            [('id', 'Ticket'), ('summary', 'Summary')], self.ui._columns())

    def test_unknown_tokens_ignored(self):
        self.env.config.set('epic', 'linked_fields',
                            'ticket,bogus,summary,nope')
        self.assertEqual(
            [('id', 'Ticket'), ('summary', 'Summary')], self.ui._columns())

    def test_duplicates_collapsed_keeping_first(self):
        self.env.config.set('epic', 'linked_fields',
                            'summary,ticket,summary,id')
        self.assertEqual(
            [('summary', 'Summary'), ('id', 'Ticket')], self.ui._columns())

    def test_case_insensitive_and_whitespace(self):
        self.env.config.set('epic', 'linked_fields',
                            '  Ticket , SUMMARY ,  Type ')
        self.assertEqual(
            [('id', 'Ticket'), ('summary', 'Summary'), ('type', 'Type')],
            self.ui._columns())

    def test_empty_falls_back_to_default(self):
        self.env.config.set('epic', 'linked_fields', '')
        self.assertEqual(
            [('id', 'Ticket'), ('summary', 'Summary'),
             ('type', 'Type'), ('status', 'Status')],
            self.ui._columns())

    def test_only_invalid_falls_back_to_default(self):
        self.env.config.set('epic', 'linked_fields', 'bogus,nope, , ')
        self.assertEqual(
            ['id', 'summary', 'type', 'status'],
            [f for f, _label in self.ui._columns()])


if __name__ == '__main__':
    unittest.main()
