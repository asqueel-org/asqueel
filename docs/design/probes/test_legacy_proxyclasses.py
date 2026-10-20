"""Read-only behavioral probes against the frozen legacy implementation.

Run using the legacy interpreter and PYTHONPATH, never as Asqueel core tests.
The assertions describe observed behavior, including limitations; no fixes.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from gnr.core import gnrlang as gl
from gnr.sql.gnrsql import GnrSqlDb
from gnr.web.gnrwebpage_proxy.gnrbaseproxy import GnrBaseProxy


@pytest.fixture(autouse=True)
def no_io(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError('No database/network I/O in proxy probes')
    monkeypatch.setattr(GnrSqlDb, 'execute', forbidden)
    monkeypatch.setattr('socket.socket.connect', forbidden)
    monkeypatch.setattr('socket.socket.connect_ex', forbidden)


class Page:
    proxy_class = GnrBaseProxy

    def __init__(self):
        self.counter = 0
        self.shared = {}
        self.events = []

    def _subscribe_event(self, name, obj):
        self.events.append((name, obj))

    def owner_method(self):
        return self


class Logic:
    proxy = 'logic'

    def who(self):
        return self

    def read(self):
        return self.counter

    def increment(self):
        self.counter += 1

    def mutate(self):
        self.shared['changed'] = True

    def owner_call(self):
        return self.owner_method()

    def local_call(self):
        return self.who()

    def event_changed(self):
        pass


def web_object():
    class Composed(Page):
        pass
    gl.classMixin(Composed, Logic)
    page = Composed()
    gl.instanceMixin(page, Composed)
    return page


def test_plain_instance_mixin_binds_self_to_owner():
    target = SimpleNamespace()
    gl.instanceMixin(target, Logic)
    # proxy='logic' is interpreted by classMixin, not instanceMixin.
    assert target.who() is target
    assert not hasattr(target, 'logic')


def test_generic_proxy_requires_class_composition_then_instantiation():
    class Carrier:
        pass
    gl.classMixin(Carrier, Logic)
    assert not hasattr(Carrier, 'who')
    assert hasattr(Carrier, 'logic_proxyclass')
    target = Carrier()
    assert not hasattr(target, 'logic')
    gl.instanceMixin(target, Carrier)
    assert target.logic.who() is target.logic
    assert target.logic.main is target
    with pytest.raises(AttributeError):
        target.logic.read()  # Generic BaseProxy has no fallback.


def test_web_proxy_self_local_calls_owner_calls_and_events():
    target = web_object()
    assert target.logic.who() is target.logic
    assert target.logic.page is target
    assert target.logic.local_call() is target.logic
    assert target.logic.owner_call() is target
    assert ('changed', target.logic) in target.events
    assert target.logic.owner_method.__self__ is target
    assert target.logic.who.__self__ is target.logic


def test_web_proxy_assignment_shadows_owner_attribute():
    target = web_object()
    assert target.logic.read() == target.counter == 0
    target.logic.increment()
    assert target.logic.counter == 1
    assert target.counter == 0
    target.counter = 9
    assert target.logic.read() == 1


def test_web_proxy_mutable_fallback_shares_owner_object():
    target = web_object()
    assert target.logic.shared is target.shared
    target.logic.mutate()
    assert target.shared == {'changed': True}


def test_components_compose_and_preserve_overridden_method():
    class Carrier:
        pass
    class First:
        proxy = 'logic'
        def ping(self):
            return 'first'
    class Second:
        proxy = 'logic'
        def ping(self):
            return self.ping_() + '+second'
    gl.classMixin(Carrier, First)
    gl.classMixin(Carrier, Second)
    target = Carrier()
    gl.instanceMixin(target, Carrier)
    assert target.logic.ping() == 'first+second'
    assert target.logic.ping_.__self__ is target.logic


def test_repeated_instance_mixin_replaces_proxy_and_its_state():
    class FirstCarrier:
        pass
    class SecondCarrier:
        pass
    class Second:
        proxy = 'logic'
        def second(self):
            return 'second'
    gl.classMixin(FirstCarrier, Logic)
    gl.classMixin(SecondCarrier, Second)
    target = SimpleNamespace()
    gl.instanceMixin(target, FirstCarrier)
    first = target.logic
    first.marker = 42
    gl.instanceMixin(target, SecondCarrier)
    assert target.logic is not first
    assert not hasattr(target.logic, 'who')
    assert not hasattr(target.logic, 'marker')
    assert target.logic.second() == 'second'


def legacy_table(mixin):
    db = GnrSqlDb(implementation='postgres', dbname='unused', debug=True)
    table = db.model.src.package('app').table('item', pkey='id')
    table.column('id', dtype='L')
    db.tableMixin('app.item', mixin)
    db.startup()
    return db.table('app.item')


def test_direct_legacy_table_mixin_can_instantiate_generic_proxy():
    class Carrier:
        pass
    gl.classMixin(Carrier, Logic)
    table = legacy_table(Carrier)
    assert table.logic.main is table
    assert table.logic.who() is table.logic
    assert table.logic.main.column('id') is table.column('id')
    assert not hasattr(table.logic, 'query')


def test_intermediate_instance_loses_proxy_in_callable_only_second_mixin():
    from gnr.app.gnrapp import GnrMixinObj
    class Carrier:
        pass
    gl.classMixin(Carrier, Logic)
    intermediate = GnrMixinObj()
    gl.instanceMixin(intermediate, Carrier)
    assert hasattr(intermediate, 'logic')
    assert not hasattr(intermediate, 'logic_proxyclass')
    table = legacy_table(intermediate)
    assert not hasattr(table, 'logic')


def test_real_leonard_example_composes_bigbang_into_leo(monkeypatch, capsys):
    from gnr.web import gnrwsgisite
    from gnr.web.gnrwsgisite_proxy.gnrresourceloader import ResourceLoader
    from gnr.web.gnrwebpage import GnrWebPage
    legacy = Path(gl.__file__).resolve().parents[3]
    resources = legacy / 'projects/gnrcore/packages/test15/resources'
    loader = ResourceLoader.__new__(ResourceLoader)
    monkeypatch.setattr(gnrwsgisite, 'currentSite', lambda: SimpleNamespace(resource_loader=loader))
    class Composed(Page):
        resourceDirs = [str(resources)]
    gl.classMixin(Composed, f'{resources}/test_proxy.py:Leonard AS leo', only_callables=False)
    page = Composed()
    GnrWebPage.instantiateProxies(page)
    assert page.leo.page is page
    calls = []
    page.leo.makeBox(SimpleNamespace(div=lambda value: calls.append(value)))
    page.leo.fakeLaugh()
    assert calls == ['Hello everybody']
    assert 'AH AH AH' in capsys.readouterr().out
    assert gl.serializedFuncName(page.leo.callPenny) == 'leo.callPenny'
    assert not hasattr(page, 'makeBox')


def test_decorator_marker_alone_does_not_select_namespace():
    from gnr.web.gnrbaseclasses import page_proxy
    @page_proxy
    class Component:
        def ping(self):
            return self
    class Carrier:
        pass
    gl.classMixin(Carrier, Component)
    assert Component.is_proxy is True
    assert not hasattr(Carrier, 'component_proxyclass')
    target = Carrier()
    assert target.ping() is target


def test_two_aliases_share_function_rpc_metadata(tmp_path):
    path = tmp_path / 'alias_probe.py'
    path.write_text('class Component:\n    is_proxy = True\n    def rpc_ping(self):\n        return self\n')
    class Carrier:
        pass
    gl.classMixin(Carrier, f'{path}:Component AS first')
    gl.classMixin(Carrier, f'{path}:Component AS second')
    target = Carrier()
    gl.instanceMixin(target, Carrier)
    assert target.first.rpc_ping() is target.first
    assert target.second.rpc_ping() is target.second
    # Metadata lives on the shared source function, not on a bound method.
    assert target.first.rpc_ping.__func__ is target.second.rpc_ping.__func__
    assert gl.serializedFuncName(target.first.rpc_ping) == 'second.ping'
