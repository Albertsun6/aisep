"""Tests written before their implementation (docs/mcp-interface.md §11): while the module under test is missing, a call
returns a Pending placeholder instead of stopping the test, so every test still builds ALL its fixtures (positive twins
included); `xfail_if_pending` then ends the test as XFAIL with the reason. A fixture assertion that fails anywhere is a
real failure. Once the module exists the same tests run for real."""
import functools, importlib

import pytest

from aisep.errors import AisepError

_missing = []


class Pending:
    """Stands in for a result (or a raised AisepError) of a function that does not exist yet."""

    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    __hash__ = None

    def __getitem__(self, k):
        return self

    def __getattr__(self, k):
        return self

    def __contains__(self, k):
        return True

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return True


def pending(x):
    return isinstance(x, Pending)


def _module(name):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as e:
        if e.name == name:
            return None
        raise


def _fn(module, name):
    mod = _module(module)
    fn = getattr(mod, name, None) if mod else None
    if fn is None:
        _missing.append(f"实现未写：{module}{'' if mod is None else '.' + name} 不存在")
    return fn


def call(module, name, *a, **kw):
    """The function's result, or Pending while it does not exist (or raises NotImplementedError)."""
    fn = _fn(module, name)
    if fn is None:
        return Pending()
    try:
        return fn(*a, **kw)
    except NotImplementedError:
        _missing.append(f"实现未写：{module}.{name} 抛 NotImplementedError")
        return Pending()


def error(code, module, name, *a, **kw):
    """The AisepError the call must raise (asserted to carry `code`), or Pending while the function is missing."""
    fn = _fn(module, name)
    if fn is None:
        return Pending()
    try:
        fn(*a, **kw)
    except NotImplementedError:
        _missing.append(f"实现未写：{module}.{name} 抛 NotImplementedError")
        return Pending()
    except AisepError as e:
        assert e.code == code, (e.code, e.message, e.details)
        return e
    raise AssertionError(f"{module}.{name} 应报 {code}，实际成功")


def xfail_if_pending(fn):
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        _missing.clear()
        fn(*a, **kw)
        if _missing:
            pytest.xfail(f"{_missing[0]}（本例 {len(_missing)} 次调用待实现；夹具已全部建成）")
    return wrapper


def wrap_module(ns):
    """Apply xfail_if_pending to every test_* function of a test module (call at the end of the module)."""
    for name, f in list(ns.items()):
        if name.startswith("test_") and callable(f):
            ns[name] = xfail_if_pending(f)
