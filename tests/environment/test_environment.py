import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

import pytest

from asqueel.environment import SqlEnvironment


def test_defaults_snapshots_and_scope_arguments_are_detached():
    defaults = {'settings': {'allowed': [1]}, 'name': 'base'}
    env = SqlEnvironment(defaults)
    defaults['settings']['allowed'].append(2)
    first = env.snapshot()
    with pytest.raises(TypeError):
        first['name'] = 'mutated'
    first['settings']['allowed'].append(3)
    assert env.current_env == {'settings': {'allowed': [1]}, 'name': 'base'}
    scope = {'allowed': [4]}
    with env.temp_env(settings=scope):
        scope['allowed'].append(5)
        snapshot = env.current_env
        snapshot['settings']['allowed'].append(6)
        assert env.current_env['settings'] == {'allowed': [4]}
    assert env.current_env['settings'] == {'allowed': [1]}


def test_nested_scopes_restore_and_none_is_explicit():
    env = SqlEnvironment({'name': 'base'})
    assert 'optional' not in env.current_env
    with env.tempEnv(name='outer', optional=None) as scoped:
        assert scoped is env
        assert env.currentEnv == {'name': 'outer', 'optional': None}
        with env.temp_env(name='inner', extra=7):
            assert env.current_env == {'name': 'inner', 'optional': None, 'extra': 7}
        assert env.current_env == {'name': 'outer', 'optional': None}
    assert env.current_env == {'name': 'base'}
    assert 'optional' not in env.current_env


def test_exception_restores_and_instances_are_isolated():
    left = SqlEnvironment({'name': 'left'})
    right = SqlEnvironment({'name': 'right'})
    with pytest.raises(RuntimeError):
        with left.temp_env(name='changed'):
            assert right.current_env['name'] == 'right'
            raise RuntimeError('scope failed')
    assert left.current_env['name'] == 'left'


def test_child_tasks_inherit_then_isolate_scopes_and_snapshots():
    async def scenario():
        env = SqlEnvironment({'settings': {'allowed': [1]}})
        ready = asyncio.Event()

        async def child(name):
            inherited = env.current_env
            await ready.wait()
            inherited['settings']['allowed'].append(name)
            with env.temp_env(name=name):
                await asyncio.sleep(0)
                assert env.current_env['name'] == name
                assert env.current_env['settings']['allowed'] == [1]
            assert env.current_env['name'] == 'parent'
            return env.snapshot()

        with env.temp_env(name='parent'):
            first = asyncio.create_task(child('first'))
            second = asyncio.create_task(child('second'))
            await asyncio.sleep(0)
        # Existing child tasks retain their inherited context after parent reset.
        assert 'name' not in env.current_env
        ready.set()
        results = await asyncio.gather(first, second)
        assert all(result == {'name': 'parent', 'settings': {'allowed': [1]}} for result in results)
        assert env.current_env == {'settings': {'allowed': [1]}}
    asyncio.run(scenario())


def test_async_cancellation_restores_scope_before_propagating():
    async def scenario():
        env = SqlEnvironment({'name': 'base'})
        started = asyncio.Event()
        restored = []

        async def worker():
            try:
                with env.temp_env(name='worker'):
                    started.set()
                    await asyncio.Event().wait()
            except asyncio.CancelledError:
                restored.append(env.current_env)
                raise

        task = asyncio.create_task(worker())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert restored == [{'name': 'base'}]
        assert env.current_env == {'name': 'base'}
    asyncio.run(scenario())


def test_threads_need_explicit_context_propagation_and_do_not_leak():
    env = SqlEnvironment({'name': 'base'})
    with ThreadPoolExecutor(max_workers=1) as executor:
        with env.temp_env(name='request'):
            context = copy_context()
            assert executor.submit(context.run, env.snapshot).result() == {'name': 'request'}
            assert executor.submit(env.snapshot).result() == {'name': 'base'}
        assert executor.submit(env.snapshot).result() == {'name': 'base'}


def test_uncopyable_values_fail_descriptively_without_changing_context():
    class Uncopyable:
        def __deepcopy__(self, memo):
            raise TypeError('cannot clone')

    with pytest.raises(ValueError, match='initialization') as error:
        SqlEnvironment({'value': Uncopyable()})
    assert isinstance(error.value.__cause__, TypeError)
    env = SqlEnvironment({'name': 'base'})
    with pytest.raises(ValueError, match='scope entry'):
        with env.temp_env(value=Uncopyable()):
            raise AssertionError('scope must never start')
    assert env.current_env == {'name': 'base'}


def test_empty_environment_and_repeated_scopes():
    env = SqlEnvironment()
    assert env.snapshot() == {}
    for value in range(3):
        with env.temp_env(value=value):
            assert env.snapshot()['value'] == value
        assert env.snapshot() == {}
