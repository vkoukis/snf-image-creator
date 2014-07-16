# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2014 GRNET S.A.
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

"""This module implements the "wizard" mode of the dialog-based version of
snf-image-creator.
"""

import time
import StringIO
import json

from image_creator.kamaki_wrapper import Kamaki, ClientError
from image_creator.util import MD5, FatalError
from image_creator.output.cli import OutputWthProgress
from image_creator.dialog_util import extract_image, update_background_title, \
    add_cloud, edit_cloud, virtio_versions, update_sysprep_param

PAGE_WIDTH = 70
PAGE_HEIGHT = 12


class WizardExit(Exception):
    """Exception used to exit the wizard"""
    pass


class WizardReloadPage(Exception):
    """Exception that reloads the last WizardPage"""
    pass


class Wizard:
    """Represents a dialog-based wizard

    The wizard is a collection of pages that have a "Next" and a "Back" button
    on them. The pages are used to collect user data.
    """

    def __init__(self, session):
        self.session = session
        self.pages = []
        self.session['wizard'] = {}
        self.d = session['dialog']

    def add_page(self, page):
        """Add a new page to the wizard"""
        self.pages.append(page)

    def run(self):
        """Run the wizard"""
        idx = 0
        while True:
            try:
                total = len(self.pages)
                title = "(%d/%d) %s" % (idx + 1, total, self.pages[idx].title)
                idx += self.pages[idx].run(self.session, title)
            except WizardExit:
                return False
            except WizardReloadPage:
                continue

            if idx >= len(self.pages):
                text = "All necessary information has been gathered:\n\n"
                for page in self.pages:
                    text += " * %s\n" % page.info
                text += "\nContinue with the image creation process?"

                ret = self.d.yesno(
                    text, width=PAGE_WIDTH, height=8 + len(self.pages),
                    ok_label="Yes", cancel="Back", extra_button=1,
                    extra_label="Quit", title="Confirmation")

                if ret == self.d.DIALOG_CANCEL:
                    idx -= 1
                elif ret == self.d.DIALOG_EXTRA:
                    return False
                elif ret == self.d.DIALOG_OK:
                    return True

            if idx < 0:
                return False


class WizardPage(object):
    """Represents a page in a wizard"""
    NEXT = 1
    PREV = -1

    def __init__(self, name, display_name, text, **kargs):
        self.name = name
        self.display_name = display_name
        self.text = text

        self.title = kargs['title'] if 'title' in kargs else ""
        self.default = kargs['default'] if 'default' in kargs else ""
        self.extra = kargs['extra'] if 'extra' in kargs else None
        self.extra_label = \
            kargs['extra_label'] if 'extra_label' in kargs else 'Extra'

        self.info = "%s: <none>" % self.display_name

        validate = kargs['validate'] if 'validate' in kargs else lambda x: x
        setattr(self, "validate", validate)

        display = kargs['display'] if 'display' in kargs else lambda x: x
        setattr(self, "display", display)

    def run(self, session, title):
        """Display this wizard page

        This function is used by the wizard program when accessing a page.
        """
        raise NotImplementedError


class WizardInfoPage(WizardPage):
    """Represents a Wizard Page that just displays some user-defined
    information.
    """
    def __init__(self, name, display_name, text, body, **kargs):
        super(WizardInfoPage, self).__init__(name, display_name, text, **kargs)
        self.body = body

    def run(self, session, title):
        d = session['dialog']
        w = session['wizard']

        extra_button = 1 if self.extra else 0
        text = "%s\n\n%s" % (self.text, self.body())

        ret = d.yesno(text, width=PAGE_WIDTH, ok_label="Next",
                      cancel="Back", extra_button=extra_button, title=title,
                      extra_label=self.extra_label, height=PAGE_HEIGHT)

        if ret in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return self.PREV
        elif ret == d.DIALOG_EXTRA:
            self.extra()
            raise WizardReloadPage

        # DIALOG_OK
        w[self.name] = self.validate(None)
        self.info = "%s: %s" % (self.display_name, self.display(w[self.name]))
        return self.NEXT


class WizardPageWthChoices(WizardPage):
    """Represents a Wizard Page that allows the user to select something from
    a list of choices.

    The available choices are created by a function passed to the class through
    the choices variable. If the choices function returns an empty list, a
    fallback function is executed if available.
    """
    def __init__(self, name, display_name, text, choices, **kargs):
        super(WizardPageWthChoices, self).__init__(name, display_name, text,
                                                   **kargs)
        self.choices = choices
        self.fallback = kargs['fallback'] if 'fallback' in kargs else None


class WizardRadioListPage(WizardPageWthChoices):
    """Represent a Radio List in a wizard"""

    def run(self, session, title):
        d = session['dialog']
        w = session['wizard']

        choices = []
        for choice in self.choices():
            default = 1 if choice[0] == self.default else 0
            choices.append((choice[0], choice[1], default))

        (code, answer) = d.radiolist(
            self.text, width=PAGE_WIDTH, ok_label="Next", cancel="Back",
            choices=choices, height=PAGE_HEIGHT, title=title)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return self.PREV

        w[self.name] = self.validate(answer)
        self.default = answer
        self.info = "%s: %s" % (self.display_name, self.display(w[self.name]))

        return self.NEXT


