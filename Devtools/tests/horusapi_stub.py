"""
A stand-in for ``HorusAPI``, so the shared helpers can be imported in a test.

HorusAPI ships with the Horus application rather than PyPI, which is why CI
cannot import the plugin either (see ``.pylintrc``). ``utils.py`` needs it at
import time, but only to declare the blocks' variables: ``PluginVariable`` is
called with keyword arguments and ``SlurmBlock`` appears only in type hints.
Standing those in lets the real ``cluster_setting`` be tested; the logic under
test is the module's own, not this stub's.

Import this module before importing ``utils``.
"""

import sys
import types


class _Declared:
    """Stands in for a HorusAPI declaration object, keeping its keywords."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.__dict__.update(kwargs)


class VariableTypes:
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    NUMBER = "number"
    BOOLEAN = "boolean"
    CHECKBOX = "checkbox"
    FILE = "file"
    FOLDER = "folder"
    LIST = "list"
    STRING_LIST = "string_list"
    CUSTOM = "custom"


def install():
    """Put the stub on ``sys.modules`` unless the real HorusAPI is importable."""
    try:  # pragma: no cover - only true inside a Horus installation
        import HorusAPI  # noqa: F401  pylint: disable=unused-import

        return
    except ImportError:
        pass

    module = types.ModuleType("HorusAPI")
    for name in (
        "PluginVariable", "SlurmBlock", "VariableList", "PluginBlock",
        "PluginConfig", "PluginPage", "Extensions", "VariableGroup",
    ):
        setattr(module, name, _Declared)
    module.VariableTypes = VariableTypes
    sys.modules["HorusAPI"] = module


class FakeRemote:
    """The parts of a Horus remote that the site checks look at."""

    def __init__(self, name="cluster", host="", is_local=False):
        self.name = name
        self.host = host
        self.isLocal = is_local


class FakeBlock:
    """A block carrying settings and a remote, which is all these helpers read."""

    def __init__(self, variables=None, remote=None):
        self.variables = dict(variables or {})
        self.remote = remote or FakeRemote()


class FakeActionBlock(FakeBlock):
    """
    A block an analysis action can actually run against.

    A block action reads ``inputs`` and ``variables`` and reports results
    through ``setOutput``; the ones tested here need nothing else. Driving the
    real action this way tests the production code rather than a restatement of
    it.
    """

    def __init__(self, inputs=None, variables=None, remote=None):
        super().__init__(variables, remote or FakeRemote(name="Local", is_local=True))
        self.inputs = dict(inputs or {})
        self.outputs = {}

    def setOutput(self, variable_id, value):  # noqa: N802 - HorusAPI spelling
        self.outputs[variable_id] = value
