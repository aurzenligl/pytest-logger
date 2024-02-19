import os
import pytest
import textwrap
from pathlib import Path


def makefile(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))
    return path


def ls(dir: Path, filepath=''):
    return sorted(os.listdir(dir / filepath))


def basetemp(pytester):
    return pytester.path.parent / 'basetemp'


@pytest.fixture(autouse=True)
def set_classic_output(monkeypatch, pytester):
    runpytest = pytester.runpytest

    def wrapper(*args, **kwargs):
        return runpytest('--override-ini=console_output_style=classic', *args, **kwargs)

    monkeypatch.setattr(pytester, 'runpytest', wrapper)


@pytest.fixture
def conftest_py(pytester):
    return makefile(pytester.path / 'conftest.py', """
        import logging
        def pytest_logger_fileloggers(item):
            return [
                'foo',
                ('bar', logging.ERROR),
            ]
    """)


@pytest.fixture
def test_case_py(pytester):
    return makefile(pytester.path / 'test_case.py', """
        import logging
        def test_case():
            for lgr in (logging.getLogger(name) for name in ['foo', 'bar', 'baz']):
                lgr.error('this is error')
                lgr.warning('this is warning')
                lgr.info('this is info')
    """)


class FileLineMatcher(pytest.LineMatcher):
    def __init__(self, path: Path):
        super().__init__(path.read_text().splitlines())


