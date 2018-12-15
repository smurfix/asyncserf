#!/usr/bin/env python
import os
import sys

exec(open("aioserf/_version.py", encoding="utf-8").read())

try:
    from setuptools import setup
    from setuptools.command.test import test as TestCommand

    class PyTest(TestCommand):
        def finalize_options(self):
            TestCommand.finalize_options(self)
            self.test_args = []
            self.test_suite = True

        def run_tests(self):
            import pytest
            errno = pytest.main(self.test_args)
            sys.exit(errno)
except ImportError:
    from distutils.core import setup
    PyTest = lambda x: x

try:
    long_description = open(os.path.join(os.path.dirname(__file__),
                                         'README.rst')).read()
except:
    long_description = None

test_requires = [
    'pytest >= 2.5.2',
    'pytest-cov >= 2.3',
]

setup(
    name='aioserf',
    version=__version__,
    description='Python client for the Serf orchestration tool',
    long_description=long_description,
    url='https://github.com/smurfix/aioserf',
    author='Matthias Urlichs',
    author_email='matthias@urlichs.de',
    maintainer='Matthias Urlichs',
    maintainer_email='matthias@urlichs.de',
    keywords=['Serf', 'orchestration', 'service discovery', 'anyio'],
    license='MIT',
    packages=['aioserf'],
    install_requires=['msgpack >= 0.5.0', 'anyio', 'outcome', 'async_generator'],
    tests_require=test_requires,
    cmdclass={'test': PyTest},
)
