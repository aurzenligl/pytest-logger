import os
import sys
import re
import py
import pytest
import logging
import time
import datetime
import argparse
from builtins import object, int
from past.builtins import basestring


def pytest_addhooks(pluginmanager):
    pluginmanager.add_hookspecs(LoggerHookspec)


def _late_addoptions(parser, logcfg):
    """Add options to control logger"""
    parser.addini(
        name='logger_logsdir',
        help='base directory with log files for file loggers [basetemp]',
        default=None,
    )
    group = parser.getgroup('logger')
    group.addoption('--logger-logsdir',
                    help='pick you own logs directory instead of default '
                         'directory under session tmpdir')

    if logcfg._enabled:
        parser = _log_option_parser(logcfg._loggers)
        group.addoption('--loggers',
                        default=parser(logcfg._log_option_default),
                        type=parser,
                        metavar='LOGGER,LOGGER.LEVEL,...',
                        help='comma delimited list of loggers optionally suffixed with level '
                             'preceded by a dot. Levels can be lower or uppercase, or numeric. '
                             'For example: "logger1,logger2.info,logger3.FATAL,logger4.25"')


@pytest.hookimpl(trylast=True)
def pytest_load_initial_conftests(early_config, parser, args):
    logcfg = LoggerConfig()
    early_config.hook.pytest_logger_config(logger_config=logcfg)
    early_config.pluginmanager.register(EarlyLoggerPlugin(logcfg), '_early_logger')
    _late_addoptions(parser, logcfg)


def pytest_configure(config):
    early_logger = config.pluginmanager.getplugin('_early_logger')
    config.pluginmanager.register(LoggerPlugin(config, early_logger._logcfg), '_logger')


class EarlyLoggerPlugin(object):
    def __init__(self, logcfg):
        self._logcfg = logcfg


class LoggerPlugin(object):
    def __init__(self, config, logcfg):
        self._config = config
        self._logdirlinks = config.hook.pytest_logger_logdirlink(config=config)
        self._loggers = _loggers_from_logcfg(logcfg, config.getoption('loggers')) if logcfg._enabled else None
        self._formatter_class = logcfg._formatter_class or DefaultFormatter
        self._logsdir = None
        self._split_by_outcome_subdir = logcfg._split_by_outcome_subdir
        self._split_by_outcome_outcomes = logcfg._split_by_outcome_outcomes

    def logsdir(self):
        ldir = self._logsdir
        if ldir:
            return ldir
        logger_logsdir = self._config.getoption('logger_logsdir')
        if not logger_logsdir:
            logger_logsdir = self._config.getini('logger_logsdir')
        if not logger_logsdir:
            logger_logsdir = self._config.hook.pytest_logger_logsdir(config=self._config)
        if logger_logsdir:
            ldir = _make_logsdir_dir(logger_logsdir)
        else:
            ldir = _make_logsdir_tmpdir(self._config._tmpdirhandler)

        self._logsdir = ldir

        for link in self._logdirlinks:
            _refresh_link(str(ldir), link)

        return ldir

    def pytest_runtest_setup(self, item):
        loggers = _choose_loggers(self._loggers, _loggers_from_hooks(item))
        formatter = self._formatter_class()
        item._logger = state = LoggerState(item=item,
                                           stdoutloggers=loggers.stdout,
                                           fileloggers=loggers.file,
                                           formatter=formatter)
        state.on_setup()

    def pytest_runtest_teardown(self, item, nextitem):
        logger = getattr(item, '_logger', None)
        if logger:
            logger.on_teardown()

    @pytest.mark.hookwrapper
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        tr = outcome.get_result()
        logger = getattr(item, '_logger', None)
        if logger:
            if self._logsdir and self._split_by_outcome_subdir and tr.outcome in self._split_by_outcome_outcomes:
                split_by_outcome_logdir = self._logsdir.join(self._split_by_outcome_subdir, tr.outcome)
                nodeid = _sanitize_nodeid(item.nodeid)
                nodepath = os.path.dirname(nodeid)
                split_by_outcome_logdir.join(nodepath).ensure(dir=1)
                destdir_relpath = os.path.relpath(str(self._logsdir.join(nodeid)),
                                                  str(split_by_outcome_logdir.join(nodepath)))
                _refresh_link(destdir_relpath, str(split_by_outcome_logdir.join(nodeid)))
            if call.when == 'teardown':
                logger.on_makereport()


