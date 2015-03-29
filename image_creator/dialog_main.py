#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2015 GRNET S.A.
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

"""This module is the entry point for the dialog-based version of the
snf-image-creator program. The main function will create a dialog where the
user is asked if he wants to use the program in expert or wizard mode.
"""

import dialog
import sys
import os
import signal
import argparse
import types
import time
import termios
import traceback
import tempfile
import logging

from image_creator import __version__ as version
from image_creator import constants
from image_creator.log import SetupLogging
from image_creator.util import FatalError, ensure_root
from image_creator.output.cli import SimpleOutput
from image_creator.output.dialog import GaugeOutput
from image_creator.output.composite import CompositeOutput
from image_creator.output.syslog import SyslogOutput
from image_creator.disk import Disk
from image_creator.dialog_wizard import start_wizard
from image_creator.dialog_menu import main_menu
from image_creator.dialog_util import WIDTH, confirm_exit, Reset, \
    update_background_title, select_file

PROGNAME = os.path.basename(sys.argv[0])

log = logging.getLogger(__name__)


def create_image(d, medium, out, tmp, snapshot):
    """Create an image out of `medium'"""
    d.setBackgroundTitle('snf-image-creator')

    gauge = GaugeOutput(d, "Initialization", "Initializing...")
    out.append(gauge)
    disk = Disk(medium, out, tmp)

    def signal_handler(signum, frame):
        gauge.cleanup()
        disk.cleanup()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    try:

        device = disk.file if not snapshot else disk.snapshot()

        image = disk.get_image(device)

        gauge.cleanup()
        out.remove(gauge)

        # Make sure the signal handler does not call gauge.cleanup again
        def dummy(self):
            pass
        gauge.cleanup = type(GaugeOutput.cleanup)(dummy, gauge, GaugeOutput)

        session = {"dialog": d,
                   "disk": disk,
                   "image": image}

        if image.is_unsupported():

            session['excluded_tasks'] = [-1]
            session['task_metadata'] = ["EXCLUDE_ALL_TASKS"]

            msg = "The system on the input medium is not supported." \
                "\n\nReason: %s\n\n" \
                "We highly recommend not to create an image out of this, " \
                "since the image won't be cleaned up and you will not be " \
                "able to configure it during the deployment. Press <YES> if " \
                "you still want to continue with the image creation process." \
                % image._unsupported

            if not d.yesno(msg, width=WIDTH, defaultno=1, height=12):
                main_menu(session)

            d.infobox("Thank you for using snf-image-creator. Bye", width=53)
            return 0

        msg = "snf-image-creator detected a %s system on the input medium. " \
              "Would you like to run a wizard to assist you through the " \
              "image creation process?\n\nChoose <Wizard> to run the wizard," \
              " <Expert> to run snf-image-creator in expert mode or press " \
              "ESC to quit the program." \
              % (image.ostype.capitalize() if image.ostype == image.distro or
                 image.distro == "unknown" else "%s (%s)" %
                 (image.ostype.capitalize(), image.distro.capitalize()))

        update_background_title(session)

        while True:
            code = d.yesno(msg, width=WIDTH, height=12, yes_label="Wizard",
                           no_label="Expert")
            if code == d.DIALOG_OK:
                if start_wizard(session):
                    break
            elif code == d.DIALOG_CANCEL:
                main_menu(session)
                break

            if confirm_exit(d):
                break

        d.infobox("Thank you for using snf-image-creator. Bye", width=53)
    finally:
        disk.cleanup()

    return 0