def test_logdir_fixture(pytester):
    makefile(pytester.path / 'test_foo1.py', """
        import os

        def test_bar(logdir, tmpdir_factory):
            print(tmpdir_factory)
            assert str(logdir).endswith(os.path.join('logs', 'test_foo1.py', 'test_bar'))

        def test_baz(logdir):
            assert str(logdir).endswith(os.path.join('logs', 'test_foo1.py', 'test_baz'))

        class TestInsideClass(object):
            def test_qez(self, logdir):
                assert str(logdir).endswith(os.path.join('logs', 'test_foo1.py', 'TestInsideClass', 'test_qez'))

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
    makefile(pytester.path / 'subdir' / 'test_foo2.py', """
        import os
        def test_bar(logdir):
            assert str(logdir).endswith(os.path.join('logs', 'subdir', 'test_foo2.py', 'test_bar'))
    """)
    makefile(pytester.path / 'subdir' / 'subsubdir' / 'test_foo3.py', """
        import os
        def test_bar(logdir):
            assert str(logdir).endswith(os.path.join('logs', 'subdir', 'subsubdir', 'test_foo3.py', 'test_bar'))
    """)

    result = pytester.runpytest()
    assert result.ret == 0

    assert ls(basetemp(pytester), 'logs') == ['subdir', 'test_foo1.py']
    assert ls(basetemp(pytester), 'logs/subdir') == ['subsubdir', 'test_foo2.py']
    assert ls(basetemp(pytester), 'logs/subdir/subsubdir') == ['test_foo3.py']
    assert ls(basetemp(pytester), 'logs/subdir/subsubdir/test_foo3.py') == ['test_bar']
    assert ls(basetemp(pytester), 'logs/subdir/test_foo2.py') == ['test_bar']
    assert ls(basetemp(pytester), 'logs/test_foo1.py') == sorted([
        'test_bar',
        'test_baz',
        'TestInsideClass',
        'test_par-abc-de',
        'test_par-2-4.127',
    ])
    assert ls(basetemp(pytester), 'logs/test_foo1.py/TestInsideClass') == ['test_qez']


def test_stdout_handlers(pytester):
    makefile(pytester.path / 'conftest.py', """
        def pytest_logger_stdoutloggers(item):
            return ['foo']
    """)
    makefile(pytester.path / 'test_case.py', """
        import logging
        def test_case():
            logging.getLogger('foo').warning('this is warning')
            logging.getLogger('foo').info('you do not see me: level too low')
            logging.getLogger('bar').warning('you do not see me: logger not handled')
    """)

    result = pytester.runpytest()
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py .',
        '',
    ])

    result = pytester.runpytest('-s')
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py ',
        '* foo: this is warning',
        '.',
        ''
    ])


def test_stdout_handlers_many_loggers(pytester):
    makefile(pytester.path / 'conftest.py', """
        import logging
        def pytest_logger_stdoutloggers(item):
            return [
                'foo',
                ('bar', logging.ERROR),
                ('baz', logging.FATAL)
            ]
    """)
    makefile(pytester.path / 'test_case.py', """
        import logging
        def test_case():
            for lgr in (logging.getLogger(name) for name in ['foo', 'bar', 'baz']):
                lgr.fatal('this is fatal')
                lgr.error('this is error')
                lgr.warning('this is warning')
    """)

    result = pytester.runpytest('-s')
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


def test_file_handlers(pytester, conftest_py, test_case_py):
    result = pytester.runpytest('-s')
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py .',
        '',
    ])

    assert ls(basetemp(pytester), 'logs') == [test_case_py.name]
    assert ls(basetemp(pytester), 'logs/{0}'.format(test_case_py.name)) == ['test_case']
    assert ls(basetemp(pytester), 'logs/{0}/test_case'.format(test_case_py.name)) == ['bar', 'foo']

    FileLineMatcher(basetemp(pytester) / f'logs/{test_case_py.name}/test_case/foo').fnmatch_lines([
        '* foo: this is error',
        '* foo: this is warning',
    ])
    FileLineMatcher(basetemp(pytester) / f'logs/{test_case_py.name}/test_case/bar').fnmatch_lines([
        '* bar: this is error',
    ])


def test_split_logs_by_outcome(pytester):
    makefile(pytester.path / 'conftest.py', """
        import logging
        def pytest_logger_fileloggers(item):
            return [
                'foo',
                ('bar', logging.ERROR),
            ]

        def pytest_logger_config(logger_config):
            logger_config.split_by_outcome(outcomes=['passed', 'failed'])
    """)
    makefile(pytester.path / 'test_case.py', """
        import pytest
        import logging
        def test_case_that_fails():
            for lgr in (logging.getLogger(name) for name in ['foo', 'bar', 'baz']):
                lgr.error('this is error')
                lgr.warning('this is warning')
            pytest.fail('just checking')

        def test_case_that_passes():
            for lgr in (logging.getLogger(name) for name in ['foo', 'bar', 'baz']):
                lgr.error('this is error')
                lgr.warning('this is warning')
    """)
    result = pytester.runpytest('-s')
    assert result.ret != 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py F.',
        '',
    ])

    assert 'by_outcome' in ls(basetemp(pytester) / 'logs')

    assert 'failed' in ls(basetemp(pytester) / 'logs' / 'by_outcome')
    failedlogpath = basetemp(pytester) / 'logs' / 'by_outcome' / 'failed' / 'test_case.py' / 'test_case_that_fails'
    assert failedlogpath.is_symlink()
    failedlogdest = os.path.join(
        os.path.pardir, os.path.pardir, os.path.pardir, 'test_case.py', 'test_case_that_fails')
    assert os.readlink(str(failedlogpath)) == failedlogdest

    assert 'passed' in ls(basetemp(pytester) / 'logs' / 'by_outcome')
    passedlogpath = basetemp(pytester) / 'logs' / 'by_outcome' / 'passed' / 'test_case.py' / 'test_case_that_passes'
    assert passedlogpath.is_symlink()
    passedlogdest = os.path.join(
        os.path.pardir, os.path.pardir, os.path.pardir, 'test_case.py', 'test_case_that_passes')
    assert os.readlink(str(passedlogpath)) == passedlogdest


def test_file_handlers_root(pytester):
    makefile(pytester.path / 'conftest.py', """
        import logging
        def pytest_logger_fileloggers(item):
            return [
                ('', logging.ERROR),
                ('foo', logging.WARNING),
            ]
    """)
    makefile(pytester.path / 'test_case.py', """
        import logging
        def test_case():
            for lgr in (logging.getLogger(name) for name in ['foo', 'bar', 'baz']):
                lgr.error('this is error')
                lgr.warning('this is warning')
    """)

    result = pytester.runpytest('-s')
    assert result.ret == 0

    result.stdout.fnmatch_lines([
        '',
        'test_case.py .',
        '',
    ])

    assert ls(basetemp(pytester), 'logs') == ['test_case.py']
    assert ls(basetemp(pytester), 'logs/test_case.py') == ['test_case']
    assert ls(basetemp(pytester), 'logs/test_case.py/test_case') == ['foo', 'logs']

    FileLineMatcher(basetemp(pytester) / 'logs/test_case.py/test_case/logs').fnmatch_lines([
        '* foo: this is error',
        '* bar: this is error',
        '* baz: this is error',
    ])
    FileLineMatcher(basetemp(pytester) / 'logs/test_case.py/test_case/foo').fnmatch_lines([
        '* foo: this is error',
        '* foo: this is warning',
    ])


def test_logdir_link(pytester):
    makefile(pytester.path / 'conftest.py', """
        import os
        def pytest_logger_fileloggers(item):
            return ['']
        def pytest_logger_logdirlink(config):
            return os.path.join(os.path.dirname(__file__), 'my_link_dir')
    """)
    makefile(pytester.path / 'test_case.py', """
        def test_case():
            pass
    """)

    result = pytester.runpytest('-s')
    assert result.ret == 0
    assert 'my_link_dir' in ls(pytester.path)
    assert ['test_case'] == ls(pytester.path, 'my_link_dir/test_case.py')


def test_logsdir(pytester):
    makefile(pytester.path / 'conftest.py', """
        import os
        def pytest_logger_fileloggers(item):
            return ['']
        def pytest_logger_logsdir(config):
            return os.path.join(os.path.dirname(__file__), 'my_logs_dir')
    """)
    makefile(pytester.path / 'test_cases.py', """
        import pytest

        def test_simple():
            pass

        @pytest.mark.parametrize('param1, param2', [
            ('x', 'a_b_c'),
            ('y', 'd/e/f'),
            ('z', '/g/h/i'),
            ('v', '/j-1/k-1/l-1'),
        ])
        def test_param(param1, param2):
            pass
    """)

    result = pytester.runpytest('-s')
    assert result.ret == 0
    assert 'my_logs_dir' in ls(pytester.path)
    assert 'test_simple' in ls(pytester.path, 'my_logs_dir/test_cases.py')
    assert 'test_param-x-a_b_c' in ls(pytester.path, 'my_logs_dir/test_cases.py')
    assert 'test_param-y-d-e-f' in ls(pytester.path, 'my_logs_dir/test_cases.py')
    assert 'test_param-z-g-h-i' in ls(pytester.path, 'my_logs_dir/test_cases.py')
    assert 'test_param-v-j-1-k-1-l-1' in ls(pytester.path, 'my_logs_dir/test_cases.py')


def test_format(pytester):
    makefile(pytester.path / 'conftest.py', """
        import os
        import logging
        def pytest_logger_stdoutloggers(item):
            return ['']
        def pytest_logger_fileloggers(item):
            return ['']
    """)
    makefile(pytester.path / 'test_case.py', """
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

    result = pytester.runpytest('-s')
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
    FileLineMatcher(basetemp(pytester) / 'logs/test_case.py/test_case/logs').fnmatch_lines(expected_lines)


def test_multiple_conftests(pytester):
    makefile(pytester.path / 'conftest.py', """
        import os
        def pytest_logger_stdoutloggers(item):
            return ['foo']
        def pytest_logger_fileloggers(item):
            return ['foo']
        def pytest_logger_logdirlink(config):
            return os.path.join(os.path.dirname(__file__), 'logs')
    """)
    makefile(pytester.path / 'subdir' / 'conftest.py', """
        import os
        def pytest_logger_stdoutloggers(item):
            return ['bar']
        def pytest_logger_fileloggers(item):
            return ['bar']
        def pytest_logger_logdirlink(config):
            return os.path.join(os.path.dirname(__file__), 'logs')
    """)
    makefile(pytester.path / 'subdir' / 'test_case.py', """
        import logging
        def test_case():
            for lgr in (logging.getLogger(name) for name in ['foo', 'bar']):
                lgr.warning('this is warning')
    """)
    makefile(pytester.path / 'makes_nodeid_in_pytest29_contain_subdir_name' / 'empty', '')

    result = pytester.runpytest('subdir', 'makes_nodeid_in_pytest29_contain_subdir_name', '-s')
    assert result.ret == 0

    assert ls(pytester.path, 'logs/subdir/test_case.py') == ['test_case']
    assert ls(pytester.path, 'subdir/logs/subdir/test_case.py') == ['test_case']

    result.stdout.fnmatch_lines([
        '',
        'subdir/test_case.py ',
        '* foo: this is warning',
        '* bar: this is warning',
        '.',
        ''
    ])

    FileLineMatcher(basetemp(pytester) / 'logs/subdir/test_case.py/test_case/foo').fnmatch_lines([
        '* foo: this is warning',
    ])
    FileLineMatcher(basetemp(pytester) / 'logs/subdir/test_case.py/test_case/bar').fnmatch_lines([
        '* bar: this is warning',
    ])


def test_skip_gracefully(pytester):
    makefile(pytester.path / 'conftest.py', """
        import os
        def pytest_logger_stdoutloggers(item):
            return ['foo']
        def pytest_logger_fileloggers(item):
            return ['foo']
        def pytest_logger_logdirlink(config):
            return os.path.join(os.path.dirname(__file__), 'logs')
    """)
    makefile(pytester.path / 'test_case.py', """
        import pytest
        @pytest.mark.skipif(True, reason='')
        def test_case():
            pass
    """)

    result = pytester.runpytest('-s')
    assert result.ret == 0

    assert 'logs' not in ls(pytester.path)


def test_xdist(pytester):
    N = 8
    makefile(pytester.path / 'conftest.py', """
        import os
        def pytest_logger_stdoutloggers(item):
            return ['foo']
        def pytest_logger_fileloggers(item):
            return ['foo']
        def pytest_logger_logdirlink(config):
            return os.path.join(os.path.dirname(__file__), 'logs')
    """)
    for index in range(N):
        makefile(pytester.path / f'test_case{index}.py', """
            import logging
            def test_case{0}():
                logging.getLogger('foo').warning('this is test {0}')
        """.format(index))

    result = pytester.runpytest('-n3')
    assert result.ret == 0

    assert ls(pytester.path, 'logs') == ['test_case%s.py' % i for i in range(N)]

    for index in range(N):
        logfilename = 'logs/test_case{0}.py/test_case{0}/foo'.format(index)
        FileLineMatcher(basetemp(pytester) / logfilename).fnmatch_lines(['* wrn foo: this is test %s' % index])


def test_logsdir_option(pytester, conftest_py, test_case_py):
    logsdir = pytester.path / 'myinilogs'
    result = pytester.runpytest('-s', '--logger-logsdir={0}'.format(str(logsdir)))
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py .',
        '',
    ])

    assert ls(logsdir) == [test_case_py.name]
    assert ls(logsdir, test_case_py.name) == ['test_case']
    assert ls(logsdir, '{0}/test_case'.format(test_case_py.name)) == ['bar', 'foo']

    FileLineMatcher(logsdir / '{0}/test_case/foo'.format(test_case_py.name)).fnmatch_lines([
        '* foo: this is error',
        '* foo: this is warning',
    ])
    FileLineMatcher(logsdir / '{0}/test_case/bar'.format(test_case_py.name)).fnmatch_lines([
        '* bar: this is error',
    ])


