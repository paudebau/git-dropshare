# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license with the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

import sys
import argparse

from . import front

def main():
    parser = argparse.ArgumentParser(prog='git-dropshare')
    parser.add_argument('-C', dest='_repository', action='store', default='.', help='git working repository')

    subparsers = parser.add_subparsers()
    subparsers.add_parser('init', help='initialize a repository to use dropshare') \
              .add_argument('-f', dest='_force', action='store_true', help='force initialization procedure') \
              .set_defaults(call=front.Dropshare.ds_init)
    subparsers.add_parser('check', help='check dropshare configuration') \
              .set_defaults(call=front.Dropshare.ds_check)
    subparsers.add_parser('track', help='add pattern to set of tracked files') \
              .add_argument('_match', nargs='+', metavar='pattern', help='file pattern') \
              .set_defaults(call=front.Dropshare.ds_track)
    subparsers.add_parser('push', help='upload tracked files to Dropbox shared folder') \
              .add_argument('_match', nargs='*', metavar='pattern', help='limit push by pattern(s)') \
              .set_defaults(call=front.Dropshare.ds_push)
    subparsers.add_parser('pull', help='download tracked files from Dropbox shared folder') \
              .add_argument('_match', nargs='*', metavar='pattern', help='limit pull by pattern(s)') \
              .set_defaults(call=front.Dropshare.ds_pull)
    subparsers.add_parser('fetch', help='fetch and merge notes from a remote repository') \
              .add_argument('_remote', nargs=1, metavar='remote', help='fetch dropshare notes from remote') \
              .set_defaults(call=front.Dropshare.ds_fetch)
    subparsers.add_parser('filter-clean', help='clean stdin stream ') \
              .add_argument('-f', dest='_filename', action='store', metavar='path', default='stdin') \
              .set_defaults(call=front.Dropshare.ds_filter_clean)
    subparsers.add_parser('filter-smudge', help='smudge sdin stream') \
              .add_argument('-f', dest='_filename', action='store', metavar='path', default='stdin') \
              .set_defaults(call=front.Dropshare.ds_filter_smudge)
    subparsers.add_parser('delta', help='index dropshare storage area') \
              .set_defaults(call=front.Dropshare.ds_delta)
    subparsers.add_parser('log', help='dump history from dropshare notes') \
              .add_argument('_paths', nargs='+', metavar='filenames') \
              .set_defaults(call=front.Dropshare.ds_log)

    try:
        _ = parser.parse_args(namespace=front.Dropshare)
    except argparse.ArgumentError:
        parser.print_help()
        sys.exit(1)

    app = front.Dropshare()
    if hasattr(app, 'call'):
        sys.exit(app.call())
    else:
        parser.print_help()
