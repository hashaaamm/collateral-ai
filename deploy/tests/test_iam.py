from unittest import mock

import pulumi
from _iam import child_opts


def test_child_opts_sets_parent():
    sentinel = object()
    opts = child_opts(sentinel)
    assert opts.parent is sentinel


def test_child_opts_threads_depends_on():
    # ResourceOptions validates depends_on entries must be Resources; at runtime child_opts
    # receives real Resources (e.g. an enabled API service), so stand in with a Resource mock.
    dep = mock.MagicMock(spec=pulumi.Resource)
    opts = child_opts(object(), depends_on=[dep])
    assert opts.depends_on == [dep]


def test_child_opts_defaults_depends_on_to_none():
    opts = child_opts(object())
    assert opts.depends_on is None