def test_logsdir_ini(pytester, conftest_py, test_case_py):
    logsdir = pytester.path / 'myinilogs'
    makefile(pytester.path / 'pytest.ini', """
        [pytest]
        logger_logsdir={0}
    """.format(logsdir))

    result = pytester.runpytest('-s')
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py .',
        '',
    ])

    assert ls(logsdir) == [test_case_py.name]
    assert ls(logsdir, test_case_py.name) == ['test_case']
    assert ls(logsdir, '{0}/test_case'.format(test_case_py.name)) == ['bar', 'foo']

    FileLineMatcher(logsdir / '{0}/test_case/foo'.format(test_case_py.name)).fnmatch_lines([
        '* foo: this is error',
        '* foo: this is warning',
    ])
    FileLineMatcher(logsdir / '{0}/test_case/bar'.format(test_case_py.name)).fnmatch_lines([
        '* bar: this is error',
    ])


def test_logsdir_cleanup(pytester, conftest_py, test_case_py):
    logsdir = pytester.path / 'myinilogs'

    makefile(pytester.path / 'pytest.ini', """
        [pytest]
        logger_logsdir={0}
    """.format(logsdir))
    makefile(logsdir / 'tmpfile', """
        this shall be removed
    """)

    result = pytester.runpytest('-s')
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        '',
        'test_case.py .',
        '',
    ])

    assert ls(logsdir) == [test_case_py.name]
    assert ls(logsdir, test_case_py.name) == ['test_case']
    assert ls(logsdir, '{0}/test_case'.format(test_case_py.name)) == ['bar', 'foo']

    FileLineMatcher(logsdir / '{0}/test_case/foo'.format(test_case_py.name)).fnmatch_lines([
        '* foo: this is error',
        '* foo: this is warning',
    ])
    FileLineMatcher(logsdir / '{0}/test_case/bar'.format(test_case_py.name)).fnmatch_lines([
        '* bar: this is error',
    ])


