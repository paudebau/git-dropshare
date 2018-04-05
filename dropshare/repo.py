# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license with the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

import os
import sys
import re
import time
from typing import List, Optional, Union, Tuple, Iterable, Dict

from . import tools
from .git import GitRepo, GitCli, GitCommandError
from .git import GitCmd, Sha # for type checking

class Repo(object):

    ATTR_LOCS = ['.gitattributes', '.git/info/attributes']
    DS_FILT = re.compile(r'^([^\s]*)\s+filter=dropshare\s*$')
    DS_REF_NOTES = 'refs/notes/dropshare'

    __instance = None # type: Optional[Repo]
    _repository = '.' # type: str # repository location
    toplevel_dir = '.'

    git = None # type: Optional[GitCmd]
    git_repo = None # type: Optional[GitRepo]
    git_directory = '.git' # may be redirected via gitdir

    def __new__(cls):
        if Repo.__instance is None:
            Repo.__instance = object.__new__(cls)
        return Repo.__instance

    def __init__(self):
        if not os.path.exists(self._repository):
            tools.Console.info(f' \u2717 non existent directory {self._repository}.')
            sys.exit(0)
        self.toplevel_dir = self._repository
        if not os.path.exists(os.path.join(self.toplevel_dir, '.git')):
            tools.Console.info(' \u2717 git: no repository found; run git init?')
            sys.exit(1)
        self.git = GitCli(self.toplevel_dir)
        self.git_repo = GitRepo(self.toplevel_dir)
        self.git_directory = self.git.rev_parse(git_dir=True)
        self.obj_directory = os.path.join(self.git_directory, 'dropshare', 'objects')
        os.makedirs(self.obj_directory, exist_ok=True)

    # Git calls
    def git_ls_tree(self, *args, **kwargs):
        for res in self.git.ls_tree(*args, **kwargs).split('\n'):
            if res.strip():
                meta, fname = res.split('\t')
                _, _, sha = meta.split(' ')
                yield (fname, sha)

    def git_identity(self) -> Tuple[str, str]:
        try:
            return (self.git.config("user.name"), self.git.config("user.email"))
        except:
            return ('Anonymous', 'somebody@from.somewhere.else')

    def git_config(self, *args, default: Optional[str] = None, **kwargs) -> Optional[str]:
        try:
            return self.git.config(*args, **kwargs)
        except GitCommandError:
            return default

    # Dropshare specific

    def ds_stub(self, sha: Sha) -> Optional[Tuple[str, str]]:
        return tools.ds_stub_string(self.git.show(sha))

    def ds_push_notes(self, remote='origin'):
        # tools.Console.info(f' * push ds notes to {remote}... ')
        try:
            self.git.push(remote, Repo.DS_REF_NOTES)
        except GitCommandError as exc:
            if exc.stderr:
                if 'failed to push' in exc.stderr:
                    self.ds_notes("append", 'HEAD', '--message', f'dropshare initialisation')
                    self.git.push(remote, Repo.DS_REF_NOTES)
                elif 'read only' in exc.stderr:
                    tools.Console.warning(' \u2717 push ds notes error: git repository read only.')
        # tools.Console.info('done')

    def ds_pull_notes(self, remote='origin', initial=False):
        # tools.Console.info(f' * pull ds notes from {remote}...')
        try:
            if initial:
                self.git.fetch("origin", f"{Repo.DS_REF_NOTES}:{Repo.DS_REF_NOTES}")
            else:
                self.git.fetch(remote, f"{Repo.DS_REF_NOTES}:{Repo.DS_REF_NOTES}-{remote}", "--force")
        except GitCommandError:
            pass
        else:
            self.ds_notes("merge", '--strategy', 'cat_sort_uniq', f"{Repo.DS_REF_NOTES}-{remote}")
        # tools.Console.info('done')

    def ds_notes(self, *args) -> str:
        return self.git.notes('--ref=dropshare', *args)

    def ds_append_note(self, sha: Sha, direction: str, hexdigest: str, fname: str):
        user, _ = self.git_identity()
        self.ds_notes("append", sha, '--message', f'{time.time()}\t{direction}\t{hexdigest}\t{fname}\t{user}')

    def ds_manifest(self, sha: Sha, reverse=False) -> Iterable[List[str]]:
        try:
            notes = self.ds_notes('show', sha)  # type: str
        except GitCommandError:
            yield from []
        else:
            if not notes:
                yield from []
            lnotes = [x for x in notes.strip().split('\n') if x.strip()] # type: List[str]
            if reverse:
                lnotes.reverse()
            yield from [x.split('\t') for x in lnotes]

    def ds_has_note(self, sha: Sha, fname: str, hexdigest: str, path: str) -> bool:
        manifest = self.ds_manifest(sha, reverse=True)
        for _, direction, hexdigest_, _, _ in manifest:
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
                tools.Console.info(' \u2717 git-ds: not initialised; run git-ds init.')
                sys.exit(1)
        except GitCommandError:
            pass

    def ds_install(self):
        self.git_config('notes.rewriteRef', Repo.DS_REF_NOTES)
        self.ds_pull_notes(initial=True)
        for val in ('clean', 'smudge'):
            self.git_config(f"filter.dropshare.{val}", f"git-ds filter-{val} -f %f")

    DS_RE = re.compile(r'^dropshare\.([^.]+).([^.]+)=(.*)$')
    def list_credentials(self) -> Dict[str, Dict[str, str]]:
        accounts = dict() # type: Dict[str, Dict[str, str]]
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

    def ds_add_pattern(self, patterns: List[str], path: Optional[str] = None):
        pattern = patterns[0]
        if not pattern:
            tools.Console.info(f' \u2717 empty pattern {pattern}?')
            return
        if path is None:
            path = Repo.ATTR_LOCS[0]
        if not os.path.exists(path):
            tools.Console.info(f' \u2717 path {path} not found.')
            return
        attributes = open(path, 'rt').readlines()
        for line in attributes:
            if not line.startswith('#'):
                match = Repo.DS_FILT.match(line)
                if match and match.group(1) == pattern:
                    tools.Console.info(f' \u2713 pattern "{pattern}" already tracked.')
                    break
        else:
            attributes.append(f'{pattern} filter=dropshare')
            with open(path, "w+t") as attr_stream:
                attr_stream.write('\n'.join(attributes))
            tools.Console.info(f' \u2713 pattern {pattern} is now tracked.')

    def _ds_patterns(self, paths: List[str]):
        for path in [os.path.join(self.toplevel_dir, x) for x in paths]:
            if os.path.exists(path):
                for line in open(path, "r+t").readlines():
                    if not line.startswith('#'):
                        match = Repo.DS_FILT.match(line)
                        if match:
                            regex = tools.fnmatch_normalize(match.group(1))
                            if regex:
                                yield regex

    def filtered_by_attributes(self, match: List[str] = []) -> Iterable[Tuple[str, str, str]]:
        patterns = list(self._ds_patterns(Repo.ATTR_LOCS))
        selected = re.compile('|'.join(filter(None.__ne__, map(tools.fnmatch_normalize, match))))
        if not patterns:
            tools.Console.info(' \u2717 Found no dropshare rules...')
            yield from []
        pat_re = re.compile('|'.join(patterns))
        items = self.git_ls_tree('HEAD', r=True)
        for fname, sha in items:
            if pat_re.match(fname):
                if not match or selected.match(fname):
                    try:
                        stub = self.ds_stub(sha)
                    except UnicodeEncodeError:
                        pass
                    else:
                        if stub:
                            yield (sha, fname, stub[0])

    # Dropshare staging management

    def ds_staging_objects(self):
        return set(os.listdir(self.obj_directory))

    def ds_orphan_files(self) -> Iterable[Tuple[str, str]]:
        for path in self.git.ls_files(self.toplevel_dir).split('\n'):
            stub = tools.ds_stub_file(path)
            if stub:
                yield stub

    def ds_referenced_objects(self, full=True) -> Union[Iterable[Tuple[str, str]], Iterable[str]]:
        for line in self.git.rev_list(objects=True, all=True).split('\n'):
            try:
                sha = line[:40]
                _, obj_type, size = self.git.get_object_header(sha)
                if obj_type != b'blob' or int(size) >= 250: # fixme tools.ds_stub max size
                    continue
            except  ValueError:
                pass
            else:
                try:
                    hexdigest, path = tools.ds_stub_string(self.git.show(sha))
                except:
                    pass
                else:
                    yield (hexdigest, path) if full else hexdigest
