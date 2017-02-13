# Overview

py-IoticAgent is the Python language client for [Iotic Space](https://iotic-labs.com/whatisit/concept/).  It enables a suitably authorised and authenticated Python program to connect to the space to share data - and to "find and bind" to receive data from other things.

It's designed to work in parallel with the UI at the [Iotic Labs Developer Portal](https://developer.iotic-labs.com/), so you can instantly see results from your agent code.

It provides two styles of interface:

- **Synchronous** - where your code blocks until the system has done what you asked before returning.
- **Asynchronous** - a more advanced style where your code doesn't block, since it issues commands and does other work before finally waiting on events that show the commands are complete.

# Getting started

Once the agent's installed, the [Agent documentation](http://pythonhosted.org/py-IoticAgent/) should get you started.

You will need a free [Iotic Space developer account](https://developer.iotic-labs.com/join/) to get credentials for the agent's .ini file.

## Building the docs

The online [Agent documentation](http://pythonhosted.org/py-IoticAgent/) can also be built locally if you prefer.

1. This requires [pdoc](https://pypi.python.org/pypi/pdoc) so run `pip install pdoc` if needed.
2. Run the `make_docs.sh` script to generate the docs.

## System requirements

This agent requires Python 3.2+ or 2.7.5+ (with ssl module capable of TLS v1.2).

## Security

Our PyPI releases are signed with the [Iotic Labs software release signing key](https://iotic-labs.com/iotic-labs.com.asc)

# Installing

- All examples use Python 3 commands but these should also work using the Python 2 equivalents.

## Quick install with pip

This works on most Linux and BSD systems (see below for macOS), installing from [PyPI](https://pypi.python.org/pypi/py-IoticAgent). You may be able to omit the `sudo` if you have a user-installed `pip`.

```shell
sudo pip3 install py-IoticAgent
```
For Python 2, use ``sudo pip`` or ``pip2``.

### Mac install

Whatever your preferred version of Python on macOS, you must install it with Homebrew so it can use a recent version of OpenSSL - no `sudo` should be needed:

```shell
brew install python3
pip3 install py-IoticAgent
```
- For Python 2, use `brew install python` and `pip`
- To install `brew`, see the [Homebrew site](http://brew.sh)

## Trying the agent

Now you can head to our [getting started doc](http://pythonhosted.org/py-IoticAgent/),
which provides a simple 3-line 'minimal script' to check everything's working.

## Possible issues

- If you do not have Python development headers and a C toolchain installed, this might produce warnings which can be safely ignored.
- With certain versions of pip, the installation of the py-ubjson dependency can fail when using `-t` flag. (Symptom: py-IoticAgent is installed but py-ubjson is not.)  See [this pip issue](https://github.com/pypa/pip/issues/3056). In this case, force non-extension installation: `PYUBJSON_NO_EXTENSION=1 pip3 install py-IoticAgent`
- On macOS, non-Homebrew Python setups may encounter this error from the agent: _Exception: At least SSL v1.0.1 required for TLS v1.2_

## Advanced: install from Git
This is an alternative to the pip install, if there's a specific change you need that's not in the pip version:

```shell
git clone https://github.com/Iotic-Labs/py-IoticAgent.git
cd py-IoticAgent
mkdir 3rd
# Direct dependencies of agent
pip3 install -t 3rd py-ubjson rdflib

export PYTHONPATH=`pwd`/3rd:`pwd`/src
```

### Dependencies
The agent has one mandatory and two optional dependencies - this only matters for the from-Git install:

- **Mandatory** [py-ubjson](https://pypi.python.org/pypi/py-ubjson) to enable universal binary JSON
- **Mandatory** [RDFlib](https://pypi.python.org/pypi/rdflib) to provide an RDF metadata handling API
- **Optional** [py-lz4framed](https://pypi.python.org/pypi/py-lz4framed) for faster compression
