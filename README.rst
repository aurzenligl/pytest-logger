.. image:: https://img.shields.io/pypi/v/pytest-logger.svg
    :target: https://pypi.python.org/pypi/pytest-logger
    :alt: Pypi Package Version
.. image:: https://img.shields.io/pypi/pyversions/pytest-logger.svg
    :target: https://pypi.python.org/pypi/pytest-logger
    :alt: Supported Python Versions
.. image:: https://readthedocs.org/projects/pytest-logger/badge
    :target: http://pytest-logger.readthedocs.io/en/latest
    :alt: Documentation Status
.. image:: https://coveralls.io/repos/github/aurzenligl/pytest-logger/badge.svg?branch=master
    :target: https://coveralls.io/github/aurzenligl/pytest-logger?branch=master
    :alt: Coverage Status
.. image:: https://github.com/aurzenligl/pytest-logger/workflows/test/badge.svg
    :target: https://github.com/aurzenligl/pytest-logger/actions?query=workflow%3Atest
.. image:: https://ci.appveyor.com/api/projects/status/1h4cy8tk220pn03o?svg=true
    :target: https://ci.appveyor.com/project/aurzenligl/pytest-logger
    :alt: AppVeyor-CI Build Status

Pytest-logger is a pytest plugin configuring handlers for loggers from Python logging module.

You can install pytest-logger via ``pip`` from ``PyPI``::

    $ [sudo] pip install pytest-logger

Plugin puts logs on per-logger basis to:

- standard output,
- files within log-specific directory under pytest's ``tmpdir_factory`` session directory.

You can setup plugin using hook::

    #conftest.py
    import os

    def pytest_logger_config(logger_config):
        logger_config.add_loggers(['foo', 'bar', 'baz'], stdout_level='info')
        logger_config.set_log_option_default('foo,bar')

    def pytest_logger_logdirlink(config):
        return os.path.join(os.path.dirname(__file__), 'mylogs')

have logging tests or libraries (including fixtures)::

    #test_something.py
    import pytest
    import logging

    foo = logging.getLogger('foo')
    bar = logging.getLogger('bar')
    baz = logging.getLogger('baz')

    @pytest.yield_fixture(scope='session')
    def session_thing():
        foo.debug('constructing session thing')
        yield
        foo.debug('destroying session thing')

    @pytest.yield_fixture
    def testcase_thing():
        foo.debug('constructing testcase thing')
        yield
        foo.debug('destroying testcase thing')

    def test_one(session_thing, testcase_thing):
        foo.info('one executes')
        bar.warning('this test does nothing aside from logging')
        baz.info('extra log, rarely read')

    def test_two(session_thing, testcase_thing):
        foo.info('two executes')
        bar.warning('neither does this')
        baz.info('extra log, not enabled by default')

and expect output in terminal (if not captured)::

    $ py.test -s -v
    (...)
    test_something.py::test_one
    00:00.002 inf foo: one executes
    00:00.002 wrn bar: this test does nothing aside from logging
    PASSED

    test_something.py::test_two
    00:00.000 inf foo: two executes
    00:00.000 wrn bar: neither does this
    PASSED

being able to change this output by cmdline option::

    $ pytest -s -v --log foo.debug,baz
    (...)
    test_something.py::test_one
    00:00.002 dbg foo: constructing session thing
    00:00.002 dbg foo: constructing testcase thing
    00:00.002 inf foo: one executes
    00:00.003 inf baz: extra log, rarely read
    PASSED

    test_something.py::test_two
    00:00.000 dbg foo: constructing testcase thing
    00:00.000 inf foo: two executes
    00:00.001 inf baz: extra log, not enabled by default
    PASSED

and - the same - in filesystem::

    $ file mylogs
    mylogs: symbolic link to `/tmp/pytest-of-aurzenligl/pytest-48/logs'

    $ tree mylogs
    mylogs
    `-- test_something.py
        |-- test_one
        |   |-- bar
        |   |-- baz
        |   `-- foo
        `-- test_two
            |-- bar
            |-- baz
            `-- foo

Distributed under the terms of the ``MIT`` license, pytest-logger is free and open source software.
