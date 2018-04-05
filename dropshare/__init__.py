# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license with the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

import sys
import argparse
from contextlib import contextmanager
from typing import Iterator

from . import front, store, git

__version__ = '0.1.4'
__author__ = 'Philippe Audebaud <paudebau@gmail.com>'
__copyright__ = 'Copyright 2018, Philippe Audebaud <paudebau@gmail.com>'
__maintainer__ = 'Philippe Audebaud'
__email__ = "paudebau@gmail.com"
__license__ = 'Gnu Public License v3'

class Parser:
    def __init__(self) -> None:
        self.parser = argparse.ArgumentParser(prog='git-dropshare')
        self.parser.add_argument('-C', dest='_repository', metavar="REPOSITORY",
                                 action='store', default='.',
                                 help='git working repository')
        self.subparser = self.parser.add_subparsers()

    def help(self):
        self.parser.print_help()

    @contextmanager
    def action(self, *args, **kwargs) -> Iterator[argparse.ArgumentParser]:
            try:
                yield self.subparser.add_parser(*args, **kwargs)
            finally:
                pass

def main():
    p = Parser()
    with p.action('init', help='initialize a repository to use dropshare') as cmd:
        cmd.add_argument('-f', dest='_force', action='store_true', help='force initialisation procedure')
        cmd.set_defaults(call=front.Dropshare.ds_init)
    with p.action('check', help='check dropshare configuration') as cmd:
        cmd.set_defaults(call=front.Dropshare.ds_check)
    with p.action('track', help='add pattern to set of tracked files') as cmd:
        cmd.add_argument('_match', nargs=1, metavar='PATTERN', help='file pattern')
        cmd.set_defaults(call=front.Dropshare.ds_track)
    with p.action('push', help='upload tracked files to Dropbox shared folder') as cmd:
        cmd.add_argument('_match', nargs='*', metavar='PATTERN', help='limit push by pattern(s)')
        cmd.set_defaults(call=front.Dropshare.ds_push)
    with p.action('pull', help='download tracked files from Dropbox shared folder') as cmd:
        cmd.add_argument('_match', nargs='*', metavar='PATTERN', help='limit pull by pattern(s)')
        cmd.set_defaults(call=front.Dropshare.ds_pull)
    with p.action('fetch', help='fetch and merge notes from a remote repository') as cmd:
        cmd.add_argument('_remote', nargs=1, metavar='REMOTE', help='fetch dropshare notes from remote')
        cmd.set_defaults(call=front.Dropshare.ds_fetch)
    with p.action('filter-clean', help='clean stdin stream ') as cmd:
        cmd.add_argument('-f', dest='_filename', action='store', metavar='PATH', default='stdin')
        cmd.set_defaults(call=front.Dropshare.ds_filter_clean)
    with p.action('filter-smudge', help='smudge sdin stream') as cmd:
        cmd.add_argument('-f', dest='_filename', action='store', metavar='PATH', default='stdin')
        cmd.set_defaults(call=front.Dropshare.ds_filter_smudge)
    with p.action('delta', help='index dropshare storage area') as cmd:
        cmd.set_defaults(call=front.Dropshare.ds_delta)
    with p.action('log', help='dump history from dropshare notes') as cmd:
        cmd.add_argument('_paths', nargs='+', metavar='FILES')
        cmd.set_defaults(call=front.Dropshare.ds_log)

    try:
        _ = p.parser.parse_args(namespace=front.Dropshare)
    except argparse.ArgumentError:
        p.help()
        sys.exit(1)

    app = front.Dropshare()
    if hasattr(app, 'call'):
        sys.exit(app.call())
    else:
        p.help()

__all__ = ['main', 'store', 'git']