def test_logger_config(pytester, test_case_py):
    makefile(pytester.path / 'conftest.py', """
        def pytest_logger_config(logger_config):
            logger_config.add_loggers(['foo', 'bar'], stdout_level='warning', file_level='info')
            logger_config.add_loggers(['baz'], stdout_level='error', file_level='warning')
            logger_config.set_log_option_default('foo,bar,baz')
    """)

    result = pytester.runpytest('-s')
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
    FileLineMatcher(basetemp(pytester) / 'logs/test_case.py/test_case/foo').fnmatch_lines([
        '* err foo: this is error',
        '* wrn foo: this is warning',
        '* inf foo: this is info',
    ])
    FileLineMatcher(basetemp(pytester) / 'logs/test_case.py/test_case/bar').fnmatch_lines([
        '* err bar: this is error',
        '* wrn bar: this is warning',
        '* inf bar: this is info',
    ])
    FileLineMatcher(basetemp(pytester) / 'logs/test_case.py/test_case/baz').fnmatch_lines([
        '* err baz: this is error',
        '* wrn baz: this is warning',
    ])


@pytest.mark.parametrize('log_option', ('', '--loggers=foo.info,baz'))
def test_logger_config_option(pytester, test_case_py, log_option):
    makefile(pytester.path / 'conftest.py', """
        def pytest_logger_config(logger_config):
            logger_config.add_loggers(['foo', 'bar'])
            logger_config.add_loggers(['baz'], file_level='error')
    """)

    opts = ('-s', log_option) if log_option else ('-s',)
    result = pytester.runpytest(*opts)
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
def test_logger_config_formatter(pytester, test_case_py, log_option):
    makefile(pytester.path / 'conftest.py', """
        import logging

        def pytest_logger_config(logger_config):
            logger_config.add_loggers(['foo', 'bar'])
            logger_config.add_loggers(['baz'], file_level='error')
            logger_config.set_formatter_class(logging.Formatter)
    """)

    opts = ('-s', log_option) if log_option else ('-s',)
    result = pytester.runpytest(*opts)
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
def test_logger_config_option_missing_without_hook(pytester, test_case_py, with_hook):
    makefile(pytester.path / 'conftest.py', """
        def pytest_addoption(parser):
            parser.addoption('--loggers')
    """ + ("""
        def pytest_logger_config(logger_config):
            logger_config.add_loggers(['foo', 'bar'], stdout_level='warning', file_level='info')
            logger_config.add_loggers(['baz'], stdout_level='error', file_level='warning')
    """ if with_hook else ""))

    result = pytester.runpytest('-s', '--loggers=foo')
    assert result.ret == (3 if with_hook else 0)

    if with_hook:
        result.stderr.fnmatch_lines([
            '*ArgumentError: argument --loggers: conflicting option string*: --loggers',
        ])


