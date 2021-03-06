Installation
^^^^^^^^^^^^

This guide describes how to install snf-image-creator on a Linux system. It is
highly recommended to have virtualization capable hardware. snf-image-creator
will work on processors that do not support virtualization but it will be slow.

Dependencies
============

snf-image-creator depends on the following programs:

 * Python 2 [http://www.python.org/]
 * Python setuptools [http://pypi.python.org/pypi/setuptools]
 * Python Dialog [http://pythondialog.sourceforge.net/]
 * Python bindings for libguestfs [http://libguestfs.org/]
 * Python interface to sendfile [http://pypi.python.org/pypi/pysendfile]
 * pyparted [https://fedorahosted.org/pyparted/]
 * rsync [http://rsync.samba.org/]
 * ./kamaki [https://code.grnet.gr/projects/kamaki]
 * Python sh (previously pbs) [https://github.com/amoffat/sh]
 * ANSI colors for Python [http://pypi.python.org/pypi/ansicolors]
 * progress [http://pypi.python.org/pypi/progress]

The above dependencies are resolved differently, depending on the installation
method you choose. There are two installation methods available:

#. `Installation using packages <#install-snf-image-creator-using-packages>`_

#. `Installation from source <#install-snf-image-creator-from-source>`_

Install snf-image-creator using packages
========================================

Debian
------

For *Debian 7.0 (wheezy)* you can use our official packages found in our
development repository.

Add the following line to */etc/apt/sources.list*:

.. code-block:: console

   deb http://apt.dev.grnet.gr wheezy/

Add the apt-dev GPG key to the list of trusted keys:

.. code-block:: console

   # wget --no-check-certificate  -qO-  http://dev.grnet.gr/files/apt-grnetdev.pub | apt-key add -

And resynchronize the package index files from their sources:

.. code-block:: console

   # apt-get update

You should be able to list the package by calling:

.. code-block:: console

   # apt-cache showpkg snf-image-creator

And install the package with this command:

.. code-block:: console

   # apt-get install snf-image-creator

Ubuntu
------

For *Ubuntu 12.04 LTS* and *14.04 LTS* systems, you can use our official
packages found in *grnet/synnefo* Lauchpad PPA.

Add the Synnefo PPA in your system:

.. code-block:: console

   $ sudo apt-add-repository ppa:grnet/synnefo
   $ sudo apt-get update

If *apt-add-repository* is missing, first install:

*software-properties-common* (Ubuntu 14.04):

.. code-block:: console

   $ sudo apt-get install software-properties-common

Or *python-software-properties* (Ubuntu 12.04):

.. code-block:: console

   $ sudo apt-get install python-software-properties

After the Synnefo repository is set up, you should be able to list
snf-image-creator by calling:

.. code-block:: console

   $ apt-cache showpkg snf-image-creator

Install the package by issuing:

.. code-block:: console

   $ sudo apt-get install snf-image-creator

.. note::
   If you are asked during the installation to create/update a
   "supermin appliance", choose "Yes".

Fedora
------

For *Fedora 20* you can use our official packages hosted at the *synnefo*
repository of the openSUSE Build Service.

Add the *synnefo* repository for *Fedora 20* to *yum*:

.. code-block:: console

   # cd /etc/yum.repos.d
   # curl -O http://download.opensuse.org/repositories/home:/GRNET:/synnefo/Fedora_20/home:GRNET:synnefo.repo

To list the *snf-image-creator* package use the following command:

.. code-block:: console

   # yum info snf-image-creator

Install the package by issuing:

.. code-block:: console

   # yum install snf-image-creator

CentOS
------

For *CentOS 6* and *CentOS 7* you can use our official packages hosted at the
*synnefo* repository of the OpenSUSE Build Service.

Add the *synnefo* repository for *CentOS 6* to the yum repositories list:

For *CentOS 6*:

.. code-block:: console

   # cd /etc/yum.repos.d
   # curl -O http://download.opensuse.org/repositories/home:/GRNET:/synnefo/CentOS_CentOS-6/home:GRNET:synnefo.repo

For *CentOS 7*:

.. code-block:: console

   # cd /etc/yum.repos.d
   # curl -O http://download.opensuse.org/repositories/home:/GRNET:/synnefo/CentOS_7/home:GRNET:synnefo.repo

Check the `Fedora <#fedora>`_ instructions on how to install the software.

openSUSE
--------

For *openSUSE 13.1* you can use our official packages hosted at the *Synnefo*
repository of the openSUSE Build Service.

Add the *Virtualization* repository for *openSUSE 13.1* to *YaST* with the
*Zypper* package manager:

.. code-block:: console

   # zypper ar -f http://download.opensuse.org/repositories/Virtualization/openSUSE_13.1/Virtualization.repo

Add the *Synnefo* repository:

.. code-block:: console

   # zypper ar -f http://download.opensuse.org/repositories/home:/GRNET:/synnefo/openSUSE_13.1/home:GRNET:synnefo.repo

To list the *snf-image-creator* package use the following command:

.. code-block:: console

   # zypper se snf-image-creator

Install the package by issuing:

.. code-block:: console

   # zypper in snf-image-creator


Arch Linux
----------

For *Arch Linux* there are **unofficial** packages in AUR:
https://aur.archlinux.org/packages/snf-image-creator/ kindly provided by
Axilleas Pipinellis <axilleas@archlinux.info>.

.. note::
    Those packages are not maintained by the Synnefo development team.

    Please direct package-specific questions to Axilleas Pipinellis <axilleas@archlinux.info>,
    Cc: the Synnefo development team <synnefo-devel@googlegroups.com>

To install the package you may use *yaourt*. Create and install
the *yaourt* package:

.. code-block:: console

   $ wget https://aur.archlinux.org/packages/pa/package-query/package-query.tar.gz
   $ tar -xvf package-query.tar.gz
   $ cd package-query
   $ makepkg -s
   $ su -c 'pacman -U package-query-<VERSION>-<ARCH>.pkg.tar.xz'
   $ cd ..
   $ wget https://aur.archlinux.org/packages/ya/yaourt/yaourt.tar.gz
   $ tar -xvf yaourt.tar.gz
   $ cd yaourt
   $ makepkg -s
   $ su -c 'pacman -U yaourt-<VERSION>-<ARCH>.pkg.tar.xz'

Install *snf-image-creator* using yaourt:

.. code-block:: console

   $ yaourt -Sa snf-image-creator

Install snf-image-creator from source
=====================================

Manually install the following dependencies:

 * Python 2 [http://www.python.org/]
 * Python setuptools [http://pypi.python.org/pypi/setuptools]
 * Python Dialog [http://pythondialog.sourceforge.net/]
 * Python bindings for libguestfs [http://libguestfs.org/]
 * Python interface to sendfile [http://pypi.python.org/pypi/pysendfile]
 * pyparted [https://fedorahosted.org/pyparted/]
 * rsync [http://rsync.samba.org/]

In Ubuntu you can do this using:
 
.. code-block:: console

   $ sudo apt-get install python-setuptools python-guestfs python-dialog \
     python-sendfile python-parted rsync

If you are using Ubuntu 12.10 you also need to install libguestfs-tools:

.. code-block:: console

   $ sudo apt-get install libguestfs-tools

.. note::
   If you are asked during the installation to create/update a
   "supermin appliance", choose "Yes".

Python Virtual Environment
--------------------------

Since snf-image-creator and the rest of its dependencies won't be installed
using packages, it's better to work in an isolated python virtual environment
(virtualenv).

Install the Virtual Python Environment builder:
http://pypi.python.org/pypi/virtualenv.

For Ubuntu use the following command:

.. code-block:: console

   $ sudo apt-get install python-virtualenv

Then create a new python virtual environment:

.. code-block:: console

   $ virtualenv --system-site-packages ~/image-creator-env

and activate it by executing:

.. code-block:: console

   $ source ~/image-creator-env/bin/activate

You may later deactivate it using:

.. code-block:: console

   $ deactivate

kamaki Installation
-------------------

Refer to `./kamaki documentation <http://docs.dev.grnet.gr/kamaki/latest/installation.html>`_
for instructions. You may install *./kamaki* from source inside the virtualenv
you've created above or by using binary packages if they are available for your
distribution.

snf-image-creator Installation
------------------------------

Download the latest snf-image-creator source package from
`here <https://code.grnet.gr/projects/snf-image-creator/files>`_ and install it
inside the virtualenv using the following commands:

.. code-block:: console

   $ tar -xf snf_image_creator-<VERSION>.tar.gz
   $ cd snf_image_creator-<VERSION>
   $ python ./setup.py install

Alternatively, you can install the bleeding edge version of the software by
cloning its git repository:

.. code-block:: console

   $ git clone https://code.grnet.gr/git/snf-image-creator
   $ cd snf-image-creator
   $ python ./setup.py install

To do the latter, you'll need to have git (http://git-scm.com/) installed.
For Ubuntu this can be done using:

.. code-block:: console

   $ sudo apt-get install git

.. warning::
   Keep in mind that the bleeding edge version may be unstable or even
   unusable.

