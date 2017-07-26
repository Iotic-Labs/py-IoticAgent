# Copyright 2016 Iotic Labs Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://github.com/Iotic-Labs/py-IoticAgent/blob/master/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=import-error,wrong-import-order

from __future__ import print_function

# Allow for environments without setuptools
try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages  # pylint: disable=ungrouped-imports

# For converting markdown README.md
try:
    from pypandoc import convert
except ImportError:
    READ_MD = lambda f: open(f, 'r').read()  # noqa: E731
    print('Warning: pypandoc module not found, will not convert Markdown to RST')
else:
    READ_MD = lambda f: convert(f, 'rst')  # noqa: E731


VERSION = '0.6.0'

setup(
    name='py-IoticAgent',
    version=VERSION,
    description='Agent for accessing Iotic Space',
    long_description=READ_MD('README.md'),
    author='Iotic Labs Ltd',
    author_email='info@iotic-labs.com',
    maintainer='Iotic Labs Ltd',
    maintainer_email='info@iotic-labs.com',
    url='https://github.com/Iotic-Labs/py-IoticAgent',
    license='Apache License 2.0',
    packages=find_packages('src', exclude=['tests']),
    package_dir={'': 'src'},
    install_requires=['py-ubjson>=0.8.5', 'rdflib>=4.2.1', 'enum34>=1.1.6'],
    zip_safe=True,
    keywords=['iotic', 'agent', 'labs', 'space', 'iot'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
