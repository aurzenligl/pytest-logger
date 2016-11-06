import pytest
from _pytest._code import Source
from _pytest.pytester import LineMatcher

def makefile(testdir, path, content):
    return testdir.tmpdir.ensure(*path).write('\n'.join(Source(content)))

def ls(dir, filepath = ''):
    return sorted([x.basename for x in dir.join(filepath).listdir()])

def basetemp(testdir):
    return testdir.tmpdir.join('..', 'basetemp')

class FileLineMatcher(LineMatcher):
    def __init__(self, dir, filepath):
        lines = dir.join(filepath).read().splitlines()
        LineMatcher.__init__(self, lines)

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

    assert ls(basetemp(testdir), 'logs') == ['subdir', 'test_foo1.py']
    assert ls(basetemp(testdir), 'logs/subdir') == ['subsubdir', 'test_foo2.py']
    assert ls(basetemp(testdir), 'logs/subdir/subsubdir') == ['test_foo3.py']
    assert ls(basetemp(testdir), 'logs/subdir/subsubdir/test_foo3.py') == ['test_bar']
    assert ls(basetemp(testdir), 'logs/subdir/test_foo2.py') == ['test_bar']
    assert ls(basetemp(testdir), 'logs/test_foo1.py') == sorted([
        'test_bar',
        'test_baz',
        'TestInsideClass.test_qez',
        'test_par-abc-de',
        'test_par-2-4.127',
    ])

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

def test_file_handlers(testdir):
    makefile(testdir, ['conftest.py'], """
        import logging
        def pytest_logger_fileloggers(item):
            return [
                'foo',
                ('bar', logging.ERROR),
            ]
    """)
    makefile(testdir, ['test_case.py'], """
        import logging
        def test_case():
            for lgr in (logging.getLogger(name) for name in ['foo', 'bar']):
                lgr.fatal('this is fatal')
                lgr.warning('this is warning')
    """)

    result = testdir.runpytest('-s')
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py .',
        '',
    ])

    assert ls(basetemp(testdir), 'logs') == ['test_case.py']
    assert ls(basetemp(testdir), 'logs/test_case.py') == ['test_case']
    assert ls(basetemp(testdir), 'logs/test_case.py/test_case') == ['bar', 'foo']

    FileLineMatcher(basetemp(testdir), 'logs/test_case.py/test_case/foo').fnmatch_lines([
        '*:*.* foo: this is fatal',
        '*:*.* foo: this is warning',
    ])
    FileLineMatcher(basetemp(testdir), 'logs/test_case.py/test_case/bar').fnmatch_lines([
        '*:*.* bar: this is fatal',
    ])

def test_file_handlers_root(testdir):
    makefile(testdir, ['conftest.py'], """
        import logging
        def pytest_logger_fileloggers(item):
            return [
                ('', logging.ERROR),
                ('foo', logging.WARNING),
            ]
    """)
    makefile(testdir, ['test_case.py'], """
        import logging
        def test_case():
            for lgr in (logging.getLogger(name) for name in ['foo', 'bar', 'baz']):
                lgr.error('this is error')
                lgr.warning('this is warning')
    """)

    result = testdir.runpytest('-s')
    assert result.ret == 0

    result.stdout.fnmatch_lines([
        '',
        'test_case.py .',
        '',
    ])

    assert ls(basetemp(testdir), 'logs') == ['test_case.py']
    assert ls(basetemp(testdir), 'logs/test_case.py') == ['test_case']
    assert ls(basetemp(testdir), 'logs/test_case.py/test_case') == ['foo', 'logs']

    FileLineMatcher(basetemp(testdir), 'logs/test_case.py/test_case/logs').fnmatch_lines([
        '*:*.* foo: this is error',
        '*:*.* bar: this is error',
        '*:*.* baz: this is error',
    ])
    FileLineMatcher(basetemp(testdir), 'logs/test_case.py/test_case/foo').fnmatch_lines([
        '*:*.* foo: this is error',
        '*:*.* foo: this is warning',
    ])

def test_logdir_link(testdir):
    makefile(testdir, ['conftest.py'], """
        import os
        def pytest_logger_fileloggers(item):
            return ['']
        def pytest_logger_logdirlink(config):
            return os.path.join(os.path.dirname(__file__), 'my_link_dir')
    """)
    makefile(testdir, ['test_case.py'], """
        def test_case():
            pass
    """)

    result = testdir.runpytest('-s')
    assert result.ret == 0
    assert 'my_link_dir' in ls(testdir.tmpdir)
    assert ['test_case'] == ls(testdir.tmpdir, 'my_link_dir/test_case.py')

def test_multiple_conftests(testdir):
    makefile(testdir, ['conftest.py'], """
        import os
        def pytest_logger_stdoutloggers(item):
            return ['foo']
        def pytest_logger_fileloggers(item):
            return ['foo']
        def pytest_logger_logdirlink(config):
            return os.path.join(os.path.dirname(__file__), 'logs')
    """)
    makefile(testdir, ['subdir', 'conftest.py'], """
        import os
        def pytest_logger_stdoutloggers(item):
            return ['bar']
        def pytest_logger_fileloggers(item):
            return ['bar']
        def pytest_logger_logdirlink(config):
            return os.path.join(os.path.dirname(__file__), 'logs')
    """)
    makefile(testdir, ['subdir', 'test_case.py'], """
        import logging
        def test_case():
            for lgr in (logging.getLogger(name) for name in ['foo', 'bar']):
                lgr.warning('this is warning')
    """)

    result = testdir.runpytest('subdir', '-s')
    assert result.ret == 0

    assert ls(testdir.tmpdir, 'logs/subdir/test_case.py') == ['test_case']
    assert ls(testdir.tmpdir, 'subdir/logs/subdir/test_case.py') == ['test_case']

    result.stdout.fnmatch_lines([
        '',
        'subdir/test_case.py ',
        '*:*.* foo: this is warning',
        '*:*.* bar: this is warning',
        '.',
        ''
    ])

    FileLineMatcher(basetemp(testdir), 'logs/subdir/test_case.py/test_case/foo').fnmatch_lines([
        '*:*.* foo: this is warning',
    ])
    FileLineMatcher(basetemp(testdir), 'logs/subdir/test_case.py/test_case/bar').fnmatch_lines([
        '*:*.* bar: this is warning',
    ])
