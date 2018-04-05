# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license with the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

import posixpath # for Dropbox API
from contextlib import contextmanager
from typing import Tuple, Generator, Optional, Dict, IO

from .git import GitCommandError
from .store import DropboxContentHasher, Storage
from . import tools, repo

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
        self.hasher = DropboxContentHasher
        if tools.reachable():
            self._connect_dropbox()
        else:
            tools.Console.info('Unable to connect Dropbox servers.')
            self.store = False

    DS_KEYS = ('root-path', 'token')
    def _connect_dropbox(self):
        tag, root_path, token = None, '', None
        try:
            tag = self.git.config('dropshare.account')
            root_path = self.git.config(f'dropshare.{tag}.root-path')
            token = self.git.config(f'dropshare.{tag}.token')
        except GitCommandError:
            root_path, token = self.set_credentials()
        finally:
            self.dbx = Storage(self.git_directory, root_path, token)
            self.store = self.dbx is not None

    def set_credentials(self) -> Tuple[str, str]:
        data = self.list_credentials()
        selected, accounts, tag = None, data.keys(), None
        choices = dict((str(choice), tag) for choice, tag in enumerate(accounts, 1))

        tools.Console.write('Choose an account (or 0 to CREATE a fresh one).')
        for choice, tag in choices.items():
            tools.Console.write(f'  ({choice}) {tag}: {data[tag]["description"]}')
        tools.Console.write(f'  (0) NEW ACCOUNT')

        while selected != '0' and selected not in choices.keys():
            selected = input("Enter your choice here: ")
        if selected in choices.keys():
            tag = choices[selected]
            dic = data[tag]
            self.git.config('dropshare.account', tag)
            return dic['root-path'], dic['token']

        tools.Console.write('\n = Dropbox Share Credentials:')
        while True:
            tag = input(' * choose a FRESH account name: ').strip()
            if tag and tag not in accounts:
                break
        description = input(' * Short description: ')
        root_path = input(' * Share base path relative to Dropbox root: ')
        token = input(" * Dropbox access token: ")
        self.git.config('--global', f'dropshare.{tag}.description', description)
        self.git.config('--global', f'dropshare.{tag}.root-path', root_path)
        self.git.config('--global', f'dropshare.{tag}.token', token)
        self.git.config('dropshare.account', tag)
        return root_path, token

    @staticmethod
    @contextmanager
    def data_location(hexdigest: str) -> Generator[str, None, None]:
        try:
            yield posixpath.join(hexdigest[:2], hexdigest[2:4], hexdigest)
        finally:
            pass

    def data_exists(self, hexdigest: str) -> bool:
        # tools.Console.info(f' * exists {hexdigest}?')
        with Backend.data_location(hexdigest) as obj:
            return self.dbx.exists(obj)

    def data_push(self, in_stream: IO[bytes], hexdigest: str, path: str, special=False) -> bool:
        with Backend.data_location(hexdigest) as obj:
            if not self.dbx.exists(obj):
                tools.Console.info(f' * push {path} filter={special}')
                if self.dbx.upload(in_stream, obj, path):
                    return True
                raise BackendException(f' \u2717 fails to upload {path}.')
            return False

    def data_pull(self, out_stream: IO[bytes], hexdigest: str, path: str, special=False) -> bool:
        with Backend.data_location(hexdigest) as obj:
            if self.dbx.exists(obj):
                tools.Console.info(f' * pull {path} filter={special}')
                if self.dbx.download(out_stream, obj, path):
                    return True
                raise BackendException(f' \u2717 fails to download {path}.')
            raise BackendException(f' \u2717 file {path} NOT found remotely.')
