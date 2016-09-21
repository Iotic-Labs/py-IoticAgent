# Copyright (c) 2016 Iotic Labs Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://github.com/Iotic-Labs/py-IoticAgent/blob/master/LICENSE
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Profiling agent scripts
-----------------------

To profile your script, first enable profiling for the main thread, e.g.:

    #!python
    from IoticAgent.Core.Profiler import profiled_thread

    @profiled_thread
    def main():
        # ...

    if __name__ == '__main__':
        main()

Now, to actually enabling profiling at runtime, use the `IOTICAGENT_PROFILE` environment variable:

    #!shell
    IOTICAGENT_PROFILE=1 python3 my_script.py

This will produce a set files in the current directory, each of the format
`profile_<process_id>.<thread_id_>.<thread_name>.log`.

To combine the results you can then use Python's [profile module](https://docs.python.org/3/library/profile.html). E.g.
if you define `print_stats.py` as:

    #!python
    from pstats import Stats
    from sys import argv
    # all command line arguments to script are interpreted as profile dumps
    stats = Stats(*argv[1:])
    stats.sort_stats('tottime')
    stats.print_stats(.2)

... you can then apply it to the collected stats:

    #!shell
    python3 print_stats.py profile_*.log
"""

from __future__ import unicode_literals

from cProfile import Profile
from os import environ, getpid
from threading import current_thread
import logging
logger = logging.getLogger(__name__)


def profiled_thread(func):
    """decorator to profile a thread or function. Profiling output will be written to
    'agent_profile_<process_id>.<thread_id_>.<thread_name>.log'"""

    def wrapper(*args, **kwargs):
        profile = Profile()
        profile.enable()
        try:
            func(*args, **kwargs)
        finally:
            profile.disable()
        try:
            thread = current_thread()
            profile.dump_stats('profile_%s.%s.%s.log' % (getpid(), thread.name, thread.ident))
        except:
            logger.exception('Failed to dump stats')

    return wrapper


if 'IOTICAGENT_PROFILE' in environ:
    logger.warning('Profiling enabled')
else:
    profiled_thread = lambda func: func  # noqa pylint: disable=invalid-name