def _dialog_form(self, text, height=20, width=60, form_height=15, fields=[],
                 **kwargs):
    """Display a form box.

    fields is in the form: [(label1, item1, item_length1), ...]
    """

    cmd = ["--form", text, str(height), str(width), str(form_height)]

    label_len = 0
    for field in fields:
        if len(field[0]) > label_len:
            label_len = len(field[0])

    input_len = width - label_len - 1

    line = 1
    for field in fields:
        label = field[0]
        item = field[1]
        item_len = field[2]
        cmd.extend((label, str(line), str(1), item, str(line),
                    str(label_len + 1), str(input_len), str(item_len)))
        line += 1

    code, output = self._perform(*(cmd,), **kwargs)

    if not output:
        return (code, [])

    return (code, output.splitlines())


def dialog_main(medium, **kwargs):
    """Main function for the dialog-based version of the program"""

    tmpdir = kwargs['tmpdir'] if 'tmpdir' in kwargs else None
    snapshot = kwargs['snapshot'] if 'snapshot' in kwargs else True
    syslog = kwargs['syslog'] if 'syslog' in kwargs else False

    # In openSUSE dialog is buggy under xterm
    if os.environ['TERM'] == 'xterm':
        os.environ['TERM'] = 'linux'

    d = dialog.Dialog(dialog="dialog")

    # Add extra button in dialog library
    dialog._common_args_syntax["extra_button"] = \
        lambda enable: dialog._simple_option("--extra-button", enable)
    dialog._common_args_syntax["extra_label"] = \
        lambda string: ("--extra-label", string)

    # Allow yes-no label overwriting
    dialog._common_args_syntax["yes_label"] = \
        lambda string: ("--yes-label", string)
    dialog._common_args_syntax["no_label"] = \
        lambda string: ("--no-label", string)

    # Add exit label overwriting
    dialog._common_args_syntax["exit_label"] = \
        lambda string: ("--exit-label", string)

    # Monkey-patch pythondialog to include support for form dialog boxes
    if not hasattr(dialog, 'form'):
        d.form = types.MethodType(_dialog_form, d)

    d.setBackgroundTitle('snf-image-creator')

    # Pick input medium
    while True:
        medium = select_file(d, init=medium, ftype="br", bundle_host=True,
                            title="Please select an input medium.")
        if medium is None:
            if confirm_exit(
                    d, "You canceled the medium selection dialog box."):
                return 0
            continue
        break

    # FIXME: It does not make sense to pass both the dialog instance
    # explicitly, and Output instances separately. The called function
    # shouldn't have to know that it is using a dialog instance, or call
    # pythondialog-specific methods, but use the Output instance via a
    # defined interface.

    # This is an ugly workaround, until the separation of logging and Output
    # frontends is complete: Just make logging through Output a no-op for now,
    # by passing an empty list.
    logs = []
    try:
        while 1:
            try:
                out = CompositeOutput(logs)
                ret = create_image(d, medium, out, tmpdir, snapshot)
                break
            except Reset:
                log.info("Resetting everything ...")
    except FatalError as error:
        log.error("Fatal: " + str(error))
        msg = "A fatal error has occured: " + str(error)
        d.infobox(msg, width=WIDTH, title="Fatal Error")
        return 1

    return ret


