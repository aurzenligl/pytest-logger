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

Terminal output mixes with normal pytest's output in graceful manner.
File output is stored in logs directory (see `logs dir layout`_ and `link to logs dir`_).

There are two ways of doing this. :ref:`First one <High-level hook>` simpler to use,
:ref:`second one <Low-level hooks>` more flexible. They cannot be mixed in given test session.

Things to note:

    - **stdout capturing:** in order to see logs printed on terminal in real time
      during test execution, you need to disable output capturing by ``-s`` switch.
    - **default root level:** by default root logger (and implicitly all its children)
      has warning level threshold set. If any logger via any hook is configured,
      root logger level will be set to NOTSET to pass all logs according to levels set
      by pytest_logger user.
    - **no handlers warning:** if log wouldn't get filtered, but there are no handlers
      added to logger, `unwanted message`_ is printed. Add `NullHandler`_
      to such loggers.
    - **default logging config:** if root logger has no handlers, using module level
      logging functions will setup basic logging config. It makes no sense in combintion
      with this plugin. Be sure root logger has some handler (at least `NullHandler`_)
      or just don't use these functions.
    - **pytest-xdist:** stdout output is not printed to terminal in `pytest-xdist`_ runs.
      File output works as in single process mode.

.. _`High-level hook`:

High-level hook
^^^^^^^^^^^^^^^^^

::

    def pytest_logger_config(logger_config):
        # adds two loggers, which will:
        #   - log to filesystem at all levels
        #   - log to terminal with default WARN level if provided in --loggers option
        logger_config.add_loggers(['foo', 'bar'], stdout_level='warn')

        # default --loggers option is set to log foo at WARN level and bar at NOTSET
        logger_config.set_log_option_default('foo,bar.notset')

- command line option :ref:`--loggers <loggers option>` is added.
- see :py:meth:`LoggerHookspec.pytest_logger_config`
- note that :py:meth:`LoggerConfig.set_formatter_class` can be used to set a custom :py:class:`logging.Formatter` class

.. _`Low-level hooks`:

Low-level hooks
^^^^^^^^^^^^^^^^^

::

    import logging

    def pytest_logger_stdoutloggers(item):
        # handles foo logger at chosen level and bar at all levels
        return [('foo', logging.WARN), 'bar']

    def pytest_logger_fileloggers(item):
        # handles root logger
        return ['']

- no command line options are added
- see :py:meth:`LoggerHookspec.pytest_logger_stdoutloggers`
- see :py:meth:`LoggerHookspec.pytest_logger_fileloggers`

.. _`logs dir layout`:

The logs directory layout
---------------------------------------

Directory with logfiles is located
    - under test session's `basetemp`_ directory named "logs"

::

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

or
     - under predefined location, if `--logger-logsdir` option or `logger_logsdir` entry in configuration file defined

::

      <logger_logsdir>/
      └── (...)


It has structure following pytest test item's `nodeid`_.

    - test directories are directories
    - test filenames are directories
    - test classes are directories
    - test functions are directories (each parametrized testcase variant is distinct)
    - each registered logger is a file (root logger is called 'root')

::

    logs/
    ├── classtests
    │   └── test_y.py
    │       └── TestClass
    │           └── test_class
    │               ├── daemon
    │               └── setup
    ├── parametrictests
    │   └── test_z.py
    │       ├── test_param-2-abc
    │       └── test_param-4.127-de
    │           └── setup
    └── test_p.py
        └── test_cat
            └── proc


.. _`split logs by outcome`:

Split logs by outcome
---------------------------------------
It is possible to split the logs by test outcome. If chosen to do so (by calling below method):

::

    # content of conftest.py
    def pytest_logger_config(logger_config):
        logger_config.split_by_outcome()

Will result in below directory structure:

::

    logs/
    ├── classtests
    │   └── test_y.py
    │       └── TestClass
    │           ├── test_class
    │           │   ├── daemon
    │           │   └── setup
    │           └── test_that_failed_two
    │               └── somelogfile
    ├── by_outcome
    │   └── failed
    │       ├── classtests
    │       │   └── test_y.py
    │       │       └── TestClass
    │       │           └── test_that_failed_two -> ../../../../../../classtests/test_y.py/TestClass/test_that_failed_two
    │       └── test_p.py
    │           └── test_that_failed_one -> ../../../../test_p.py/test_that_failed_one
    └── test_p.py
        ├── test_cat
        │   └── proc
        └── test_that_failed_one
            └── somelog

You can change the default `by_outcome` dirname to something else, as well as add more "per-outcome" subdirectories by passing proper arguments to the `split_by_outcome` method.

See: :py:meth:`LoggerConfig.split_by_outcome`

.. _`link to logs dir`:

Set the log directory
---------------------------------------

Implement the logsdir hook to place logs in a different directory.

::

    # content of conftest.py
    import os
    def pytest_logger_logsdir(config):
        return os.path.join(os.path.dirname(__file__), 'logs')

- see :py:meth:`LoggerHookspec.pytest_logger_logsdir`

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
    :members: pytest_logger_config,
              pytest_logger_stdoutloggers,
              pytest_logger_fileloggers,
              pytest_logger_logdirlink

.. autoclass:: LoggerConfig()
    :members: add_loggers,
              set_log_option_default,
              set_formatter_class,
              split_by_outcome

.. _`conftest.py`: http://docs.pytest.org/en/latest/writing_plugins.html#conftest-py
.. _`unwanted message`: https://docs.python.org/2/howto/logging.html#what-happens-if-no-configuration-is-provided
.. _`NullHandler`: https://docs.python.org/2/library/logging.handlers.html#logging.NullHandler
.. _`pytest-xdist`: https://pypi.python.org/pypi/pytest-xdist
.. _`basetemp`: http://doc.pytest.org/en/latest/tmpdir.html#the-default-base-temporary-directory
.. _`nodeid`: http://docs.pytest.org/en/latest/writing_plugins.html#_pytest.main.Node.nodeid
.. _`tmpdir`: http://docs.pytest.org/en/latest/tmpdir.html#the-tmpdir-fixture
.. _`py.path.local`: http://py.rtfd.org/en/latest/path.html

Command line options
---------------------------------------

`--logger-logsdir=<logsdir>`
    where <logsdir> is root directory where log files are created

.. _`loggers option`:

`--loggers=<loggers>`
    where <loggers> are a comma delimited list of loggers optionally suffixed
    with level preceded by a dot. Levels can be lower or uppercase, or numeric.
    For example: "logger1,logger2.info,logger3.FATAL,logger4.25"

Configuration file parameters
---------------------------------------

`logger_logsdir=<logsdir>`
    where <logsdir> is root directory where log files are created
