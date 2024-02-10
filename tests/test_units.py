import logging
import argparse
import pytest
import pytest_logger.plugin as plugin


def test_sanitize_nodeid():
    assert plugin._sanitize_nodeid('test_p.py::test_echo') == 'test_p.py/test_echo'
    assert plugin._sanitize_nodeid('classtests/test_y.py::TestClass::()::test_class') == \
        'classtests/test_y.py/TestClass/test_class'
    assert plugin._sanitize_nodeid('parametrictests/test_z.py::test_param[2-abc]') == \
        'parametrictests/test_z.py/test_param-2-abc'
    assert plugin._sanitize_nodeid('parametrictests/test_z.py::test_param[4.127-de]') == \
        'parametrictests/test_z.py/test_param-4.127-de'
    assert plugin._sanitize_nodeid('parametrictests/test_z.py::test_param[x-a/b]') == \
        'parametrictests/test_z.py/test_param-x-a-b'
    assert plugin._sanitize_nodeid('parametrictests/test_z.py::test_param[y-/c/d]') == \
        'parametrictests/test_z.py/test_param-y-c-d'
    assert plugin._sanitize_nodeid('parametrictests/test_z.py::test_param[z-/e-1/f-1]') == \
        'parametrictests/test_z.py/test_param-z-e-1-f-1'


def test_sanitize_level():
    assert plugin._sanitize_level(logging.INFO) == logging.INFO
    assert plugin._sanitize_level('15') == 15
    assert plugin._sanitize_level('warn') == logging.WARN
    assert plugin._sanitize_level('FATAL') == logging.FATAL

    with pytest.raises(TypeError):
        plugin._sanitize_level('WARN ')
    with pytest.raises(TypeError):
        plugin._sanitize_level('unknown')
    with pytest.raises(TypeError):
        plugin._sanitize_level(1.0)

    assert plugin._sanitize_level('WARN ', raises=False) is None


def test_log_option_parser():
    loggers = [
        (['a', 'b', 'c'], 20, 10),
        (['d'], 30, 15),
        (['e', 'f.g.h'], 31, 16),
    ]

    assert plugin._log_option_parser([])('') == []
    assert plugin._log_option_parser(loggers)('') == []

    assert plugin._log_option_parser(loggers)('a') == [('a', 20)]
    assert plugin._log_option_parser(loggers)('a.info') == [('a', logging.INFO)]
    assert plugin._log_option_parser(loggers)('a.19') == [('a', 19)]
    assert plugin._log_option_parser(loggers)('f.g.h') == [('f.g.h', 31)]
    assert plugin._log_option_parser(loggers)('f.g.h.INFO') == [('f.g.h', logging.INFO)]
    assert plugin._log_option_parser(loggers)('a,b') == [('a', 20), ('b', 20)]
    assert plugin._log_option_parser(loggers)('a,d.19,e.info') == [('a', 20), ('d', 19), ('e', logging.INFO)]

    with pytest.raises(argparse.ArgumentTypeError) as e:
        plugin._log_option_parser(loggers)('a.unknown')
    assert str(e.value) == 'wrong level, expected (INFO, warn, 15, ...), got "unknown"'
    with pytest.raises(argparse.ArgumentTypeError) as e:
        plugin._log_option_parser(loggers)('alien.info')
    assert str(e.value) == 'wrong logger, expected (a, b, c, d, e, f.g.h), got "alien"'
    with pytest.raises(argparse.ArgumentTypeError) as e:
        plugin._log_option_parser(loggers)('alien.unknown')
    assert str(e.value) == 'wrong logger, expected (a, b, c, d, e, f.g.h), got "alien.unknown"'


def test_set_formatter_class():
    logcfg = plugin.LoggerConfig()

    logcfg.set_formatter_class(logging.Formatter)
    logcfg.set_formatter_class(plugin.DefaultFormatter)

    with pytest.raises(ValueError) as e:
        logcfg.set_formatter_class(plugin.DefaultFormatter())
    assert str(e.value) == 'Got a formatter instance instead of its class !'
    with pytest.raises(ValueError) as e:
        logcfg.set_formatter_class(plugin.LoggerState)
    assert str(e.value) == 'Formatter should be a class inheriting from logging.Formatter'
    with pytest.raises(TypeError) as e:
        logcfg.set_formatter_class(10)
    assert str(e.value).startswith('issubclass() arg 1 must be a class')


def test_loggers_from_logcfg_empty():
    logcfg = plugin.LoggerConfig()

    loggers = plugin._loggers_from_logcfg(logcfg, [])
    assert loggers.stdout == []
    assert loggers.file == []
    assert not loggers


def test_loggers_from_logcfg():
    logcfg = plugin.LoggerConfig()
    logcfg.add_loggers(['a', 'b', 'c'], stdout_level=logging.ERROR, file_level='warn')
    logcfg.add_loggers(['d'], stdout_level='10')

    log_option = [('b', logging.FATAL), 'd']

    loggers = plugin._loggers_from_logcfg(logcfg, log_option)
    assert loggers.stdout == [('b', logging.FATAL), ('d', 10)]
    assert loggers.file == [('a', logging.WARN), ('b', logging.WARN), ('c', logging.WARN), ('d', 0)]
    assert loggers


def test_split_by_outcome_wrong_config():
    logcfg = plugin.LoggerConfig()
    with pytest.raises(ValueError, match="got unexpected_outcomes: <\\['sthelese'\\]>"):
        logcfg.split_by_outcome(outcomes=['failed', 'sthelese'])
