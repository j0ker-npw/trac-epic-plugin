# -*- coding: utf-8 -*-
"""Run the JavaScript sorting/pagination logic tests via Node.

``epic.js`` exposes its pure helpers (comparator, sort, pagination state)
through ``module.exports`` when loaded under Node.  ``tests/test_epic_js.js``
exercises the sort semantics (including the priority ordering and id
tiebreak), the natural default direction, config validation and the
pagination slicing.  This wrapper simply shells out to ``node`` so the JS
logic is covered by the normal ``pytest`` run; it is skipped automatically
when Node is not installed.
"""

import os
import shutil
import subprocess
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_JS_TEST = os.path.join(_HERE, 'test_epic_js.js')


class EpicJsLogicTestCase(unittest.TestCase):

    @unittest.skipUnless(shutil.which('node'), "node executable not available")
    def test_epic_js_logic(self):
        result = subprocess.run(
            ['node', _JS_TEST],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True)
        self.assertEqual(
            0, result.returncode,
            "epic.js logic tests failed:\n%s" % result.stdout)


if __name__ == '__main__':
    unittest.main()
