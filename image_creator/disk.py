# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2014 GRNET S.A.
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

"""Module hosting the Disk class."""

from image_creator.util import get_command, try_fail_repeat, free_space, \
    FatalError, create_snapshot, image_info
from image_creator.bundle_volume import BundleVolume
from image_creator.image import Image

import stat
import os
import tempfile
import uuid
import shutil

import logging
log = logging.getLogger(__name__)

dd = get_command('dd')
dmsetup = get_command('dmsetup')
losetup = get_command('losetup')
blockdev = get_command('blockdev')


def get_tmp_dir(tmpdir=None):
    """Try to guess a suitable directory for holding temporary files.

    Try to guess a suitable directory for holding (rather big) temporary
    files, including the snapshot file used to protect the source medium.

    """

    # Don't try to outsmart the user, if they have already made a choice
    if tmpdir is not None:
        log.debug("Using user-specified value `%s' as tmp directory", tmpdir)
        return tmpdir

    # If the TMPDIR environment has been set, use it
    if "TMPDIR" in os.environ:
        tmpdir = os.environ["TMPDIR"]
        log.debug(("Using value of TMPDIR environment variable as tmp"
                   "directory"), tmpdir)
        return tmpdir

    # Otherwise, make a list of candidate locations (all mountpoints) and pick
    # the directory with the most available space, provided it is mounted
    # read-write. The standard /var/tmp, /tmp are added to the end of the list,
    # to ensure they are preferred over the mountpoint of the filesystem they
    # belong to.
    #
    # FIXME: Enumerating mount points using /etc/mtab is Linux-specific.
    # FIXME: Perhaps omit remote directories, e.g., NFS/SMB mounts?
    #        Must use stafs(2) for this, statvfs(2) does not return f_type

    with open("/etc/mtab", "r") as mtab:
        mounts = [l.strip() for l in mtab.readlines()]
    points = [m.split(" ")[1] for m in mounts] + ["/tmp", "/var/tmp"]

    # FIXME:
    # Disable the above algorithm for the time being, and reduce the
    # list of candidate directories to the standard /var/tmp, /tmp directories.
    #
    # It is un-intuitive and completely unexpected by the user to end up
    # using a random directory under /home, or under /mnt to hold temporary
    # files. Perhaps re-enable it when we actually have the ability to
    # propose these alternate locations to the user, and have them make
    # choose explicitly.
    #
    points = ["/var/tmp", "/tmp"]
    log.debug("Trying to guess a suitable tmpdir, candidates are: %s",
              ", ".join(points))

    stats = [os.statvfs(p) for p in points]
    rwzip = [z for z in zip(points, stats) if
                z[1].f_flag & os.ST_RDONLY == 0]
    # See http://plug.org/pipermail/plug/2010-August/023606.html
    # on why calculation of free space is based on f_frsize
    sortedzip = sorted(rwzip, key=lambda z: z[1].f_bavail * z[1].f_frsize,
                       reverse=True)
    tmpdir = sortedzip[0][0]

    log.debug("Using directory `%s' as tmp directory", tmpdir)
    return tmpdir


