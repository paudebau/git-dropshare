# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license with the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

import os
import sys
import re
# import itertools
import time

import git
from git.exc import GitCommandError

from . import tools

class Repo(object):

    ATTR_LOCS = ['.gitattributes', '.git/info/attributes']
    DS_FILT = re.compile(r'^([^\s]*)\s+filter=dropshare\s*$')
    DS_REF_NOTES = 'refs/notes/dropshare'

    __instance = None
    _repository = '.' # repository location

    git = None
    toplevel_dir = '.'
    git_directory = '.git'
    config_filename = None

    def __new__(cls):
        if Repo.__instance is None:
            Repo.__instance = object.__new__(cls)
        return Repo.__instance

    def __init__(self):
        if not os.path.exists(self._repository):
            tools.Console.write(f' \u2717 non existent directory {self._repository}.\n')
            sys.exit(0)
        self.toplevel_dir = self._repository
        if not os.path.exists(os.path.join(self.toplevel_dir, '.git')):
            tools.Console.write(' \u2717 git: no repository found; run git init?\n')
            sys.exit(1)
        self.git = git.Git(self.toplevel_dir)
        self.git_directory = self.git.rev_parse(git_dir=True)
        self.config_filename = os.path.join(self.toplevel_dir, '.dropshare')
        os.makedirs(os.path.join(self.git_directory, 'dropshare'), exist_ok=True)

    # Git calls
    def git_ls_tree(self, *args, **kwargs):
        for res in self.git.ls_tree(*args, **kwargs).split('\n'):
            if res.strip():
                meta, fname = res.split('\t')
                _, _, sha = meta.split(' ')
                yield (fname, sha)

    def git_identity(self):
        try:
            return (self.git.config("user.name"), self.git.config("user.email"))
        except:
            return ('Anonymous', 'somebody@from.somewhere.else')

    def git_config(self, *args, default=None, **kwargs):
        try:
            return self.git.config(*args, **kwargs)
        except GitCommandError:
            return default

    # Dropshare specific

    def ds_stub(self, sha):
        return tools.ds_stub_string(self.git.show(sha))

    def ds_push_notes(self, remote='origin'):
        tools.Console.write(f" * push ds notes to {remote}... ")
        try:
            self.git.push(remote, Repo.DS_REF_NOTES)
        except GitCommandError as exc:
            if exc.stderr:
                if 'failed to push' in exc.stderr:
                    self.ds_notes("append", 'HEAD', '--message', f'dropshare initialisation')
                    self.git.push(remote, Repo.DS_REF_NOTES)
                elif 'read only' in exc.stderr:
                    tools.Console.write(' \u2717 push ds notes error: git repository read only.\n')
        tools.Console.write('done\n')

    def ds_pull_notes(self, remote='origin', initial=False):
        tools.Console.write(f" * pull ds notes from {remote}...")
        try:
            if initial:
                self.git.fetch("origin", f"{Repo.DS_REF_NOTES}:{Repo.DS_REF_NOTES}")
            else:
                self.git.fetch(remote, f"{Repo.DS_REF_NOTES}:{Repo.DS_REF_NOTES}-{remote}", "--force")
        except GitCommandError:
            pass
        else:
            self.ds_notes("merge", '--strategy', 'cat_sort_uniq', f"{Repo.DS_REF_NOTES}-{remote}")
        tools.Console.write("done\n")

    def ds_notes(self, *args, **kwargs):
        return self.git.notes('--ref=dropshare', *args, **kwargs)

    def ds_append_note(self, sha, direction, hexdigest, fname):
        user, _ = self.git_identity()
        self.ds_notes("append", sha, '--message', f'{time.time()}\t{direction}\t{hexdigest}\t{fname}\t{user}')

    def ds_manifest(self, sha, reverse=False):
        try:
            notes = self.ds_notes('show', sha)
        except GitCommandError:
            yield from []
        else:
            if notes:
                notes = [x for x in notes.strip().split('\n') if x.strip()]
                if reverse:
                    notes.reverse()
                # returns (timestamp, direction, hexdigest, path, user) tuples
                yield from [x.split('\t') for x in notes]
            else:
                yield from []

    def ds_has_note(self, sha, fname, hexdigest, path):
        manifest = list(self.ds_manifest(sha, reverse=True))
        for _, direction, hexdigest_, path_, _ in manifest:
            if direction == 'push' and hexdigest == hexdigest_:
                return True
        return False

    def check_filters(self):
        for val in ('clean', 'smudge'):
            if self.git_config(f'filter.dropshare.{val}') != f'git-ds filter-{val} -f %f':
                return False
        return True

    def ds_ready(self):
        try:
            if not self.check_filters():
                tools.Console.write(' \u2717 git-ds: not initialised; run git-ds init.\n')
                sys.exit(1)
        except GitCommandError:
            pass

    def ds_install(self):
        self.git_config('notes.rewriteRef', Repo.DS_REF_NOTES)
        self.ds_pull_notes(initial=True)
        for val in ('clean', 'smudge'):
            self.git_config(f"filter.dropshare.{val}", f"git-ds filter-{val} -f %f")

    DS_RE = re.compile(r'^dropshare\.([^.]+).([^.]+)=(.*)$')
    def list_credentials(self):
        accounts = dict()
        for line in self.git.config('--global', '--list').split('\n'):
            match = Repo.DS_RE.match(line)
            if match:
                tag = match.group(1).strip()
                key = match.group(2).strip()
                val = match.group(3).strip() if match.group(3) else None
                if tag not in accounts:
                    accounts[tag] = {'description': 'No description provided',
                                     'token': None, 'root_path': None}
                accounts[tag][key] = val
        return accounts

    def ds_add_pattern(self, pattern, path=None):
        if path is None:
            path = Repo.ATTR_LOCS[0]
        if not os.path.exists(path):
            tools.Console.write(f' \u2717 path {path} not found.\n')
            return

        with open(path, "w+t") as attr_stream:
            for line in attr_stream.readlines():
                if not line.startswith('#'):
                    match = Repo.DS_FILT.match(line)
                    if match and match.group(1) == pattern:
                        tools.Console.write(f' \u2713 pattern {pattern} already tracked.\n')
                        break
            else:
                attr_stream.write(f'{pattern} filter=dropshare\n')
                tools.Console.write(f' \u2713 pattern {pattern} is now tracked.\n')

    def _ds_patterns(self, paths):
        for path in [os.path.join(self.toplevel_dir, x) for x in paths]:
            if os.path.exists(path):
                for line in open(path, "r+t").readlines():
                    if not line.startswith('#'):
                        match = Repo.DS_FILT.match(line)
                        if match:
                            regex = tools.fnmatch_normalize(match.group(1))
                            if regex:
                                yield regex

    def filtered_by_attributes(self, match=[]):
        patterns = list(self._ds_patterns(Repo.ATTR_LOCS))
        selected = re.compile('|'.join(filter(None.__ne__, map(tools.fnmatch_normalize, match))))
        if not patterns:
            tools.Console.write(" \u2717 Found no dropshare rules...\n")
            yield from []
        pat_re = re.compile('|'.join(patterns))
        items = self.git_ls_tree('HEAD', r=True)
        for fname, sha in items:
            if pat_re.match(fname):
                if not match or selected.match(fname):
                    stub = self.ds_stub(sha)
                    if stub:
                        yield (sha, fname, stub)
