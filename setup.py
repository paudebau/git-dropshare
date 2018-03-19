#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license which the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

# TODO: improve with https://github.com/pypa/sampleproject

from setuptools import setup, find_packages

import dropshare

setup(name='git-dropshare',
      description="Git plus Dropbox sharing for binary documents.",
      url="https://github.com/paudebau/git-dropshare",
      version=dropshare.__version__,
      license=dropshare.__license__,
      author=dropshare.__author__,
      author_email=dropshare.__email__,
      packages=find_packages(),
      include_package_data=True,
      entry_points={'console_scripts': ['git-ds=dropshare.__init__:main []']},
      install_requires=['gitpython>=2', 'python-dateutil', 'pytz'],
      classifiers=['Development Status :: 4 - Beta',
                   'Environment :: Console',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
                   'Natural Language :: English',
                   'Operating System :: Unix',
                   'Operating System :: MacOS :: MacOS X',
                   'Programming Language :: Python :: 3.6',
                   'Topic :: Software Development :: Libraries',
                   'Topic :: Software Development :: Version Control',
                   'Topic :: Utilities'],
)