class LoggerState(object):
    def __init__(self, item, stdoutloggers, fileloggers, formatter):
        self._put_newlines = bool(item.config.option.capture == 'no' and stdoutloggers)
        self.handlers = _make_handlers(stdoutloggers, fileloggers, item, formatter)
        self.root_enabler = RootEnabler(bool(stdoutloggers and fileloggers))

    def put_newline(self):
        if self._put_newlines:
            sys.stdout.write('\n')

    def on_setup(self):
        self.put_newline()
        _enable(self.handlers)
        self.root_enabler.enable()

    def on_teardown(self):
        self.put_newline()

    def on_makereport(self):
        self.root_enabler.disable()
        _disable(self.handlers)


class RootEnabler(object):
    def __init__(self, enabled):
        self._enabled = enabled
        self._root_level = logging.root.level

    def enable(self):
        if self._enabled:
            self._root_level = logging.root.level
            logging.root.setLevel(logging.NOTSET)  # stops root logger from blocking logs

    def disable(self):
        if self._enabled:
            logging.root.setLevel(self._root_level)


class Loggers(object):
    def __init__(self, stdout, file_):
        self.stdout = stdout
        self.file = file_

    def __bool__(self):
        return bool(self.stdout) or bool(self.file)


class LoggerConfig(object):
    """Configuration of logging to stdout and filesystem."""

    def __init__(self):
        self._enabled = False
        self._loggers = []
        self._formatter_class = None
        self._log_option_default = ''
        self._split_by_outcome_subdir = None
        self._split_by_outcome_outcomes = []

    def add_loggers(self, loggers, stdout_level=logging.NOTSET, file_level=logging.NOTSET):
        """Adds loggers for stdout/filesystem handling.

        Stdout: loggers will log to stdout only when mentioned in `loggers` option. If they're
        mentioned without explicit level, `stdout_level` will be used.

        Filesystem: loggers will log to files at `file_level`.

        :arg loggers: List of logger names.

        :arg stdout_level: Default level at which stdout handlers will pass logs.
           By default: `logging.NOTSET`, which means: pass everything.

        :arg file_level: Level at which filesystem handlers will pass logs.
           By default: `logging.NOTSET`, which means: pass everything.
        """
        self._enabled = True
        self._loggers.append((loggers, _sanitize_level(stdout_level), _sanitize_level(file_level)))

    def set_formatter_class(self, formatter_class):
        """Sets the `logging.Formatter` class to be used by all loggers.

        :arg formatter_class: The `logging.Formatter` class
        """
        if isinstance(formatter_class, logging.Formatter):
            raise ValueError("Got a formatter instance instead of its class !")

        if not issubclass(formatter_class, logging.Formatter):
            raise ValueError("Formatter should be a class inheriting from logging.Formatter")
        self._formatter_class = formatter_class

    def set_log_option_default(self, value):
        """ Sets default value of `log` option."""
        self._log_option_default = value

    def split_by_outcome(self, outcomes=None, subdir='by_outcome'):
        """Makes a directory inside main logdir where logs are further split by test outcome

        :param outcomes: list of test outcomes to be handled (failed/passed/skipped)
        :param subdir: name for the subdirectory in main log directory
        """
        if outcomes is not None:
            allowed_outcomes = ['passed', 'failed', 'skipped']
            unexpected_outcomes = set(outcomes) - set(allowed_outcomes)
            if unexpected_outcomes:
                raise ValueError('got unexpected_outcomes: <' + str(list(unexpected_outcomes)) + '>')
            self._split_by_outcome_outcomes = outcomes
        else:
            self._split_by_outcome_outcomes = ['failed']

        self._split_by_outcome_subdir = subdir


