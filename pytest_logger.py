import os
import sys
import re
import pytest
import logging
import time
import datetime
from contextlib import contextmanager

def pytest_addoption(parser):
    group = parser.getgroup("logger", "logging")
    group.addoption('--logdirflat', default=False, action='store_true',
                     help='puts all logs in single file.')

def pytest_configure(config):
    config.pluginmanager.register(LoggerPlugin(config), '_logger')

def pytest_addhooks(pluginmanager):
    pluginmanager.add_hookspecs(LoggerHookspec)

class LoggerPlugin(object):
    def __init__(self, config):
        self.config = config
        self.logdirlinks = config.hook.pytest_logger_logdirlink(config=config)
        self.logdirflat = config.getoption('logdirflat')
        self._logsdir = None

    def logsdir(self):
        ldir = self._logsdir
        if ldir:
            return ldir
        ldir = self._logsdir = _make_logsdir(self.config._tmpdirhandler, self.logdirlinks)
        return ldir

    def pytest_runtest_setup(self, item):
        def to_loggers(names_list):
            return [logging.getLogger(name) for names in names_list for name in names]

        stdoutloggers = to_loggers(item.config.hook.pytest_logger_stdoutloggers(item=item))
        fileloggers = to_loggers(item.config.hook.pytest_logger_fileloggers(item=item))
        item._logger = state = LoggerState(plugin=self,
                                           item=item,
                                           stdoutloggers=stdoutloggers,
                                           fileloggers=fileloggers)
        state.on_setup()

    def pytest_runtest_teardown(self, item, nextitem):
        item._logger.on_teardown()

    def pytest_runtest_makereport(self, item, call):
        if call.when == 'teardown':
            item._logger.on_makereport()

class LoggerState(object):
    def __init__(self, plugin, item, stdoutloggers, fileloggers):
        self._put_newlines = bool(stdoutloggers)
        self.handlers = _make_handlers(stdoutloggers, fileloggers, item)

    def put_newline(self):
        if self._put_newlines:
            if type(sys.stdout) == file and sys.stdout.name == '<stdout>':
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
        """ called before testcase setup, returns list of logger names """

    def pytest_logger_fileloggers(self, item):
        """ called before testcase setup, returns list of logger names """

    def pytest_logger_logdirlink(self, config):
        """ called after cmdline options parsing, returns location of link to logs dir """

class Formatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        super(Formatter, self).__init__(*args, **kwargs)
        self._start = time.time()
    def formatTime(self, record, datefmt=None):
        ct = record.created - self._start
        dt = datetime.datetime.utcfromtimestamp(ct)
        return dt.strftime("%M:%S.%f")[:-3]  # omit useconds, leave mseconds

@pytest.fixture
def logdir(request):
    return _make_logdir(request._pyfuncitem)

def _sanitize(filename):
    filename = filename.replace('::()::', '-')
    filename = filename.replace('::', '-')
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

def _make_logsdir(tmpdirhandler, logdirlinks):
    logsdir = tmpdirhandler.getbasetemp()
    if logsdir.basename.startswith('popen-gw'):
        logsdir = logsdir.join('..')
    logsdir = logsdir.join('logs').ensure(dir=1)
    for link in logdirlinks:
        _refresh_link(str(logsdir), link)
    return logsdir

def _make_logdir(item):
    plugin = item.config.pluginmanager.getplugin('_logger')
    return plugin.logsdir().join(_sanitize(item.nodeid)).ensure(dir=1)

def _enable(handlers):
    for hdlr in handlers:
        for lgr in hdlr.loggers:
            lgr.addHandler(hdlr)

def _disable(handlers):
    for hdlr in handlers:
        for lgr in hdlr.loggers:
            lgr.removeHandler(hdlr)

def _make_handlers(stdoutloggers, fileloggers, item):
    FORMAT = '%(asctime)s %(name)s: %(message)s'
    fmt = Formatter(fmt=FORMAT)
    handlers = []
    if stdoutloggers:
        handlers += [_make_stdout_handler(stdoutloggers, fmt)]
    if fileloggers:
        logdir = _make_logdir(item)
        logdirflat = item.config.pluginmanager.getplugin('_logger').logdirflat
        handlers += _make_file_handlers(fileloggers, fmt, logdir, logdirflat)
    return handlers

def _make_stdout_handler(loggers, fmt):
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(fmt)
    handler.loggers = loggers
    return handler

def _make_file_handlers(loggers, fmt, logdir, logdirflat):
    def make_handler(logdir, basename, loggers, fmt):
        logfile = str(logdir.join(basename))
        handler = logging.FileHandler(filename=logfile, mode='w', delay=True)
        handler.setFormatter(fmt)
        handler.loggers = loggers
        return handler

    if logdirflat:
        return [make_handler(logdir, 'logs', loggers, fmt)]
    else:
        return [make_handler(logdir, lgr.name, [lgr], fmt) for lgr in loggers]