class WizardInputPage(WizardPage):
    """Represents an input field in a wizard"""

    def run(self, session, title):
        d = session['dialog']
        w = session['wizard']

        (code, answer) = d.inputbox(
            self.text, init=self.default, width=PAGE_WIDTH, ok_label="Next",
            cancel="Back", height=PAGE_HEIGHT, title=title)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return self.PREV

        value = answer.strip()
        self.default = value
        w[self.name] = self.validate(value)
        self.info = "%s: %s" % (self.display_name, self.display(w[self.name]))

        return self.NEXT


class WizardFormPage(WizardPage):
    """Represents a Form in a wizard"""

    def __init__(self, name, display_name, text, fields, **kargs):
        super(WizardFormPage, self).__init__(name, display_name, text, **kargs)
        self.fields = fields

    def run(self, session, title):
        d = session['dialog']
        w = session['wizard']

        field_lenght = len(self.fields())
        form_height = field_lenght if field_lenght < PAGE_HEIGHT - 4 \
            else PAGE_HEIGHT - 4

        (code, output) = d.form(
            self.text, width=PAGE_WIDTH, height=PAGE_HEIGHT,
            form_height=form_height, ok_label="Next", cancel="Back",
            fields=self.fields(), title=title)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return self.PREV

        w[self.name] = self.validate(output)
        self.default = output
        self.info = "%s: %s" % (self.display_name, self.display(w[self.name]))

        return self.NEXT


class WizardMenuPage(WizardPageWthChoices):
    """Represents a menu dialog with available choices in a wizard"""

    def run(self, session, title):
        d = session['dialog']
        w = session['wizard']

        extra_button = 1 if self.extra else 0

        choices = self.choices()

        if len(choices) == 0:
            assert self.fallback, "Zero choices and no fallback"
            if self.fallback():
                raise WizardReloadPage
            else:
                return self.PREV

        default_item = self.default if self.default else choices[0][0]

        (code, choice) = d.menu(
            self.text, width=PAGE_WIDTH, ok_label="Next", cancel="Back",
            title=title, choices=choices, height=PAGE_HEIGHT,
            default_item=default_item, extra_label=self.extra_label,
            extra_button=extra_button)

        if code in (d.DIALOG_CANCEL, d.DIALOG_ESC):
            return self.PREV
        elif code == d.DIALOG_EXTRA:
            self.extra()
            raise WizardReloadPage

        self.default = choice
        w[self.name] = self.validate(choice)
        self.info = "%s: %s" % (self.display_name, self.display(w[self.name]))

        return self.NEXT


def start_wizard(session):
    """Run the image creation wizard"""

    image = session['image']
    distro = image.distro
    ostype = image.ostype

    # Create Cloud Wizard Page
    def cloud_choices():
        choices = []
        for (name, cloud) in Kamaki.get_clouds().items():
            descr = cloud['description'] if 'description' in cloud else ''
            choices.append((name, descr))

        return choices

    def cloud_add():
        return add_cloud(session)

    def cloud_none_available():
        if not session['dialog'].yesno(
                "No available clouds found. Would you like to add one now?",
                width=PAGE_WIDTH, defaultno=0):
            return add_cloud(session)
        return False

    def cloud_validate(cloud):
        if not Kamaki.get_account(cloud):
            if not session['dialog'].yesno(
                    "The cloud you have selected is not valid! Would you "
                    "like to edit it now?", width=PAGE_WIDTH, defaultno=0):
                if edit_cloud(session, cloud):
                    return cloud

            raise WizardReloadPage

        return cloud

    cloud = WizardMenuPage(
        "Cloud", "Cloud",
        "Please select a cloud account or press <Add> to add a new one:",
        choices=cloud_choices, extra_label="Add", extra=cloud_add,
        title="Clouds", validate=cloud_validate, fallback=cloud_none_available)

    # Create Image Name Wizard Page
    name = WizardInputPage(
        "ImageName", "Image Name", "Please provide a name for the image:",
        title="Image Name", default=ostype if distro == "unknown" else distro)

    # Create Image Description Wizard Page
    descr = WizardInputPage(
        "ImageDescription", "Image Description",
        "Please provide a description for the image:",
        title="Image Description", default=session['metadata']['DESCRIPTION']
        if 'DESCRIPTION' in session['metadata'] else '')

    # Create VirtIO Installation Page
    def display_installed_drivers():
        """Returnes the installed virtio drivers"""
        versions = virtio_versions(image.os.virtio_state)

        ret = "Installed Block Device Driver:  %(netkvm)s\n" \
              "Installed Network Device Driver: %(viostor)s\n" % versions

        virtio = image.os.sysprep_params['virtio'].value
        if virtio:
            ret += "\nNew Block Device Driver:   %(netkvm)s\n" \
                   "New Network Device Driver: %(viostor)s\n" % \
                   virtio_versions(image.os.compute_virtio_state(virtio))
        return ret

    def validate_virtio(_):
        netkvm = len(image.os.virtio_state['netkvm']) != 0
        viostor = len(image.os.virtio_state['viostor']) != 0
        drv_dir = image.os.sysprep_params['virtio'].value

        if netkvm is False or viostor is False:
            new = image.os.compute_virtio_state(drv_dir) if drv_dir else None
            new_viostor = len(new['viostor']) != 0 if new else False
            new_netkvm = len(new['netkvm']) != 0 if new else False

            d = session['dialog']
            title = "VirtIO driver missing"
            msg = "Image creation cannot proceed unless a VirtIO %s driver " \
                  "is installed on the media!"
            if not (viostor or new_viostor):
                d.msgbox(msg % "Block Device", width=PAGE_WIDTH,
                         height=PAGE_HEIGHT, title=title)
                raise WizardReloadPage
            if not(netkvm or new_netkvm):
                d.msgbox(msg % "Network Device", width=PAGE_WIDTH,
                         height=PAGE_HEIGHT, title=title)
                raise WizardReloadPage

        return drv_dir

    virtio = WizardInfoPage(
        "virtio", "VirtIO Drivers Path",
        "Press <New> to install new VirtIO drivers.",
        display_installed_drivers, title="VirtIO Drivers", extra_label='New',
        extra=lambda: update_sysprep_param(session, 'virtio'),
        validate=validate_virtio)

    # Create Image Registration Wizard Page
    def registration_choices():
        return [("Private", "Image is accessible only by this user"),
                ("Public", "Everyone can create VMs from this image")]

    registration = WizardRadioListPage(
        "ImageRegistration", "Registration Type",
        "Please provide a registration type:", registration_choices,
        title="Registration Type", default="Private")

    wizard = Wizard(session)

    wizard.add_page(cloud)
    wizard.add_page(name)
    wizard.add_page(descr)
    if hasattr(image.os, 'install_virtio_drivers'):
        wizard.add_page(virtio)
    wizard.add_page(registration)

    if wizard.run():
        create_image(session)
    else:
        return False

    return True