@pytest.mark.parametrize('stdout_hook', (False, True))
@pytest.mark.parametrize('config_hook', (False, True))
def test_error_both_hook_apis_used(pytester, test_case_py, stdout_hook, config_hook):
    makefile(pytester.path / 'conftest.py', ("""
        def pytest_logger_stdoutloggers(item):
            return ['foo']
    """ if stdout_hook else '') + ("""
        def pytest_logger_config(logger_config):
            logger_config.add_loggers(['foo'])
    """ if config_hook else ''))

    result = pytester.runpytest('-s')
    assert result.ret == (1 if (stdout_hook and config_hook) else 0)

    if stdout_hook and config_hook:
        result.stdout.fnmatch_lines([
            '*AssertionError: pytest_logger_config and pytest_logger_*loggers hooks used at the same time',
        ])


def test_help_prints(pytester, test_case_py):
    """
    Pytest doesn't evaluate group.addoption(..., type=...) option when run with --help option.
    This causes log option string to remain as unchecked string instead of a list in expected format.
    This happens regardless of --loggers option source (default, cmdline, etc.),

    To remedy this hack checking whether option has been parsed was made.
    This test ensures that it keeps working.
    """
    makefile(pytester.path / 'conftest.py', """
        def pytest_logger_config(logger_config):
            logger_config.add_loggers(['foo'])
            logger_config.set_log_option_default('foo')
    """)

    result = pytester.runpytest('-s', '--help')
    assert result.ret == 0


