# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copyof the license with the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

import os
import sys
import shutil
import operator
from contextlib import contextmanager
from typing import List, Optional

from . import tools, back

class Dropshare(back.Backend):

    store = False
    # calls args
    _force = False    # init
    _match = []       # type: List[str] # pull/push
    _remote = None    # type: Optional[str] # fetch
    _filename = None  # type: Optional[str] # log
    _paths = []       # type: List[str]

    def __init__(self):
        super().__init__()
        if not self.store:
            tools.Console.warning('Dropshare not operational. Leaving...')
            #sys.exit(1)

    def call(self):
        pass

    @contextmanager
    def _dropshare_notes(self):
        """ Notes are neither pushed, pulled or fetched automatically, so... """
        self.ds_ready()
        self.ds_pull_notes()
        self.ds_delta()
        try:
            yield
        except back.BackendException as exc:
            tools.Console.error(exc.message)
            sys.exit(1)
        finally:
            self.ds_push_notes()

    def ds_fetch(self):
        with self._dropshare_notes():
            self.ds_pull_notes(self._remote)

    def _checkout(self):
        # hack to trigger smudge filter on remaining stubs
        for hexdigest, fname in self.ds_orphan_files():
            if os.access(os.path.join(self.obj_directory, hexdigest), os.R_OK):
                os.utime(fname, None)
                self.git.checkout_index(fname, index=True, force=True)
        # remove objects writtent by clean filter
        for fname in self.ds_staging_objects():
            if self.data_exists(fname):
                os.unlink(os.path.join(self.obj_directory, fname))
        # tools.Console.write(' * check repository status: ', cr=False)
        # tools.Console.write('dirty' if self.git_repo.is_dirty() else 'OK')

    def ds_pull(self):
        with self._dropshare_notes():
            for sha, fname, hexdigest in self.filtered_by_attributes(self._match):
                if hexdigest != tools.hash_file(fname, self.hasher()):
                    obj_hexdigest = os.path.join(self.obj_directory, hexdigest)
                    if not os.access(obj_hexdigest, os.W_OK):
                        with open(obj_hexdigest, 'wb') as out_stream:
                            if self.data_pull(out_stream, hexdigest, fname):
                                self.ds_append_note(sha, "pull", hexdigest, fname)
                                # self.git.add(fname)
                            else:
                                tools.Console.info(f' \u2717 fails to download {fname}.')
            self._checkout()
            self.git.status()

    def ds_push(self):
        with self._dropshare_notes():
            for sha, fname, hexdigest in self.filtered_by_attributes(self._match):
                if not self.ds_has_note(sha, fname, hexdigest, fname):
                    with open(fname, 'rb') as in_stream:
                        if not self.data_push(in_stream, hexdigest, fname):
                            tools.Console.info(f' \u2713 file {fname} already in store.')
                    self.ds_append_note(sha, "push", hexdigest, fname)

    def ds_filter_clean(self):
        """run when a file is added to the index (checking):
        - receives the "smudged" (tree) version of the file on stdin (stub)
        - produces the "clean" (working repository) version on stdout.
        - N.B.: the additional path argument serves only informative purpose."""
        out_stream, path = sys.stdout.buffer, self._filename
        with tools.scanner(sys.stdin.buffer) as in_stream:
            if in_stream.ds_is_stub():
                tools.cat_stream(in_stream, out_stream)
            else:
                # We keep in cache objects not already available in store
                hexdigest = tools.hash_file(path, self.hasher())
                if not self.data_exists(hexdigest):
                    obj_hexdigest = os.path.join(self.obj_directory, hexdigest)
                    if not os.access(obj_hexdigest, os.W_OK) or \
                       os.path.getsize(obj_hexdigest) != os.path.getsize(path):
                        shutil.copy(path, obj_hexdigest)
                        os.chmod(obj_hexdigest, int('644', 8) & ~tools.umask())
                out_stream.write(tools.DS_WRITE(hexdigest, path))

    def ds_filter_smudge(self):
        """ Checkout process. Warning: path merely informative. """
        out_stream, path = sys.stdout.buffer, self._filename
        with tools.scanner(sys.stdin.buffer) as in_stream:
            try:
                hexdigest, _ = in_stream.ds_stub()
            except:
                tools.cat_stream(in_stream, out_stream)
            else:
                obj_hexdigest = os.path.join(self.obj_directory, hexdigest)
                if os.access(obj_hexdigest, os.R_OK):
                    with open(obj_hexdigest, 'rb') as obj_stream:
                        tools.cat_stream(obj_stream, out_stream)
                else:
                    tools.cat_stream(in_stream, out_stream)

    def ds_init(self):
        if not self.store or self._force:
            self.set_credentials()
        if not self.store:
            tools.Console.info('failed to access storage; token invalid?')
            sys.exit(1)
        else:
            self.ds_install()
            self.ds_delta()

    def ds_check(self, init=False):
        tag = self.git_config('dropshare.account', None)
        if not self.store or tag is None:
            tools.Console.write(f' \u2717 dropshare not configured yet?...')
            sys.exit(1)
        tools.Console.write(f' \u2713 found dropshare account = {tag}')
        missing = False
        for key in self.DS_KEYS:
            val = self.git_config('--global', f'dropshare.{tag}.{key}')
            if val is None:
                missing = True
                tools.Console.write(f' \u2717 dropshare.{tag}.{key} is not set')
            else:
                tools.Console.write(f' \u2713 dropshare.{tag}.{key} = {val}')
        if missing:
            tools.Console.write(f' * call "git-ds init" first!')

    def ds_track(self):
        self.ds_add_pattern([x.strip() for x in self._match])

    def ds_delta(self):
        changed, deleted, inserted = self.dbx.delta()
        if changed:
            tools.Console.info(f' * {len(deleted)} deleted, {len(inserted)} updated.')

    def ds_log(self):
        for fname in self._paths:
            if not os.access(fname, os.R_OK):
                tools.Console.write(f' \u2717 file {fname} does not exist.')
                return
            entries = []
            for tree in self.git.log("--pretty=format:%T", fname).split('\n'):
                for _, sha in self.git_ls_tree('-r', tree, fname):
                    for timestamp, dir_, _, _, user in self.ds_manifest(sha, reverse=True):
                        dt_local = tools.local_date(timestamp)
                        dt_fmt = dt_local.strftime("%A %d %B %Y, %X")
                        arrow = '\u2191' if dir_ == 'push' else '\u2193'
                        entries.append((dt_local, sha[:6], dt_fmt, arrow, dir_, user))
            sentries = sorted(entries, key=operator.itemgetter(0), reverse=True)
            for _, sha, date, arrow, direction, user in sentries:
                tools.Console.write(f' {arrow} ({sha}) {date} - {direction}ed by {user}.')

    def ds_show(self):
        from subprocess import call

        if os.access(self._filename, os.R_OK):
            call("xdg-open {}".format(self._filename), shell=True)
        else:
            tools.Console.write(f' \u2717 dropshare: file not found "{self._filename}".')
