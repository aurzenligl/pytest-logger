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


def outdir(testdir, dst):
    return testdir.tmpdir.join('..', dst)


@pytest.fixture(autouse=True)
def force_classic_output(monkeypatch, testdir):
    runpytest = testdir.runpytest

    def wrapper(*args, **kwargs):
        return runpytest('--override-ini=console_output_style=classic', *args, **kwargs)

    monkeypatch.setattr(testdir, 'runpytest', wrapper)


@pytest.fixture
def conftest_py(testdir):
    filename = 'conftest.py'
    makefile(testdir, [filename], """
        import logging
        def pytest_logger_fileloggers(item):
            return [
                'foo',
                ('bar', logging.ERROR),
            ]
    """)
    return filename


@pytest.fixture
def test_case_py(testdir):
    filename = 'test_case.py'
    makefile(testdir, [filename], """
        import logging
        def test_case():
            for lgr in (logging.getLogger(name) for name in ['foo', 'bar', 'baz']):
                lgr.error('this is error')
                lgr.warning('this is warning')
                lgr.info('this is info')
    """)
    return filename


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


def test_file_handlers(testdir, conftest_py, test_case_py):

    result = testdir.runpytest('-s')
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py .',
        '',
    ])

    assert ls(basetemp(testdir), 'logs') == [test_case_py]
    assert ls(basetemp(testdir), 'logs/{0}'.format(test_case_py)) == ['test_case']
    assert ls(basetemp(testdir), 'logs/{0}/test_case'.format(test_case_py)) == ['bar', 'foo']

    FileLineMatcher(basetemp(testdir), 'logs/{0}/test_case/foo'.format(test_case_py)).fnmatch_lines([
        '* foo: this is error',
        '* foo: this is warning',
    ])
    FileLineMatcher(basetemp(testdir), 'logs/{0}/test_case/bar'.format(test_case_py)).fnmatch_lines([
        '* bar: this is error',
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


def test_logsdir_option(testdir, conftest_py, test_case_py):

    logsdir = outdir(testdir, 'myinilogs')
    result = testdir.runpytest('-s', '--logger-logsdir={0}'.format(str(logsdir)))
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py .',
        '',
    ])

    assert ls(logsdir) == [test_case_py]
    assert ls(logsdir, test_case_py) == ['test_case']
    assert ls(logsdir, '{0}/test_case'.format(test_case_py)) == ['bar', 'foo']

    FileLineMatcher(logsdir, '{0}/test_case/foo'.format(test_case_py)).fnmatch_lines([
        '* foo: this is error',
        '* foo: this is warning',
    ])
    FileLineMatcher(logsdir, '{0}/test_case/bar'.format(test_case_py)).fnmatch_lines([
        '* bar: this is error',
    ])


def test_logsdir_ini(testdir, conftest_py, test_case_py):

    logsdir = outdir(testdir, 'myinilogs')
    makefile(testdir, ['pytest.ini'], """
        [pytest]
        logger_logsdir={0}
    """.format(logsdir))

    result = testdir.runpytest('-s')
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py .',
        '',
    ])

    assert ls(logsdir) == [test_case_py]
    assert ls(logsdir, test_case_py) == ['test_case']
    assert ls(logsdir, '{0}/test_case'.format(test_case_py)) == ['bar', 'foo']

    FileLineMatcher(logsdir, '{0}/test_case/foo'.format(test_case_py)).fnmatch_lines([
        '* foo: this is error',
        '* foo: this is warning',
    ])
    FileLineMatcher(logsdir, '{0}/test_case/bar'.format(test_case_py)).fnmatch_lines([
        '* bar: this is error',
    ])


def test_logsdir_cleanup(testdir, conftest_py, test_case_py):

    logsdir = outdir(testdir, 'myinilogs')

    makefile(testdir, ['pytest.ini'], """
        [pytest]
        logger_logsdir={0}
    """.format(logsdir))

    logsdir.ensure('tmpfile').write('\n'.join(Source('this shall be removed')))
    logsdir.join('tmpdir')

    result = testdir.runpytest('-s')
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py .',
        '',
    ])

    assert ls(logsdir) == [test_case_py]
    assert ls(logsdir, test_case_py) == ['test_case']
    assert ls(logsdir, '{0}/test_case'.format(test_case_py)) == ['bar', 'foo']

    FileLineMatcher(logsdir, '{0}/test_case/foo'.format(test_case_py)).fnmatch_lines([
        '* foo: this is error',
        '* foo: this is warning',
    ])
    FileLineMatcher(logsdir, '{0}/test_case/bar'.format(test_case_py)).fnmatch_lines([
        '* bar: this is error',
    ])


