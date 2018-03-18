# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license with the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

import posixpath # for Dropbox API
from contextlib import contextmanager
from typing import List, Generator, Optional, Dict, IO

from git.exc import GitCommandError

from . import tools, repo
from .store import DropboxContentHasher, Storage

class BackendException(Exception):
    def __init__(self, message):
        super().__init__()
        self.message = message

class Backend(repo.Repo):
    """dropshare backend"""

    store = False # type: bool
    dbx = None # type: Optional[Storage]

    def __init__(self):
        super().__init__()
        root_path, token = self.get_credentials()
        if not root_path:
            root_path = ''
        self.hasher = DropboxContentHasher
        if tools.reachable():
            self.dbx = Storage(self.git_directory, root_path, token)
            self.store = self.dbx is not None
        else:
            tools.Console.info('Unable to connect Dropbox servers.')
            self.store = False

    DS_KEYS = ('root-path', 'token')
    def get_credentials(self, tag : Optional[str] = None) -> List[str]:
        try:
            if tag is None:
                tag = self.git.config('dropshare.account')
            return list(map(lambda key: self.git.config(f'dropshare.{tag}.{key}'), Backend.DS_KEYS))
        except GitCommandError:
            self.set_credentials()
            return []

    def set_credentials(self):
        data = self.list_credentials()
        selected, accounts = None, data.keys()
        tools.Console.write('Choose an account (or 0 to enter a new one.\n')
        choices = dict((str(choice), tag) for choice, tag in enumerate(accounts, 1))
        tag, dic = None, dict()
        for choice, tag in choices.items():
            tools.Console.write(f'  ({choice}) {tag}: {data[tag]["description"]}\n')
        tools.Console.write(f'  (0) NEW ACCOUNT')
        while selected != '0' and selected not in choices.keys():
            selected = input("Enter your choice here: ")
        if selected in choices.keys():
            dic = choices[selected]
        else:
            tools.Console.write('\n = Dropbox Share Credentials:\n')
            while True:
                tag = input(' * choose a FRESH account name: ').strip()
                if tag and tag not in accounts:
                    break
            root_path = input(' * Share base path relative to Dropbox root: ')
            token = input(" * Dropbox access token: ")
            description = input(' * Short description: ')
            self.git.config('--global', f'dropshare.{tag}.description', description)
            self.git.config('--global', f'dropshare.{tag}.root-path', root_path)
            self.git.config('--global', f'dropshare.{tag}.token', token)
            dic = {'description': description, 'token': token, 'root_path': root_path}
            self.git.config('dropshare.account', tag)

        self.git.config('dropshare.account', tag)
        self.dbx = Storage(self.git_directory, dic['root_path'], dic['token'])
        self.store = self.dbx is not None

    @staticmethod
    @contextmanager
    def data_location(hexdigest : str) -> Generator[str, None, None]:
        try:
            yield posixpath.join(hexdigest[:2], hexdigest[2:4], hexdigest)
        finally:
            pass

    def data_exists(self, hexdigest : str) -> bool:
        tools.Console.info(f' * exists {hexdigest}?')
        with Backend.data_location(hexdigest) as obj:
            return self.dbx.exists(obj)

    def data_push(self, in_stream : IO[bytes], hexdigest : str, path : str, special=False) -> bool:
        with Backend.data_location(hexdigest) as obj:
            if not self.dbx.exists(obj):
                tools.Console.info(f' * push {path} filter={special}')
                if self.dbx.upload(in_stream, obj, path):
                    return True
                raise BackendException(f' \u2717 fails to upload {path}.')
            return False

    def data_pull(self, out_stream : IO[bytes], hexdigest : str, path : str, special=False) -> bool:
        with Backend.data_location(hexdigest) as obj:
            if self.dbx.exists(obj):
                tools.Console.info(f' * pull {path} {hexdigest} filter={special}')
                if self.dbx.download(out_stream, obj, path):
                    return True
                raise BackendException(f' \u2717 fails to download {path}.')
            raise BackendException(f' \u2717 file {path} NOT found remotely.')
