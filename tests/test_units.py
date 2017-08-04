import logging
import pytest
import pytest_logger.plugin as plugin

def test_sanitize_nodeid():
    assert plugin._sanitize_nodeid('test_p.py::test_echo') == 'test_p.py/test_echo'
    assert plugin._sanitize_nodeid('classtests/test_y.py::TestClass::()::test_class') == 'classtests/test_y.py/TestClass.test_class'
    assert plugin._sanitize_nodeid('parametrictests/test_z.py::test_param[2-abc]') == 'parametrictests/test_z.py/test_param-2-abc'
    assert plugin._sanitize_nodeid('parametrictests/test_z.py::test_param[4.127-de]') == 'parametrictests/test_z.py/test_param-4.127-de'

def test_sanitize_level():
    assert plugin._sanitize_level(logging.INFO) == logging.INFO
    assert plugin._sanitize_level('warn') == logging.WARN
    assert plugin._sanitize_level('FATAL') == logging.FATAL

    with pytest.raises(AttributeError):
        plugin._sanitize_level('WARN ')
    with pytest.raises(AttributeError):
        plugin._sanitize_level('unknown')
    with pytest.raises(TypeError):
        plugin._sanitize_level(1.0)