class LoggerHookspec(object):
    def pytest_logger_config(self, logger_config):
        """ called before cmdline options parsing. Accepts terse configuration
        of both stdout and file logging, adds cmdline options to manipulate
        stdout logging. Cannot be used together with \\*loggers hooks.

        :arg logger_config: instance of :py:class:`LoggerConfig`, allows
           setting loggers for stdout and file handling and their levels.
        """

    def pytest_logger_stdoutloggers(self, item):
        """ called before testcase setup. If implemented, given loggers
        will emit their output to terminal output. Cannot be used together with
        logger_config hook.

        :arg item: test item for which handlers are to be setup.

        :return list: List should contain logger name strings
                      or tuples with logger name string and logging level.
        """

    def pytest_logger_fileloggers(self, item):
        """ called before testcase setup. If implemented, given loggers
        will emit their output to files within logs temporary directory.
        Cannot be used together with logger_config hook.

        :arg item: test item for which handlers are to be setup.

        :return list: List should contain logger name strings
                      or tuples with logger name string and logging level.
        """

    def pytest_logger_logdirlink(self, config):
        """ called after cmdline options parsing.
        If implemented, symlink to logs directory will be created.

        :arg config: pytest config object, holds e.g. options

        :return string: Absolute path of requested link to logs directory.
        """

    @pytest.hookspec(firstresult=True)
    def pytest_logger_logsdir(self, config):
        """ called after cmdline options parsing.
        If implemented, place logs into the location returned. This is similar
        to using --logger-logsdir or the logger_logsdir ini option, but will
        only be used if those are not.

        Additionally, if multiple implementations of this hook are found, only
        the first non-None value will be used.

        :arg config: pytest config object, holds e.g. options

        :return string: Absolute path of logs directory.
        """


class DefaultFormatter(logging.Formatter):
    short_level_names = {
        logging.FATAL: 'ftl',
        logging.ERROR: 'err',
        logging.WARN: 'wrn',
        logging.INFO: 'inf',
        logging.DEBUG: 'dbg',
    }

    format_string = '%(asctime)s %(levelshortname)s %(name)s: %(message)s'

    def __init__(self):
        logging.Formatter.__init__(self, DefaultFormatter.format_string)
        self._start = time.time()

    def formatTime(self, record, datefmt=None):
        ct = record.created - self._start
        dt = datetime.datetime.utcfromtimestamp(ct)
        return dt.strftime("%M:%S.%f")[:-3]  # omit useconds, leave mseconds

    def format(self, record):
        record.levelshortname = DefaultFormatter.short_level_names.get(record.levelno,
                                                                       'l%s' % record.levelno)
        return logging.Formatter.format(self, record)


@pytest.fixture
def logdir(request):
    return _make_logdir(request._pyfuncitem)


def _sanitize_nodeid(filename):
    filename = filename.replace('::()::', '/')
    filename = filename.replace('::', '/')
    filename = re.sub(r'\[(.+)\]', r'-\1', filename)
    return filename


def _sanitize_level(level, raises=True):
    if isinstance(level, basestring):
        try:
            return int(level)
        except ValueError:
            int_level = getattr(logging, level.upper(), None)
            if int_level is not None:
                return int_level
    elif isinstance(level, int):
        return level
    if raises:
        raise TypeError('bad logging level, expected int or string, got "%s"' % level)


def _refresh_link(source, link_name):
    try:
        os.unlink(link_name)
    except OSError:
        pass
    try:
        os.symlink(source, link_name)
    except (OSError, AttributeError, NotImplementedError):
        pass


def _make_logsdir_tmpdir(tmpdirhandler):
    logsdir = tmpdirhandler.getbasetemp()
    if logsdir.basename.startswith('popen-gw'):
        logsdir = logsdir.join('..')
    logsdir = logsdir.join('logs').ensure(dir=1)
    return logsdir


def _make_logsdir_dir(dstname, cleandir=True):
    logsdir = py.path.local(dstname)
    if cleandir:
        if logsdir.check():
            logsdir.remove()
        logsdir.mkdir()
    return logsdir


