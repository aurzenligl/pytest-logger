Overview
===================================

Installation
--------------------

As simple as::

	$ [sudo] pip install pytest-logger

Project is hosted on github:

	https://github.com/aurzenligl/pytest-logger

Rationale
--------------------

I work with C++ application which logs copiously on its own and has multiple interfaces on which
interesting events occur. Getting all this information as separate files in directory tree
or filtered real-time logs proves to be invaluable in testing.

Unfortunately, contemporary state of pytest and plugins doesn't allow to do this out-of-the-box:

	- real-time output to terminal which doesn't mix with regular pytest output ('-v' or not)
	- possibility to enable and set levels on per logger basis
	- test session logs persistent in filesystem and partitioned in fine-grained manner
	  (per testcase and per logger)

Above problems require reacting on events such as session start, test start/teardown
and inspecting some data stored by framework, e.g. test locations/names. This requires
writing pytest plugin.

Plugin has a hook API, which means that if user doesn't implement hooks, nothing happens,
and if he does - any cmdline options and logging configuration logic may be envisioned.

Contributing
--------------------

Contibutions are welcome!

If you:

    - find a bug in plugin,
    - find important features missing,
    - want to propose a new feature,
    - or just like it,

please write to `github issues`_ or let me know `via email`_.

.. _`github issues`: https://github.com/aurzenligl/pytest-logger/issues
.. _`via email`: https://github.com/aurzenligl