@pytest.mark.skip("Since pytest v3.3 progress percentage is being displayed by default during test execution. "
                  "It interferes with most of the old test cases that assert stdout/err so to not change them, we are "
                  "now forcing classic output with a set_classic_output auto-use fixture which overrides pytest's "
                  "console_output_style. We could have at least one test that proves the plugin can work in the new"
                  "default mode as well.")
def test_works_with_progress_percentage_prints():
    assert False


def test_collects_teardown_logs(pytester):
    makefile(pytester.path / 'conftest.py', """
        def pytest_logger_config(logger_config):
            logger_config.add_loggers(['foo'])
            logger_config.set_log_option_default('foo')
    """)

    makefile(pytester.path / 'test_bar.py', """
        import logging
        import pytest
        logger = logging.getLogger('foo')

        @pytest.fixture(autouse=True)
        def fixture_with_teardown_logging():
            logger.info('setup')
            yield
            logger.info('teardown')

        def test_bar():
            logger.info('test_bar')
    """)

    result = pytester.runpytest()
    assert result.ret == 0

    FileLineMatcher(basetemp(pytester) / 'logs/test_bar.py/test_bar/foo').fnmatch_lines([
        '* inf foo: setup',
        '* inf foo: test_bar',
        '* inf foo: teardown',
    ])
