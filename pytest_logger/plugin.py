import os
import sys
import re
import py
import pytest
import logging
import time
import datetime

PY2 = sys.version_info[0] == 2

if PY2:
    string_type = basestring
else:
    string_type = str


def pytest_addoption(parser):
    """Add options to control logger"""
    parser.addini(
        name='logger_logsdir',
        help='base directory with log files for file loggers [basetemp]',
        default=None,
    )
    parser.getgroup('logger').addoption('--logger-logsdir', dest='logger_logsdir')


def pytest_configure(config):
    config.pluginmanager.register(LoggerPlugin(config), '_logger')


def pytest_addhooks(pluginmanager):
    pluginmanager.add_hookspecs(LoggerHookspec)


class LoggerPlugin(object):
    def __init__(self, config):
        self.config = config
        self.logdirlinks = config.hook.pytest_logger_logdirlink(config=config)
        self._logsdir = None

    def logsdir(self):
        ldir = self._logsdir
        if ldir:
            return ldir
        logger_logsdir = self.config.getoption('logger_logsdir')
        if not logger_logsdir:
            logger_logsdir = self.config.getini('logger_logsdir')
        if logger_logsdir:
            ldir = _make_logsdir_dir(logger_logsdir)
        else:
            ldir = _make_logsdir_tmpdir(self.config._tmpdirhandler)

        self._logsdir = ldir

        for link in self.logdirlinks:
            _refresh_link(str(ldir), link)

        return ldir

    def pytest_runtest_setup(self, item):
        def to_loggers(configs_lists):
            def to_logger_and_level(cfg):
                if isinstance(cfg, string_type):
                    name, level = cfg, logging.NOTSET
                else:
                    name, level = cfg
                logger = logging.getLogger(name)
                return logger, level
            return [to_logger_and_level(cfg) for configs in configs_lists for cfg in configs]

        stdoutloggers = to_loggers(item.config.hook.pytest_logger_stdoutloggers(item=item))
        fileloggers = to_loggers(item.config.hook.pytest_logger_fileloggers(item=item))
        item._logger = state = LoggerState(plugin=self,
                                           item=item,
                                           stdoutloggers=stdoutloggers,
                                           fileloggers=fileloggers)
        state.on_setup()

    def pytest_runtest_teardown(self, item, nextitem):
        logger = getattr(item, '_logger', None)
        if logger:
            logger.on_teardown()

    def pytest_runtest_makereport(self, item, call):
        logger = getattr(item, '_logger', None)
        if logger:
            if call.when == 'teardown':
                logger.on_makereport()


class LoggerState(object):
    def __init__(self, plugin, item, stdoutloggers, fileloggers):
        self._put_newlines = bool(item.config.option.capture == 'no' and stdoutloggers)
        self.handlers = _make_handlers(stdoutloggers, fileloggers, item)

    def put_newline(self):
        if self._put_newlines:
            sys.stdout.write('\n')

    def on_setup(self):
        self.put_newline()
        _enable(self.handlers)

    def on_teardown(self):
        self.put_newline()

    def on_makereport(self):
        _disable(self.handlers)


class LoggerHookspec(object):
    def pytest_logger_stdoutloggers(self, item):
        """ called before testcase setup. If implemented, given loggers
        will emit their output to terminal output.

        :arg item: test item for which handlers are to be setup.

        :return list: List should contain logger name strings
                      or tuples with logger name string and logging level.
        """

    def pytest_logger_fileloggers(self, item):
        """ called before testcase setup. If implemented, given loggers
        will emit their output to files within logs temporary directory.

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


class Formatter(logging.Formatter, object):
    short_level_names = {
        logging.FATAL: 'ftl',
        logging.ERROR: 'err',
        logging.WARN: 'wrn',
        logging.INFO: 'inf',
        logging.DEBUG: 'dbg',
    }

    def __init__(self, *args, **kwargs):
        super(Formatter, self).__init__(*args, **kwargs)
        self._start = time.time()

    def formatTime(self, record, datefmt=None):
        ct = record.created - self._start
        dt = datetime.datetime.utcfromtimestamp(ct)
        return dt.strftime("%M:%S.%f")[:-3]  # omit useconds, leave mseconds

    def format(self, record):
        record.levelshortname = Formatter.short_level_names.get(record.levelno,
                                                                'l%s' % record.levelno)
        return super(Formatter, self).format(record)


@pytest.fixture
def logdir(request):
    return _make_logdir(request._pyfuncitem)


def _sanitize(filename):
    filename = filename.replace('::()::', '.')
    filename = filename.replace('::', '/')
    filename = re.sub(r'\[(.+)\]', r'-\1', filename)
    return filename


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
    return plugin.logsdir().join(_sanitize(item.nodeid)).ensure(dir=1)


def _enable(handlers):
    for hdlr in handlers:
        hdlr.logger.addHandler(hdlr)


def _disable(handlers):
    for hdlr in handlers:
        hdlr.logger.removeHandler(hdlr)
        hdlr.close()


def _make_handlers(stdoutloggers, fileloggers, item):
    FORMAT = '%(asctime)s %(levelshortname)s %(name)s: %(message)s'
    fmt = Formatter(fmt=FORMAT)
    handlers = []
    if stdoutloggers:
        handlers += _make_stdout_handlers(stdoutloggers, fmt)
    if fileloggers:
        logdir = _make_logdir(item)
        handlers += _make_file_handlers(fileloggers, fmt, logdir)
    return handlers


def _make_stdout_handlers(loggers, fmt):
    def make_handler(logger_and_level, fmt):
        logger, level = logger_and_level
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(fmt)
        handler.setLevel(level)
        handler.logger = logger
        return handler

    return [make_handler(lgr, fmt) for lgr in loggers]


def _make_file_handlers(loggers, fmt, logdir):
    def make_handler(logdir, logger_and_level, fmt):
        logger, level = logger_and_level
        name = logger.name == 'root' and 'logs' or logger.name
        logfile = str(logdir.join(name))
        handler = logging.FileHandler(filename=logfile, mode='w', delay=True)
        handler.setFormatter(fmt)
        handler.setLevel(level)
        handler.logger = logger
        return handler

    return [make_handler(logdir, lgr, fmt) for lgr in loggers]