def create_image(session):
    """Create an image using the information collected by the wizard"""
    d = session['dialog']
    image = session['image']
    wizard = session['wizard']

    with_progress = OutputWthProgress(True)
    out = image.out
    out.add(with_progress)
    try:
        out.clear()

        if 'virtio' in wizard and image.os.sysprep_params['virtio'].value:
            image.os.install_virtio_drivers()

        # Sysprep
        image.os.do_sysprep()
        metadata = image.os.meta

        # Shrink
        size = image.shrink()
        session['shrinked'] = True
        update_background_title(session)

        metadata.update(image.meta)
        metadata['DESCRIPTION'] = wizard['ImageDescription']

        # MD5
        md5 = MD5(out)
        session['checksum'] = md5.compute(image.device, size)

        out.output()
        try:
            out.output("Uploading image to the cloud:")
            account = Kamaki.get_account(wizard['Cloud'])
            assert account, "Cloud: %s is not valid" % wizard['Cloud']
            kamaki = Kamaki(account, out)

            name = "%s-%s.diskdump" % (wizard['ImageName'],
                                       time.strftime("%Y%m%d%H%M"))
            pithos_file = ""
            with open(image.device, 'rb') as f:
                pithos_file = kamaki.upload(f, size, name,
                                            "(1/3)  Calculating block hashes",
                                            "(2/3)  Uploading missing blocks")

            out.output("(3/3)  Uploading md5sum file ...", False)
            md5sumstr = '%s %s\n' % (session['checksum'], name)
            kamaki.upload(StringIO.StringIO(md5sumstr), size=len(md5sumstr),
                          remote_path="%s.%s" % (name, 'md5sum'))
            out.success('done')
            out.output()

            is_public = True if wizard['ImageRegistration'] == "Public" else \
                False
            out.output('Registering %s image with the cloud ...' %
                       wizard['ImageRegistration'].lower(), False)
            result = kamaki.register(wizard['ImageName'], pithos_file,
                                     metadata, is_public)
            out.success('done')
            out.output("Uploading metadata file ...", False)
            metastring = unicode(json.dumps(result, ensure_ascii=False))
            kamaki.upload(StringIO.StringIO(metastring), size=len(metastring),
                          remote_path="%s.%s" % (name, 'meta'))
            out.success('done')

            if is_public:
                out.output("Sharing md5sum file ...", False)
                kamaki.share("%s.md5sum" % name)
                out.success('done')
                out.output("Sharing metadata file ...", False)
                kamaki.share("%s.meta" % name)
                out.success('done')

            out.output()

        except ClientError as e:
            raise FatalError("Storage service client: %d %s" %
                             (e.status, e.message))
    finally:
        out.remove(with_progress)

    text = "The %s image was successfully uploaded to the storage service " \
           "and registered with the compute service of %s. Would you like " \
           "to keep a local copy?" % \
           (wizard['Cloud'], wizard['ImageRegistration'].lower())

    if not d.yesno(text, width=PAGE_WIDTH):
        extract_image(session)

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