def main():
    """Entry Point"""
    d = ("Create a cloud Image from the specified INPUT_MEDIUM."
         " INPUT_MEDIUM must be the hard disk of an existing OS deployment"
         " to be used as the template for Image creation. Supported formats"
         " include raw block devices, all disk image file formats supported"
         " by QEMU (e.g., QCOW2, VMDK, VDI, VHD), or the filesystem of the"
         " host itself. The resulting Image is meant to be used with Synnefo"
         " and other IaaS cloud platforms. Note this program works on a"
         " snapshot of INPUT_MEDIUM, and will not modify its contents.")
    e = ("%(prog)s requires root privileges.")

    parser = argparse.ArgumentParser(description=d, epilog=e)

    parser.add_argument("--tmpdir", metavar="TMPDIR", type=str, dest="tmpdir",
                        default=None,
                        help=("Create large temporary files under TMPDIR."
                              " Default is to use a randomly-named temporary"
                              " directory under /var/tmp or /tmp."))
    parser.add_argument("-l", "--logfile", metavar="LOGFILE", type=str,
                        dest="logfile", default=constants.DEFAULT_LOGFILE,
                        help=("Log all messages to LOGFILE."
                              " Default: %(default)s"))
    parser.add_argument("--syslog", dest="syslog", default=False,
                        action="store_true", help="Also log to syslog")
    parser.add_argument("-v", "--verbose", dest="verbose", default=False,
                        action="store_true",
                        help="Be verbose, log everything to ease debugging")
    parser.add_argument("--no-snapshot", dest="snapshot", default=True,
                        action="store_false",
                        help=("Do not work on a snapshot, but modify the input"
                              " medium directly instead. DO NOT USE THIS"
                              " OPTION UNLESS YOU REALLY KNOW WHAT YOU ARE"
                             " DOING. THIS WILL ALTER THE ORIGINAL MEDIUM!"))
    parser.add_argument("-V", "--version", action="version",
                        version=version)
    parser.add_argument(metavar="INPUT_MEDIUM",
                        nargs='?', dest="medium", type=str, default=None,
                        help=("Use INPUT_MEDIUM as the template for"
                              " Image creation, e.g., /dev/sdc, /disk0.vmdk."
                              " Specify a single slash character (/) to bundle"
                              " the filesystem of the host itself."))

    args = parser.parse_args()

    ensure_root(PROGNAME)

    if args.tmpdir is not None and not os.path.isdir(args.tmpdir):
        parser.error("Argument `%s' to --tmpdir must be a directory"
                     % args.tmpdir)

    # Setup logging and get a logger as early as possible.
    # FIXME: Must turn on redirect_stderr, but need to verify that only
    # errors/diagnostics and not user-visible output goes to stderr
    SetupLogging(PROGNAME, logfile=args.logfile, debug=args.verbose,
                 use_syslog=args.syslog, redirect_stderr_fd=False)
    log.info("%s v%s starting..." % (PROGNAME, version))

    # Ensure we run on a terminal, so we can use termios calls liberally
    if not (os.isatty(sys.stdin.fileno()) and os.isatty(sys.stdout.fileno())):
        sys.stderr.write(("Error: This program is interactive and requires a"
                          "terminal for standard input and output."))
        sys.exit(2)

    # Save the terminal attributes
    attr = termios.tcgetattr(sys.stdin.fileno())
    try:
        try:
            ret = dialog_main(args.medium, tmpdir=args.tmpdir,
                              snapshot=args.snapshot, syslog=args.syslog)
        finally:
            # Restore the terminal attributes. If an error occurs make sure
            # that the terminal turns back to normal.

            # This is an ugly hack:
            #
            # It seems resetting the terminal after using dialog
            # races with printing the text of the exception,
            # and overwrites it with the dialog background.
            #
            # Sleep for a tiny amount of time to ensure
            # the exception is visible.
            #
            # This code path is ugly and must be replaced:
            #
            # Logging should be mandatory, since we have a temporary directory
            # anyway, and all logging output should go there.
            time.sleep(0.5)
            termios.tcflush(sys.stdin.fileno(), termios.TCIOFLUSH)
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, attr)
    except:
        # An unexpected exception has occured.
        # Ensure the exception is logged,
        # then clear the screen and output the traceback.
        log.exception("Internal error. Unexpected Exception:")
        sys.stdout.flush()
        sys.stdout.write('\033[2J')  # Erase Screen
        sys.stdout.write('\033[H')  # Cursor Home
        sys.stdout.flush()

        exception = traceback.format_exc()
        sys.stderr.write("An unexpected exception has occured. Please"
                         " include the following text in any bug report:\n\n")
        sys.stderr.write(exception)
        sys.stderr.write(("\nLogfile `%s' may contain more information about"
                          " the cause of this error.\n\n" % args.logfile))
        sys.stderr.flush()

        sys.exit(3)

    sys.exit(ret)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
