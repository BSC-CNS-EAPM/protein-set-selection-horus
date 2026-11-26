"""
Make the plugin's ``Include`` folder importable, the way Horus does.

Horus puts ``<pluginRoot>/Include`` on ``sys.path`` before importing the plugin,
so the blocks reach the shared helpers as ``from sequence_io import ...``. The
tests import the same module by the same name, so what they exercise is exactly
what a block gets at run time.

``sequence_io`` is importable outside Horus because its only HorusAPI imports
are inside the functions that need them; the module level is stdlib only.
"""

import os
import sys

INCLUDE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "ProtSelect",
    "Include",
)

if INCLUDE not in sys.path:
    sys.path.insert(0, INCLUDE)
