# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copyof the license with the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

import os
import sys
import operator
import tempfile
from contextlib import contextmanager

from . import tools, back

class Dropshare(back.Backend):

    store = False
    # calls args
    _force = None     # init
    _match = []       # pull/push
    _remote = None    # fetch
    _filename = None  # log
    _paths = []

    def __init__(self):
        super().__init__()
        if not self.store:
            tools.Console.write('Dropshare not operational. Leaving...\n')
            sys.exit(1)

    @contextmanager
    def _dropshare_notes(self):
        """ Notes are neither pushed, pulled or fetched automatically, so... """
        self.ds_ready()
        self.ds_pull_notes()
        self.ds_delta()
        try:
            yield
        except back.BackendException as exc:
            tools.Console.write(exc.message)
            sys.exit(1)
        finally:
            self.ds_push_notes()

    def ds_fetch(self):
        with self._dropshare_notes():
            self.ds_pull_notes(self._remote)

    def ds_pull(self):
        with self._dropshare_notes():
            for sha, fname, stub in self.filtered_by_attributes(self._match):
                if stub[0] != tools.hash_file(fname, self.hasher()):
                    with open(fname, 'wb') as out_stream:
                        if self.data_pull(out_stream, *stub):
                            self.ds_append_note(sha, "pull", *stub)
                            self.git.add(fname)
                        else:
                            tools.Console.write(f' \u2717 fails to download {fname}.\n')

    def ds_push(self):
        with self._dropshare_notes():
            for sha, fname, stub in self.filtered_by_attributes(self._match):
                if not self.ds_has_note(sha, fname, *stub):
                    with open(fname, 'rb') as in_stream:
                        if not self.data_push(in_stream, *stub):
                            tools.Console.write(f' \u2713 file {fname} already in store.\n')
                    self.ds_append_note(sha, "push", *stub)

    def ds_filter_clean(self):
        """ Checking process. Warning: path merely informative. """
        out_stream, path = sys.stdout.buffer, self._filename
        with tools.scanner(sys.stdin.buffer) as in_stream:
            if in_stream.ds_is_stub():
                tools.Console.write(f" * clean/cat {path}\n")
                tools.cat_stream(in_stream, out_stream)
                return
            stub = tools.hash_file(path, self.hasher()), path
            out_stream.write(tools.DS_WRITE(*stub))

    def ds_filter_smudge(self):
        """ Checkout process. Warning: path merely informative. """
        out_stream, path = sys.stdout.buffer, self._filename
        with tools.scanner(sys.stdin.buffer) as in_stream:
            stub = in_stream.ds_stub()
            if stub is None or not self.data_exists(stub[0]):
                tools.Console.write(f" * smudge/cat {path}\n")
                tools.cat_stream(in_stream, out_stream)
                return
            with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as tmp_stream:
                self.data_pull(tmp_stream, *stub, special='smudge')
                tools.cat_stream(tmp_stream, out_stream)

    def ds_init(self):
        if not self.store or self._force:
            self.set_credentials()
        if not self.store:
            tools.Console.write('failed to access storage; token invalid?\n')
            sys.exit(1)
        else:
            self.ds_install()
            self.ds_delta()

    def ds_check(self, init=False):
        tag = self.git_config('dropshare.account', None)
        if not self.store or tag is None:
            tools.Console.write(f' \u2717 dropshare not configured yet?...\n')
            sys.exit(1)
        tools.Console.write(f' \u2713 found dropshare account = {tag}\n')
        missing = False
        for key in self.DS_KEYS:
            val = self.git_config('--global', f'dropshare.{tag}.{key}')
            if val is None:
                missing = True
                tools.Console.write(f' \u2717 dropshare.{key} is not set\n')
            else:
                tools.Console.write(f' \u2713 dropshare.{key} = {val}\n')
        if missing:
            tools.Console.write(f' * call "git-ds init" first!\n')

    def ds_track(self):
        self.ds_add_pattern([x.strip() for x in self._match])

    def ds_delta(self):
        changed, deleted, inserted = self.dbx.delta()
        if changed:
            tools.Console.write(f' * {len(deleted)} deleted, {len(inserted)} updated.\n')
        else:
            tools.Console.write(f' * delta() returns no changes.\n')

    def ds_log(self):
        for fname in self._paths:
            if not os.path.exists(fname):
                tools.Console.write(f' \u2717 file {fname} does not exist.\n')
                return
            entries = []
            for tree in self.git.log("--pretty=format:%T", fname).split('\n'):
                for _, sha in self.git_ls_tree('-r', tree, fname):
                    for timestamp, direction, _, _, user in self.ds_manifest(sha, reverse=True):
                        dt_local = tools.local_date(timestamp)
                        dt_fmt = dt_local.strftime("%A %d %B %Y, %X")
                        arrow = '\u2190' if direction == 'push' else '\u2192'
                        entries.append((dt_local, sha[:6], dt_fmt, arrow, user))
            sentries = sorted(entries, key=operator.itemgetter(0), reverse=True)
            for _, sha, date, arrow, user in sentries:
                tools.Console.write(f" {arrow} ({sha}) {date} by {user}.\n")

    def ds_show(self):
        from subprocess import call

        if os.path.exists(self._filename):
            call("xdg-open {}".format(self._filename), shell=True)
        else:
            tools.Console.write(f' \u2717 dropshare: file not found "{self._filename}".\n')
