# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GRNET S.A.
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

"""This module hosts Windows PowerShell scripts that need to be injected into
the windows image"""

DRVINST = r"""
#requires -version 2

Param([string]$dirName=$(throw "You need to provide a directory name"))

if (!(Test-Path -PathType Container "$dirName")) {
    Write-Error -Category InvalidArgument "Invalid Directory: $dirName"
    Exit
}

foreach ($file in Get-ChildItem "$dirName" -Filter *.cat) {
    $cert = (Get-AuthenticodeSignature $file.FullName).SignerCertificate
    $certFile = $dirName + "\" + $file.BaseName + ".cer"
    [System.IO.File]::WriteAllBytes($certFile, $cert.Export("Cert"))
    CertUtil -addstore TrustedPublisher "$certFile"
}

if (Test-Path "$dirName/viostor.inf") {
    pnputil.exe -i -a "$dirName/viostor.inf"
}

pnputil.exe -a "$dirname\*.inf"

shutdown /s /t 5
"""

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
