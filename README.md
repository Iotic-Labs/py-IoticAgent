# Overview
py-IoticAgent is the python-language client for  [Iotic Space](https://iotic-labs.com/whatisit/concept/).  It enables a suitably authorised and authenticated python program to connect to the space to share data - and to "find and bind" to receive data from other things.

It's designed to work in parallel with the UI at the [Iotic Labs Developer Portal](https://developer.iotic-labs.com/)

It provides to styles of interface:

- **Synchronous** - where your code blocks until the system has done what you asked before returning.
- **Asynchronous** - for the more advanced programmer, where you can issue commands and then wait on events until they complete.  Your code doesn't block.

## Documentation
Source-level documentation is part of the agent.  It requires [pdoc](https://pypi.python.org/pypi/pdoc) to generate.  Run the `make_docs.sh` script to generate it yourself, or it's available online [here](http://pythonhosted.org/py-IoticAgent/)

## System requirements
This agent requires Python v3.2+ (or 2.7.9+).

## Dependencies
The agent has one mandatory two optional dependencies

- **Mandatory** [py-ubjson](https://pypi.python.org/pypi/py-ubjson) to enable universal binary json
- **Optional** [py-lz4framed](https://pypi.python.org/pypi/py-lz4framed) for faster compression
- **Optional** [RDFlib](https://pypi.python.org/pypi/rdflib) to provide an RDF metadata handling api


## Installing
**Notes**

- All examples use Python 3 commands but these should also work using the Python v2 equivalents.
- PyPI releases are signed with the [Iotic Labs Software release signing key](https://iotic-labs.com/iotic-labs.com.asc)

## Using pip
```shell
pip3 install py-IoticAgent
# Optional: The agent can provide additional functionality if rdflib is available
pip3 install rdflib
```
**Notes**

- If you do not have Python development headers and a C toolchain installed, this might produce warnings which can be safely ignored.
- With certains versions of pip the dependency installation of py-ubjson can fail when using `-t` flag. (Symptom: py-IoticAgent is installed but py-ubsjon not. See also [this](https://github.com/pypa/pip/issues/3056) bug. In this case force non-extension installation as follows: `PYUBJSON_NO_EXTENSION=1 pip3 install py-IoticAgent`

## Using repository
```shell
git clone https://github.com/Iotic-Labs/py-IoticAgent.git
cd py-IoticAgent
mkdir 3rd
# Direct dependency of agent
pip3 install -t 3rd py-ubjson
# Optional: The agent can provide additional functionality if rdflib is available
pip3 install -t 3rd rdflib

export PYTHONPATH=`pwd`/3rd:`pwd`/src
```
