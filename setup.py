# -*- coding: utf-8 -*-
"""Setup shim for TracEpicPlugin.

All packaging metadata now lives in :file:`pyproject.toml` (PEP 621).
This thin ``setup.py`` is retained only so that the legacy ``bdist_egg``
command remains available::

    python3 -B setup.py bdist_egg

Trac loads plugins that are dropped into an environment's ``plugins/``
directory as ``*.egg`` archives, and ``bdist_egg`` is the only tool that
still produces that format.  For a virtual-environment install prefer the
standards-based build instead::

    python3 -m build      # produces a universal wheel + sdist
    pip install dist/TracEpicPlugin-*.whl
"""

from setuptools import setup

setup()
