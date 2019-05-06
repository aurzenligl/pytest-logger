#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import codecs
from setuptools import setup


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    return codecs.open(file_path, encoding='utf-8').read()


setup(
    name='pytest-logger',
    version='0.5.0',
    author='Krzysztof Laskowski',
    author_email='aurzenligl@gmail.com',
    maintainer='Krzysztof Laskowski',
    maintainer_email='aurzenligl@gmail.com',
    license='MIT',
    url='https://github.com/aurzenligl/pytest-logger',
    description='Plugin configuring handlers for loggers from Python logging module.',
    long_description=read('README.rst'),
    long_description_content_type='text/x-rst',
    packages=['pytest_logger'],
    install_requires=['pytest>=3.2', 'future'],
    keywords='py.test pytest logging',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Pytest',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: MIT License',
    ],
    entry_points={
        'pytest11': [
            'logger = pytest_logger.plugin',
        ],
    },
)
