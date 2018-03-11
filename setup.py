#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license which the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

from setuptools import setup

setup(name='git-dropshare',
      description="Git plus Dropbox sharing for binary documents.",
      version="0.1.0",
      license="Gnu Public License v3",
      author="Philippe Audebaud",
      author_email="paudebau@gmail.com",
      url="https://github.com/paudebau/git-dropshare",
      classifiers=["Development Status :: Beta",
                   "Environment :: Console",
                   "Intended Audience :: Developers",
                   "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
                   "Natural Language :: English",
                   "Operating System :: Unix",
                   "Operating System :: MacOS :: MacOS X",
                   "Programming Language :: Python :: 3.6",
                   "Topic :: Software Development :: Libraries",
                   "Topic :: Software Development :: Version Control",
                   "Topic :: Utilities"],
      packages=['dropshare'],
      entry_points={"console_scripts": ["git-ds=dropshare.__init__:main []"]},
      install_requires=['gitpython>=2', 'python-dateutil', 'pytz'],
)
