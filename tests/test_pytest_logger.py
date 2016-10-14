import pytest
from _pytest._code import Source

def makefile(testdir, path, content):
    return testdir.tmpdir.ensure(*path).write('\n'.join(Source(content)))

def ls(path):
    return [x.basename for x in path.listdir()]

def test_logdir_fixture(testdir):
    makefile(testdir, ['test_foo1.py'], """
        def test_bar(logdir, tmpdir_factory):
            print tmpdir_factory
            assert str(logdir).endswith('/logs/test_foo1.py/test_bar')

        def test_baz(logdir):
            assert str(logdir).endswith('/logs/test_foo1.py/test_baz')

        class TestInsideClass(object):
            def test_qez(self, logdir):
                assert str(logdir).endswith('/logs/test_foo1.py/TestInsideClass.test_qez')

        import pytest
        @pytest.mark.parametrize('param1,param2', [
            ('abc', 'de'),
            (2, 4.127)
        ])
        def test_par(logdir, param1, param2):
            assert any((
                str(logdir).endswith('/logs/test_foo1.py/test_par-abc-de'),
                str(logdir).endswith('/logs/test_foo1.py/test_par-2-4.127'),
            ))
        def test_this_should_not_generate_logdir():
            pass
    """)
    makefile(testdir, ['subdir', 'test_foo2.py'], """
        def test_bar(logdir):
            assert str(logdir).endswith('/logs/subdir/test_foo2.py/test_bar')
    """)
    makefile(testdir, ['subdir', 'subsubdir', 'test_foo3.py'], """
        def test_bar(logdir):
            assert str(logdir).endswith('/logs/subdir/subsubdir/test_foo3.py/test_bar')
    """)

    result = testdir.runpytest()

    assert result.ret == 0

    basetemp = testdir.tmpdir.join('..', 'basetemp')

    assert sorted(ls(basetemp.join('logs'))) == sorted(['test_foo1.py', 'subdir'])
    assert sorted(ls(basetemp.join('logs', 'subdir'))) == sorted(['test_foo2.py', 'subsubdir'])
    assert sorted(ls(basetemp.join('logs', 'subdir', 'subsubdir'))) == sorted(['test_foo3.py'])
    assert sorted(ls(basetemp.join('logs', 'test_foo1.py'))) == sorted([
        'test_bar',
        'test_baz',
        'TestInsideClass.test_qez',
        'test_par-abc-de',
        'test_par-2-4.127',
    ])
    assert sorted(ls(basetemp.join('logs', 'subdir', 'test_foo2.py'))) == ['test_bar']
    assert sorted(ls(basetemp.join('logs', 'subdir', 'subsubdir', 'test_foo3.py'))) == ['test_bar']

def test_stdout_handlers(testdir):
    makefile(testdir, ['conftest.py'], """
        def pytest_logger_stdoutloggers(item):
            return ['foo']
    """)
    makefile(testdir, ['test_case.py'], """
        import logging
        def test_case():
            logging.getLogger('foo').warning('this is warning')
            logging.getLogger('foo').info('you do not see me: level too low')
            logging.getLogger('bar').warning('you do not see me: logger not handled')
    """)

    result = testdir.runpytest()
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py .',
        '',
    ])

    result = testdir.runpytest('-s')
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py ',
        '*:*.* foo: this is warning',
        '.',
        ''
    ])

def test_stdout_handlers_many_loggers(testdir):
    makefile(testdir, ['conftest.py'], """
        import logging
        def pytest_logger_stdoutloggers(item):
            return [
                'foo',
                ('bar', logging.ERROR),
                ('baz', logging.FATAL)
            ]
    """)
    makefile(testdir, ['test_case.py'], """
        import logging
        def test_case():
            for lgr in (logging.getLogger(name) for name in ['foo', 'bar', 'baz']):
                lgr.fatal('this is fatal')
                lgr.error('this is error')
                lgr.warning('this is warning')
    """)

    result = testdir.runpytest('-s')
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py ',
        '*:*.* foo: this is fatal',
        '*:*.* foo: this is error',
        '*:*.* foo: this is warning',
        '*:*.* bar: this is fatal',
        '*:*.* bar: this is error',
        '*:*.* baz: this is fatal',
        '.',
        ''
    ])
