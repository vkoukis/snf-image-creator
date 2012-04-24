# Copyright 2012 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

from os.path import basename

from kamaki.config import Config
from kamaki.clients import ClientError
from kamaki.clients.image import ImageClient
from kamaki.clients.pithos import PithosClient
from progress.bar import Bar

from image_creator.util import FatalError, output, success

CONTAINER = "images"


def progress(message):

    MSG_LENGTH = 30

    def progress_gen(n):
        msg = "%s:" % message

        progressbar = Bar(msg.ljust(MSG_LENGTH))
        progressbar.max = n
        for _ in range(n):
            yield
            progressbar.next()
        output("\r%s...\033[K" % message, False)
        success("done")
        yield
    return progress_gen


class Kamaki:
    def __init__(self, account, token):
        self.account = account
        self.token = token

        config = Config()

        pithos_url = config.get('storage', 'url')
        self.container = CONTAINER
        self.pithos_client = PithosClient(pithos_url, token, self.account,
                                                                self.container)

        image_url = config.get('image', 'url')
        self.image_client = ImageClient(image_url, token)

        self.uploaded_object = None

    def upload(self, file_obj, size=None, remote_path=None, hp=None, up=None):

        if remote_path is None:
            remote_path = basename(filename)

        try:
            self.pithos_client.create_container(self.container)
        except ClientError as e:
            if e.status != 202:  # Ignore container already exists errors
                raise FatalError("Pithos client: %d %s" % \
                                                    (e.status, e.message))
        try:
            hash_cb = progress(hp) if hp is not None else None
            upload_cb = progress(up) if up is not None else None
            self.pithos_client.create_object(remote_path, file_obj, size,
                                                            hash_cb, upload_cb)
            return "pithos://%s/%s/%s" % \
                            (self.account, self.container, remote_path)
        except ClientError as e:
            raise FatalError("Pithos client: %d %s" % (e.status, e.message))

    def register(self, name, location, metadata):

        params = {'is_public': 'true', 'disk_format': 'diskdump'}
        try:
            self.image_client.register(name, location, params, metadata)
        except ClientError as e:
            raise FatalError("Image client: %d %s" % (e.status, e.message))

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