class Disk(object):
    """This class represents a hard disk hosting an Operating System

    A Disk instance never alters the source medium it is created from.
    Any change is done on a snapshot created by the device-mapper of
    the Linux kernel.
    """

    def __init__(self, source, output, tmp=None):
        """Create a new Disk instance out of a source medium. The source
        medium can be an image file, a block device or a directory.
        """
        self._cleanup_jobs = []
        self._images = []
        self._file = None
        self.source = source
        self.out = output
        self.meta = {}
        self.tmp = tempfile.mkdtemp(prefix='.snf_image_creator.',
                                    dir=get_tmp_dir(tmp))

        self._add_cleanup(shutil.rmtree, self.tmp)

    def _add_cleanup(self, job, *args):
        """Add a new job in the cleanup list."""
        self._cleanup_jobs.append((job, args))

    def _losetup(self, fname):
        """Setup a loop device and add it to the cleanup list. The loop device
        will be detached when cleanup is called.
        """
        loop = losetup('-f', '--show', fname)
        loop = loop.strip()  # remove the new-line char
        self._add_cleanup(try_fail_repeat, losetup, '-d', loop)
        return loop

    def _dir_to_disk(self):
        """Create a disk out of a directory."""
        if self.source == '/':
            bundle = BundleVolume(self.out, self.meta)
            image = '%s/%s.raw' % (self.tmp, uuid.uuid4().hex)

            def check_unlink(path):
                """Unlinks file if exists"""
                if os.path.exists(path):
                    os.unlink(path)

            self._add_cleanup(check_unlink, image)
            bundle.create_image(image)
            return image
        raise FatalError("Using a directory as medium source is supported")

    def cleanup(self):
        """Cleanup internal data. This needs to be called before the
        program ends.
        """
        try:
            while len(self._images):
                image = self._images.pop()
                image.destroy()
        finally:
            # Make sure those are executed even if one of the device.destroy
            # methods throws exeptions.
            while len(self._cleanup_jobs):
                job, args = self._cleanup_jobs.pop()
                job(*args)

    @property
    def file(self):
        """Convert the source medium into a file."""

        if self._file is not None:
            return self._file

        self.out.info("Examining source medium `%s' ..." % self.source, False)
        mode = os.stat(self.source).st_mode
        if stat.S_ISDIR(mode):
            self.out.success('looks like a directory')
            self._file = self._dir_to_disk()
        elif stat.S_ISREG(mode):
            self.out.success('looks like an image file')
            self._file = self.source
        elif not stat.S_ISBLK(mode):
            raise FatalError("Invalid medium source. Only block devices, "
                             "regular files and directories are supported.")
        else:
            self.out.success('looks like a block device')
            self._file = self.source

        return self._file

    def snapshot(self):
        """Creates a snapshot of the original source medium of the Disk
        instance.
        """

        if self.source == '/':
            self.out.warn("Snapshotting ignored for host bundling mode.")
            return self.file

        # Examine medium file
        info = image_info(self.file)

        self.out.info("Snapshotting medium source ...", False)

        # Create a qcow2 snapshot for image files that are not raw
        if info['format'] != 'raw':
            snapshot = create_snapshot(self.file, self.tmp)
            self._add_cleanup(os.unlink, snapshot)
            self.out.success('done')
            return snapshot

        # Create a device-mapper snapshot for raw image files and block devices
        mode = os.stat(self.file).st_mode
        device = self.file if stat.S_ISBLK(mode) else self._losetup(self.file)
        size = int(blockdev('--getsz', device))

        cowfd, cow = tempfile.mkstemp(dir=self.tmp)
        os.close(cowfd)
        self._add_cleanup(os.unlink, cow)
        # Create cow sparse file
        dd('if=/dev/null', 'of=%s' % cow, 'bs=512', 'seek=%d' % size)
        cowdev = self._losetup(cow)

        snapshot = 'snf-image-creator-snapshot-%s' % uuid.uuid4().hex
        tablefd, table = tempfile.mkstemp()
        try:
            try:
                os.write(tablefd, "0 %d snapshot %s %s n 8\n" %
                         (size, device, cowdev))
            finally:
                os.close(tablefd)

            dmsetup('create', snapshot, table)
            self._add_cleanup(try_fail_repeat, dmsetup, 'remove', snapshot)
        finally:
            os.unlink(table)
        self.out.success('done')
        return "/dev/mapper/%s" % snapshot

    def get_image(self, medium, **kwargs):
        """Returns a newly created Image instance."""
        info = image_info(medium)
        image = Image(medium, self.out, format=info['format'], **kwargs)
        self._images.append(image)
        image.enable()
        return image

    def destroy_image(self, image):
        """Destroys an Image instance previously created with the get_image()
        method.
        """

        self._images.remove(image)
        image.destroy()

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
