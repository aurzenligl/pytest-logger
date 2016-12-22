import sys
import pytest
import platform
from py.code import Source
from _pytest.pytester import LineMatcher

win32py2 = sys.platform == 'win32' and sys.version_info[0] == 2
win32pypy = sys.platform == 'win32' and platform.python_implementation() == 'PyPy'


def makefile(testdir, path, content):
    return testdir.tmpdir.ensure(*path).write('\n'.join(Source(content)))


def ls(dir, filepath=''):
    return sorted([x.basename for x in dir.join(filepath).listdir()])


def basetemp(testdir):
    return testdir.tmpdir.join('..', 'basetemp')


class FileLineMatcher(LineMatcher):
    def __init__(self, dir, filepath):
        lines = dir.join(filepath).read().splitlines()
        LineMatcher.__init__(self, lines)


def test_logdir_fixture(testdir):
    makefile(testdir, ['test_foo1.py'], """
        import os

        def test_bar(logdir, tmpdir_factory):
            print(tmpdir_factory)
            assert str(logdir).endswith(os.path.join('logs', 'test_foo1.py', 'test_bar'))

        def test_baz(logdir):
            assert str(logdir).endswith(os.path.join('logs', 'test_foo1.py', 'test_baz'))

        class TestInsideClass(object):
            def test_qez(self, logdir):
                assert str(logdir).endswith(os.path.join('logs', 'test_foo1.py', 'TestInsideClass.test_qez'))

        import pytest
        @pytest.mark.parametrize('param1,param2', [
            ('abc', 'de'),
            (2, 4.127)
        ])
        def test_par(logdir, param1, param2):
            assert any((
                str(logdir).endswith(os.path.join('logs', 'test_foo1.py', 'test_par-abc-de')),
                str(logdir).endswith(os.path.join('logs', 'test_foo1.py', 'test_par-2-4.127')),
            ))
        def test_this_should_not_generate_logdir():
            pass
    """)
    makefile(testdir, ['subdir', 'test_foo2.py'], """
        import os
        def test_bar(logdir):
            assert str(logdir).endswith(os.path.join('logs', 'subdir', 'test_foo2.py', 'test_bar'))
    """)
    makefile(testdir, ['subdir', 'subsubdir', 'test_foo3.py'], """
        import os
        def test_bar(logdir):
            assert str(logdir).endswith(os.path.join('logs', 'subdir', 'subsubdir', 'test_foo3.py', 'test_bar'))
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
        '* foo: this is warning',
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
        '* foo: this is fatal',
        '* foo: this is error',
        '* foo: this is warning',
        '* bar: this is fatal',
        '* bar: this is error',
        '* baz: this is fatal',
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
        '* foo: this is fatal',
        '* foo: this is warning',
    ])
    FileLineMatcher(basetemp(testdir), 'logs/test_case.py/test_case/bar').fnmatch_lines([
        '* bar: this is fatal',
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
        '* foo: this is error',
        '* bar: this is error',
        '* baz: this is error',
    ])
    FileLineMatcher(basetemp(testdir), 'logs/test_case.py/test_case/foo').fnmatch_lines([
        '* foo: this is error',
        '* foo: this is warning',
    ])


@pytest.mark.skipif(win32py2, reason="python 2 on windows doesn't have symlink feature")
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


def test_format(testdir):
    makefile(testdir, ['conftest.py'], """
        import os
        import logging
        def pytest_logger_stdoutloggers(item):
            return ['']
        def pytest_logger_fileloggers(item):
            return ['']
    """)
    makefile(testdir, ['test_case.py'], """
        import logging
        def test_case():
            lgr = logging.getLogger('foo')
            lgr.setLevel(logging.DEBUG)
            lgr.fatal('this is fatal')
            lgr.error('this is error')
            lgr.warning('this is warning')
            lgr.info('this is info')
            lgr.debug('this is debug')
            lgr.log(35, 'this is 35')
    """)

    result = testdir.runpytest('-s')
    assert result.ret == 0

    expected_lines = [
        '*:*.* ftl foo: this is fatal',
        '*:*.* err foo: this is error',
        '*:*.* wrn foo: this is warning',
        '*:*.* inf foo: this is info',
        '*:*.* dbg foo: this is debug',
        '*:*.* l35 foo: this is 35',
    ]
    result.stdout.fnmatch_lines(expected_lines)
    FileLineMatcher(basetemp(testdir), 'logs/test_case.py/test_case/logs').fnmatch_lines(expected_lines)


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
    makefile(testdir, ['makes_nodeid_in_pytest29_contain_subdir_name', 'empty'], '')

    result = testdir.runpytest('subdir', 'makes_nodeid_in_pytest29_contain_subdir_name', '-s')
    assert result.ret == 0

    if not win32py2:
        assert ls(testdir.tmpdir, 'logs/subdir/test_case.py') == ['test_case']
        assert ls(testdir.tmpdir, 'subdir/logs/subdir/test_case.py') == ['test_case']

    result.stdout.fnmatch_lines([
        '',
        'subdir/test_case.py ',
        '* foo: this is warning',
        '* bar: this is warning',
        '.',
        ''
    ])

    FileLineMatcher(basetemp(testdir), 'logs/subdir/test_case.py/test_case/foo').fnmatch_lines([
        '* foo: this is warning',
    ])
    FileLineMatcher(basetemp(testdir), 'logs/subdir/test_case.py/test_case/bar').fnmatch_lines([
        '* bar: this is warning',
    ])


def test_skip_gracefully(testdir):
    makefile(testdir, ['conftest.py'], """
        import os
        def pytest_logger_stdoutloggers(item):
            return ['foo']
        def pytest_logger_fileloggers(item):
            return ['foo']
        def pytest_logger_logdirlink(config):
            return os.path.join(os.path.dirname(__file__), 'logs')
    """)
    makefile(testdir, ['test_case.py'], """
        import pytest
        @pytest.mark.skipif(True, reason='')
        def test_case():
            pass
    """)

    result = testdir.runpytest('-s')
    assert result.ret == 0

    assert 'logs' not in ls(testdir.tmpdir)


@pytest.mark.skipif(win32pypy, reason="pytest-xdist crashes on win32 under pypy")
def test_xdist(testdir):
    N = 8
    makefile(testdir, ['conftest.py'], """
        import os
        def pytest_logger_stdoutloggers(item):
            return ['foo']
        def pytest_logger_fileloggers(item):
            return ['foo']
        def pytest_logger_logdirlink(config):
            return os.path.join(os.path.dirname(__file__), 'logs')
    """)
    for index in range(N):
        makefile(testdir, ['test_case%s.py' % index], """
            import logging
            def test_case{0}():
                logging.getLogger('foo').warning('this is test {0}')
        """.format(index))

    result = testdir.runpytest('-n3')
    assert result.ret == 0

    if not win32py2:
        assert ls(testdir.tmpdir, 'logs') == ['test_case%s.py' % i for i in range(N)]

    for index in range(N):
        logfilename = 'logs/test_case{0}.py/test_case{0}/foo'.format(index)
        FileLineMatcher(basetemp(testdir), logfilename).fnmatch_lines(['* wrn foo: this is test %s' % index])
