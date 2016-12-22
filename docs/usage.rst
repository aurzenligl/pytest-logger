Usage
===============================================================

.. currentmodule:: pytest_logger.plugin

Logging to files or stdout
---------------------------------------

Implement pytest-logger hooks in your conftest.py to direct logs to terminal or files::

    def pytest_logger_fileloggers(item):
        # handles root logger
    	return ['']

    import logging
    def pytest_logger_stdoutloggers(item):
    	# handles foo logger at chosen level
        return [('foo', logging.WARN)]

Hook API:

.. autoclass:: LoggerHookspec()
	:members: pytest_logger_stdoutloggers,
	          pytest_logger_fileloggers
