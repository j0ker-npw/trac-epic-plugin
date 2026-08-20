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

from setuptools import setup, find_packages

# When bdist_egg is invoked, setuptools does not reliably read pyproject.toml
# in legacy mode.  We must explicitly declare packages and data files here.
setup(
    name='TracEpicPlugin',
    version='1.4.2',
    python_requires='>=3.9,<3.12',
    packages=find_packages(exclude=['tests', 'tests.*']),
    package_data={
        'tracepic': [
            'templates/*.html',
            'htdocs/*.css',
            'htdocs/*.js',
            'locale/*/LC_MESSAGES/*.mo',
            'locale/*/LC_MESSAGES/*.po',
            'locale/messages.pot',
        ],
    },
    entry_points={
        'trac.plugins': [
            'tracepic.api = tracepic.api',
            'tracepic.web_ui = tracepic.web_ui',
            'tracepic.xmlrpc = tracepic.xmlrpc',
        ],
    },
    message_extractors={
        'tracepic': [
            ('**.py', 'python', None),
            ('**/templates/**.html', 'jinja2', None),
        ],
    },
)
