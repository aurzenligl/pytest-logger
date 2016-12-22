Usage
===============================================================

.. currentmodule:: pytest_logger.plugin

By default pytest-logger does nothing in scope of logging.
It's only default action is to add new hooks and fixture.
Terminal output, logfiles together with their directory structure, symlink
appear only when explicitly requested by user via one of hooks or fixture.

Logging to stdout or files
---------------------------------------

Implement pytest-logger hooks in your `conftest.py`_ to direct logs to terminal or files.
You can make up your own cmdline arguments relevant to your test environment for convenience.

Terminal output mixes with normal pytest's output in graceful manner.
File output is stored in logs directory (see `logs dir layout`_ and `link to logs dir`_).

::

    import logging
    def pytest_logger_stdoutloggers(item):
        # handles foo logger at chosen level and bar at all levels
        return [('foo', logging.WARN), 'bar']

    def pytest_logger_fileloggers(item):
        # handles root logger
        return ['']

- see :py:meth:`LoggerHookspec.pytest_logger_stdoutloggers`
- see :py:meth:`LoggerHookspec.pytest_logger_fileloggers`

Things to note:

    - **stdout capturing:** in order to see logs printed on terminal in real time
      during test execution, you need to disable output capturing by ``-s`` switch.
    - **default root level:** by default root logger (and all its children)
      has warning level threshold set. This can filter logs regardless of handler levels
      user gives via hooks. Be sure to set root logger level as NOTSET if you
      don't want this to happen.
    - **no handlers warning:** if log wouldn't get filtered, but there are no handlers
      added to logger, `unwanted message`_ is printed. Add `NullHandler`_
      to such loggers.
    - **default logging config:** if root logger has no handlers, using module level
      logging functions will setup basic logging config. It makes no sense in combintion
      with this plugin. Be sure root logger has some handler (at least `NullHandler`_)
      or just don't use these functions.
    - **pytest-xdist:** stdout output is not printed to terminal in `pytest-xdist`_ runs.
      File output works as in single process mode.

.. _`logs dir layout`:

The logs directory layout
---------------------------------------

Directory with logfiles is named "logs" and located under test session's `basetemp`_ directory::

    tmp/
    └── pytest-of-aurzenligl
        ├── pytest-0
        │   └── logs
        │       (...)
        ├── pytest-1
        │   └── logs
        │       (...)
        └── pytest-2
            └── logs
                (...)

It has structure following pytest test item's `nodeid`_.

    - test directories are directories
    - test filenames are directories
    - test functions are directories (each parametrized testcase variant is distinct)
    - each registered logger is a file (root logger is called 'root')

::

    logs/
    ├── classtests
    │   └── test_y.py
    │       └── TestClass.test_class
    │           ├── daemon
    │           └── setup
    ├── parametrictests
    │   └── test_z.py
    │       ├── test_param-2-abc
    │       └── test_param-4.127-de
    │           └── setup
    └── test_p.py
        └── test_cat
            └── proc

.. _`link to logs dir`:

Link to logs directory
---------------------------------------

Implement link hook to have access to logfiles from place where you regularly run your tests.
Link is created in a race-safe manner, even if multiple pytest processes run tests simultaneously.

::

    # content of conftest.py
    import os
    def pytest_logger_logdirlink(config):
        return os.path.join(os.path.dirname(__file__), 'logs')

::

    $ ls -o
    total 80
    drwxr-xr-x  9 aurzenligl 4096 Dec 22 21:09 .
    drwxr-xr-x 28 aurzenligl 4096 Dec 14 23:33 ..
    -rwxr-xr-x  1 aurzenligl 3028 Dec 11 02:18 conftest.py
    lrwxrwxrwx  1 aurzenligl   39 Dec 22 21:09 logs -> /tmp/pytest-of-aurzenligl/pytest-2/logs
    -rwxr-xr-x  1 aurzenligl  817 Dec 11 02:13 test_x.py

- see :py:meth:`LoggerHookspec.pytest_logger_logdirlink`

The logdir fixture
---------------------------------------

Like pytest's `tmpdir`_ it's a `py.path.local`_ object which offers os.path methods.
Points to logs subdirectory related to particular testcase.
Directory is ensured to exist and custom log files can be written into it::

    def test_foo(logdir):
        logdir.join('myfile.txt').write('abc')

API reference
---------------------------------------

.. autoclass:: LoggerHookspec()
    :members: pytest_logger_stdoutloggers,
              pytest_logger_fileloggers,
              pytest_logger_logdirlink

.. _`conftest.py`: http://docs.pytest.org/en/latest/writing_plugins.html#conftest-py
.. _`unwanted message`: https://docs.python.org/2/howto/logging.html#what-happens-if-no-configuration-is-provided
.. _`NullHandler`: https://docs.python.org/2/library/logging.handlers.html#logging.NullHandler
.. _`pytest-xdist`: https://pypi.python.org/pypi/pytest-xdist
.. _`basetemp`: http://doc.pytest.org/en/latest/tmpdir.html#the-default-base-temporary-directory
.. _`nodeid`: http://docs.pytest.org/en/latest/writing_plugins.html#_pytest.main.Node.nodeid
.. _`tmpdir`: http://docs.pytest.org/en/latest/tmpdir.html#the-tmpdir-fixture
.. _`py.path.local`: http://py.rtfd.org/en/latest/path.html
