# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Vangelis Koukis <vkoukis@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Setup logging: Formatters, handlers, and loggers"""

import logging
import logging.handlers


def _get_log_format(progname, debug=False, use_syslog=False):
    """Return an appropriate log format

    Different formats ensure entries are uniformly formatted and do not
    contain redundant information -- syslogd will log timestamps on its own.

    """
    if use_syslog:
        fmt = progname + "[%(process)d]: "
    else:
        fmt = "%(asctime)-15s " + progname + " pid=%(process)-6d "

    if debug:
        fmt += "%(module)s:%(lineno)s "

    fmt += "[%(levelname)s] %(message)s"

    return fmt


def SetupLogging(progname, debug=False, logfile=None, redirect_stderr_fd=False,
                 use_syslog=False, syslog_facility=None):
    """Configure the logging module.

    If debug is False (default) log messages of level INFO and higher,
    otherwise log all messages.

    If logfile is specified, use it to log messages of the appropriate level,
    according to the setting of debug.

    If redirect_stderr_fd is True, also redirect stderr (fd 2) to logfile.
    This ensures the log captures the stderr of child processes and the Python
    interpreter itself.

    Finally, if use_syslog is True, also log to syslog using the facility
    specified via syslog_facility, or LOG_USER if left unspecified.

    Note more logging points may be added in the future by using
    root_handler.add_handler() repeatedly.

    """

    # File and syslog formatters
    file_formatter = logging.Formatter(_get_log_format(progname, debug,
                                                       False))
    syslog_formatter = logging.Formatter(_get_log_format(progname, debug,
                                                         True))

    # Root logger
    root_logger = logging.getLogger("")
    root_logger.setLevel(logging.NOTSET)  # Process all log messages by default

    level = logging.NOTSET if debug else logging.INFO

    for handler in root_logger.handlers:
        handler.close()
        root_logger.removeHandler(handler)

    # Syslog handler
    if use_syslog:
        facility = (syslog_facility if syslog_facility is not None
                    else logging.handlers.SysLogHandler.LOG_USER)
        # We hardcode address `/dev/log' for now, i.e., deliver to local
        # syslogd.
        #
        # The local administrator can impose whatevery policy they wish
        # by configuring the local syslogd, e.g., to forward logs
        # to a remote syslog server.
        syslog_handler = logging.handlers.SysLogHandler(address="/dev/log",
                                                        facility=facility)
        syslog_handler.setFormatter(syslog_formatter)
        syslog_handler.setLevel(level)
        root_logger.addHandler(syslog_handler)

    # File handler
    if logfile is not None:
        logfile_handler = logging.FileHandler(logfile, "a")
        logfile_handler.setFormatter(file_formatter)
        logfile_handler.setLevel(level)
        root_logger.addHandler(logfile_handler)

    # Redirect standard error at the OS level, to catch all error output,
    # including that of child processes and the Python interpreter itself
    if redirect_stderr_fd:
        os.dup2(logfile_handler.stream.fileno(), 1)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