def _make_logdir(item):
    plugin = item.config.pluginmanager.getplugin('_logger')
    return plugin.logsdir().join(_sanitize_nodeid(item.nodeid)).ensure(dir=1)


def _enable(handlers):
    for hdlr in handlers:
        hdlr.logger.addHandler(hdlr)


def _disable(handlers):
    for hdlr in handlers:
        hdlr.logger.removeHandler(hdlr)
        hdlr.close()


def _log_option_parser(loggers):
    def parser(arg):
        def to_out(elem):
            def find_row(name):
                return next((row for row in loggers if name in row[0]), None)

            def bad_logger(name):
                names = [x for row in loggers for x in row[0]]
                pretty_names = '(' + ', '.join(names) + ')'
                raise argparse.ArgumentTypeError(
                    'wrong logger, expected %s, got "%s"' % (pretty_names, name))

            def bad_level(level):
                raise argparse.ArgumentTypeError(
                    'wrong level, expected (INFO, warn, 15, ...), got "%s"' % level)

            row = find_row(elem)
            if row:
                return elem, row[1]
            if '.' in elem:
                elem_name, elem_level = elem.rsplit('.', 1)
                row = find_row(elem_name)
                level = _sanitize_level(elem_level, raises=False)
                if row and level is not None:
                    return elem_name, level
                if row:
                    bad_level(elem_level)
                if level is not None:
                    bad_logger(elem_name)
            bad_logger(elem)
        return [to_out(x) for x in arg.split(',') if x]
    return parser


def _loggers_from_logcfg(logcfg, logopt):
    def to_stdout(loggers, opt):
        def one(loggers, one):
            if isinstance(one, basestring):
                return one, next(row for row in loggers if one in row[0])[1]
            else:
                return one
        return [one(loggers, x) for x in opt]

    def to_file(loggers):
        return [(name, row[2]) for row in loggers for name in row[0]]

    return Loggers(
        stdout=to_stdout(logcfg._loggers, logopt),
        file_=to_file(logcfg._loggers)
    )


def _loggers_from_hooks(item):
    def to_loggers(configs_lists):
        def to_logger_and_level(cfg):
            if isinstance(cfg, basestring):
                name, level = cfg, logging.NOTSET
            else:
                name, level = cfg
            return name, level
        return [to_logger_and_level(cfg) for configs in configs_lists for cfg in configs]
    return Loggers(
        stdout=to_loggers(item.config.hook.pytest_logger_stdoutloggers(item=item)),
        file_=to_loggers(item.config.hook.pytest_logger_fileloggers(item=item))
    )


def _choose_loggers(config_loggers, hook_loggers):
    assert (not config_loggers) or (not hook_loggers),\
        'pytest_logger_config and pytest_logger_*loggers hooks used at the same time'
    return config_loggers or hook_loggers


def _make_handlers(stdoutloggers, fileloggers, item, formatter):
    handlers = []
    if stdoutloggers:
        handlers += _make_stdout_handlers(stdoutloggers, formatter)
    if fileloggers:
        logdir = _make_logdir(item)
        handlers += _make_file_handlers(fileloggers, formatter, logdir)
    return handlers


def _make_stdout_handlers(loggers, fmt):
    def make_handler(logger_and_level, fmt):
        name, level = logger_and_level
        logger = logging.getLogger(name)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(fmt)
        handler.setLevel(level)
        handler.logger = logger
        return handler

    return [make_handler(lgr, fmt) for lgr in loggers]


def _make_file_handlers(loggers, fmt, logdir):
    def make_handler(logdir, logger_and_level, fmt):
        name, level = logger_and_level
        logger = logging.getLogger(name)
        name = name or 'logs'
        logfile = str(logdir.join(name))
        handler = logging.FileHandler(filename=logfile, mode='w', delay=True)
        handler.setFormatter(fmt)
        handler.setLevel(level)
        handler.logger = logger
        return handler

    return [make_handler(logdir, lgr, fmt) for lgr in loggers]