def test_logger_config(testdir, test_case_py):
    makefile(testdir, ['conftest.py'], """
        def pytest_logger_config(logger_config):
            logger_config.add_loggers(['foo', 'bar'], stdout_level='warning', file_level='info')
            logger_config.add_loggers(['baz'], stdout_level='error', file_level='warning')
            logger_config.set_log_option_default('foo,bar,baz')
    """)

    result = testdir.runpytest('-s')
    assert result.ret == 0

    result.stdout.fnmatch_lines([
        '',
        'test_case.py ',
        '* err foo: this is error',
        '* wrn foo: this is warning',
        '* err bar: this is error',
        '* wrn bar: this is warning',
        '* err baz: this is error',
        '.',
        '',
    ])
    FileLineMatcher(basetemp(testdir), 'logs/test_case.py/test_case/foo').fnmatch_lines([
        '* err foo: this is error',
        '* wrn foo: this is warning',
        '* inf foo: this is info',
    ])
    FileLineMatcher(basetemp(testdir), 'logs/test_case.py/test_case/bar').fnmatch_lines([
        '* err bar: this is error',
        '* wrn bar: this is warning',
        '* inf bar: this is info',
    ])
    FileLineMatcher(basetemp(testdir), 'logs/test_case.py/test_case/baz').fnmatch_lines([
        '* err baz: this is error',
        '* wrn baz: this is warning',
    ])


@pytest.mark.parametrize('log_option', ('', '--loggers=foo.info,baz'))
def test_logger_config_option(testdir, test_case_py, log_option):
    makefile(testdir, ['conftest.py'], """
        def pytest_logger_config(logger_config):
            logger_config.add_loggers(['foo', 'bar'])
            logger_config.add_loggers(['baz'], file_level='error')
    """)

    opts = ('-s', log_option) if log_option else ('-s',)
    result = testdir.runpytest(*opts)
    assert result.ret == 0

    if log_option:
        result.stdout.fnmatch_lines([
            '',
            'test_case.py ',
            '* err foo: this is error',
            '* wrn foo: this is warning',
            '* inf foo: this is info',
            '* err baz: this is error',
            '.',
            '',
        ])
    else:
        result.stdout.fnmatch_lines([
            '',
            'test_case.py .',
            '',
        ])


@pytest.mark.parametrize('log_option', ('', '--loggers=foo.info,baz'))
def test_logger_config_formatter(testdir, test_case_py, log_option):
    makefile(testdir, ['conftest.py'], """
        import logging

        def pytest_logger_config(logger_config):
            logger_config.add_loggers(['foo', 'bar'])
            logger_config.add_loggers(['baz'], file_level='error')
            logger_config.set_formatter_class(logging.Formatter)
    """)

    opts = ('-s', log_option) if log_option else ('-s',)
    result = testdir.runpytest(*opts)
    assert result.ret == 0

    if log_option:
        result.stdout.fnmatch_lines([
            '',
            'test_case.py ',
            'this is error',
            'this is warning',
            'this is info',
            'this is error',
            '.',
            '',
        ])
    else:
        result.stdout.fnmatch_lines([
            '',
            'test_case.py .',
            '',
        ])


@pytest.mark.parametrize('with_hook', (False, True))
def test_logger_config_option_missing_without_hook(testdir, test_case_py, with_hook):
    makefile(testdir, ['conftest.py'], """
        def pytest_addoption(parser):
            parser.addoption('--loggers')
    """ + ("""
        def pytest_logger_config(logger_config):
            logger_config.add_loggers(['foo', 'bar'], stdout_level='warning', file_level='info')
            logger_config.add_loggers(['baz'], stdout_level='error', file_level='warning')
    """ if with_hook else ""))

    result = testdir.runpytest('-s', '--loggers=foo')
    assert result.ret == (3 if with_hook else 0)

    if with_hook:
        result.stderr.fnmatch_lines([
            '*ArgumentError: argument --loggers: conflicting option string*: --loggers',
        ])


@pytest.mark.parametrize('stdout_hook', (False, True))
@pytest.mark.parametrize('config_hook', (False, True))
def test_error_both_hook_apis_used(testdir, test_case_py, stdout_hook, config_hook):
    makefile(testdir, ['conftest.py'], ("""
        def pytest_logger_stdoutloggers(item):
            return ['foo']
    """ if stdout_hook else '') + ("""
        def pytest_logger_config(logger_config):
            logger_config.add_loggers(['foo'])
    """ if config_hook else ''))

    result = testdir.runpytest('-s')
    assert result.ret == (1 if (stdout_hook and config_hook) else 0)

    if stdout_hook and config_hook:
        result.stdout.fnmatch_lines([
            '*AssertionError: pytest_logger_config and pytest_logger_*loggers hooks used at the same time',
        ])


def test_help_prints(testdir, test_case_py):
    """
    Pytest doesn't evaluate group.addoption(..., type=...) option when run with --help option.
    This causes log option string to remain as unchecked string instead of a list in expected format.
    This happens regardless of --loggers option source (default, cmdline, etc.),

    To remedy this hack checking whether option has been parsed was made.
    This test ensures that it keeps working.
    """
    makefile(testdir, ['conftest.py'], ("""
        def pytest_logger_config(logger_config):
            logger_config.add_loggers(['foo'])
            logger_config.set_log_option_default('foo')
    """))

    result = testdir.runpytest('-s', '--help')
    assert result.ret == 0
