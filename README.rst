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
.. image:: https://travis-ci.org/aurzenligl/pytest-logger.svg?branch=master
    :target: https://travis-ci.org/aurzenligl/pytest-logger
    :alt: Travis-CI Build Status
.. image:: https://ci.appveyor.com/api/projects/status/1h4cy8tk220pn03o?svg=true
    :target: https://ci.appveyor.com/project/aurzenligl/pytest-logger
    :alt: AppVeyor-CI Build Status

Pytest-logger is a pytest plugin configuring handlers for loggers from Python logging module.

You can install pytest-logger via ``pip`` from ``PyPI``::

    $ [sudo] pip install pytest-logger

Plugin puts logs on per-logger basis to:

- standard output,
- files within log-specific directory under pytest's ``tmpdir_factory`` session directory.

You can setup plugin using hooks::

    #conftest.py
    import os

    def pytest_logger_stdoutloggers(item):
        return ['foo', 'bar']

    def pytest_logger_fileloggers(item):
        return ['foo', 'bar']

    def pytest_logger_logdirlink(config):
        return os.path.join(os.path.dirname(__file__), 'mylogs')

have logging tests or libraries (including fixtures)::

    #test_something.py
    import pytest
    import logging

    foo = logging.getLogger('foo')
    foo.setLevel(logging.INFO)

    bar = logging.getLogger('bar')

    @pytest.yield_fixture(scope='session')
    def session_thing():
        foo.info('constructing session thing')
        yield
        foo.info('destroying session thing')

    @pytest.yield_fixture
    def testcase_thing():
        foo.info('constructing testcase thing')
        yield
        foo.info('destroying testcase thing')

    def test_one(session_thing, testcase_thing):
        foo.info('one executes')
        bar.warning('this test does nothing aside from logging')

    def test_two(session_thing, testcase_thing):
        foo.info('two executes')
        bar.warning('neither does this')

and expect output in terminal (if not captured)::

    $ py.test -s -v
    (...)
    test_something.py::test_one
    00:00.001 inf foo: constructing session thing
    00:00.001 inf foo: constructing testcase thing
    00:00.002 inf foo: one executes
    00:00.002 wrn bar: this test does nothing aside from logging
    PASSED
    00:00.002 inf foo: destroying testcase thing

    test_something.py::test_two
    00:00.000 inf foo: constructing testcase thing
    00:00.000 inf foo: two executes
    00:00.000 wrn bar: neither does this
    PASSED
    00:00.001 inf foo: destroying testcase thing
    00:00.001 inf foo: destroying session thing
    (...)

and - the same - in filesystem::

    $ file mylogs
    mylogs: symbolic link to `/tmp/pytest-of-aurzenligl/pytest-48/logs'

    $ tree mylogs
    mylogs
    `-- test_something.py
        |-- test_one
        |   |-- bar
        |   `-- foo
        `-- test_two
            |-- bar
            `-- foo

Distributed under the terms of the ``MIT`` license, pytest-logger is free and open source software.
