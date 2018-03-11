# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license with the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

import os
import sys
import posixpath # for Dropbox API
import re
import time
import hashlib
from contextlib import contextmanager

from git.exc import GitCommandError

import yaml # fixme json!

from . import tools, repo

try:
    import dropbox
except ImportError:
    tools.Console.write('fatal: "dropbox" module missing...\n')
    sys.exit(1)
else:
    from dropbox.files import WriteMode
    from dropbox.exceptions import ApiError, HttpError
    from dropbox.files import FileMetadata, DeletedMetadata

class DropboxContentHasher(object):
    """ From https://github.com/dropbox/dropbox-api-content-hasher """
    BLOCK_SIZE = 4 * 1024 * 1024

    def __init__(self):
        self._overall_hasher = hashlib.sha256()
        self._block_hasher = hashlib.sha256()
        self._block_pos = 0
        self.digest_size = self._overall_hasher.digest_size

    def update(self, new_data):
        # assert isinstance(new_data, bytes), "Expecting a byte string, got {type(new_data)}"
        new_data_pos = 0
        while new_data_pos < len(new_data):
            if self._block_pos == self.BLOCK_SIZE:
                self._overall_hasher.update(self._block_hasher.digest())
                self._block_hasher = hashlib.sha256()
                self._block_pos = 0
            space_in_block = self.BLOCK_SIZE - self._block_pos
            part = new_data[new_data_pos:(new_data_pos+space_in_block)]
            self._block_hasher.update(part)
            self._block_pos += len(part)
            new_data_pos += len(part)

    def _finish(self):
        if self._block_pos > 0:
            self._overall_hasher.update(self._block_hasher.digest())
            self._block_hasher = None
        hasher = self._overall_hasher
        self._overall_hasher = None  # Make sure we can't use this object anymore.
        return hasher

    def hexdigest(self):
        return self._finish().hexdigest()

    # def digest(self):
    #     return self._finish().digest()

    # def copy(self):
    #     c = ContentHasher.__new__(ContentHasher)
    #     c._overall_hasher = self._overall_hasher.copy()
    #     c._block_hasher = self._block_hasher.copy()
    #     c._block_pos = self._block_pos
    #     return c

@contextmanager
def apply_request(message):
    start = time.time()
    try:
        yield
    except HttpError as err:
        tools.Console.write(f' \u2717 HTTP error {err}\n')
    except ApiError as err:
        if err.error.is_path() and err.error.get_path().reason.is_insufficient_space():
            tools.Console.write(' \u2717 insufficient space on account.\n')
        elif err.user_message_text:
            tools.Console.write(f" \u2717 {err.user_message_text}\n")
        else:
            tools.Console.write(f" \u2717 API error {err}\n")
        sys.exit(1)
    finally:
        stop = time.time()
        tools.Console.write(f' \u2713 {message} took {stop - start:.3f} seconds\n')

class HashTable(object):
    _ht = None
    _ht_ver = "1"
    _ht_loc = None

    def __init__(self, gitdir):
        self._ht = None
        self._ht_loc = os.path.join(gitdir, 'dropshare', 'hash_table.yml')
        self.load()

    @property
    def hash_table(self):
        if self._ht is None:
            self.load()
        return self._ht

    @staticmethod
    def init():
        return {"version": HashTable._ht_ver,
                "dropbox_id": None,
                "sharing": dict(),
                "cursor": None,
                "dirs": dict(), "files": dict()}

    def load(self):
        if not os.path.exists(self._ht_loc):
            self._ht = HashTable.init()
        else:
            with open(self._ht_loc, 'rt') as stream:
                self._ht = yaml.load(stream, Loader=yaml.Loader)
                return
            if self._ht.get("version", "none") != HashTable._ht_ver:
                tools.Console.write(f'ds database upgraded to {HashTable._ht_ver}\n')
                self._ht["version"] = HashTable._ht_ver
                self._ht['cursor'] = None
        self.save()

    def save(self):
        with open(self._ht_loc, 'wt') as stream:
            stream.write(yaml.dump(self._ht, default_flow_style=False))

class Storage(HashTable):

    mode = WriteMode.add

    def __init__(self, gitdir, root_path='', token=None):
        super(Storage, self).__init__(gitdir)
        self.db_client = None
        self.db_path = '/' + posixpath.normpath(root_path.strip('/'))
        if token:
            self.db_client = dropbox.Dropbox(token)
        if self.db_client:
            self.update_id_info()

    @staticmethod
    def sharing_info(entry):  # fixme
        if hasattr(entry, 'sharing_info'):
            return dict()
        else:
            return None

    @staticmethod
    def account_info(entry):
        return {'abbreviated_name': entry.name.abbreviated_name,
                'display_name': entry.name.display_name,
                'email': entry.email}

    # BasicAccount(account_id='',
    #   name=Name(given_name='', surname='', familiar_name='', display_name='', abbreviated_name=''),
    #   email='', email_verified=True, disabled=False, is_teammate=True, team_member_id=None,
    #   profile_photo_url=''

    @staticmethod
    def file_info(entry):
        sharing_info = Storage.sharing_info(entry)
        return {'id': entry.id,
                'rev': entry.rev,
                'size': entry.size,
                'modified': entry.client_modified,
                'sharing_info': sharing_info}

    # FileMetadata(name='', id='', rev='', size=0, content_hash=''
    # client_modified=datetime.datetime(*), server_modified=datetime.datetime(*),
    # path_lower='', path_display='',
    # parent_shared_folder_id=None, media_info=None, sharing_info=None, property_groups=None,
    # has_explicit_shared_members=None

    @contextmanager
    def local_path(self, path):
        try:
            yield path[len(self.db_path)+1:]
        finally:
            pass

    @contextmanager
    def remote_path(self, path):
        try:
            yield posixpath.normpath(posixpath.join(self.db_path, path.strip('/')))
        finally:
            pass

    def download(self, out_stream, obj, path):
        with apply_request(f"dn {path} from {obj}"):
            with self.remote_path(obj) as remote:
                meta = self.db_client.files_download_to_file(out_stream.name, remote)
                out_stream.seek(0)
                return Storage.file_info(meta) if meta else None

    def upload(self, in_stream, obj, path):
        with apply_request(f"up {path} as {obj}"):
            data = in_stream.read() # fixme gerer barriere 150Mo
            with self.remote_path(obj) as remote:
                meta = self.db_client.files_upload(data, remote, mode=Storage.mode)
                return Storage.file_info(meta) if meta else None

    def infos(self, obj):
        with self.remote_path(obj) as remote:
            return self.db_client.files_get_metadata(remote)

    def exists(self, obj):
        return obj in self.hash_table['files']

    def get_id_info(self, account_id):
        if "sharing" not in self.hash_table:
            self.hash_table["sharing"] = dict()
        if account_id in self.hash_table["sharing"]:
            return self.hash_table["sharing"][account_id]
        info = Storage.account_info(self.db_client.users_get_account(account_id))
        self.hash_table["sharing"][account_id] = info
        return info

    def update_id_info(self):
        if not self.hash_table.get("dropbox_id", None):
            account = self.db_client.users_get_current_account()
            self.hash_table["dropbox_id"] = account.account_id
            return self.get_id_info(account.account_id)

    def get_state(self, cursor_val):
        if cursor_val is None:
            tools.Console.write('dropshare initial synchronization!\n')
            return self.db_client.files_list_folder(self.db_path, recursive=True, include_deleted=True)
        return self.db_client.files_list_folder_continue(cursor_val)

    def delta(self):
        cursor_previous = cursor_val = self.hash_table["cursor"]
        changes, deleted, inserted = 0, dict(), dict()
        with apply_request(f"delta()"):
            has_more = True
            while has_more:
                try:
                    state = self.get_state(cursor_val)
                    items_count = len(state.entries)
                    for entry in state.entries:
                        with self.local_path(entry.path_display) as path:
                            if isinstance(entry, DeletedMetadata):
                                deleted[path] = entry.name
                                if path in self.hash_table['files']:
                                    del self.hash_table['files'][path]
                            elif isinstance(entry, FileMetadata):
                                # tools.Console.write(f' * in {path}\n')
                                val = Storage.file_info(entry)
                                inserted[path] = val
                                self.hash_table['files'][path] = val
                except dropbox.exceptions.ApiError as err:
                    tools.Console.write(f'listing failed -- {str(err)}\n')
                    return (False, 0, 0)
                changes += items_count
                cursor_val = state.cursor
                has_more = state.has_more

        if changes > 0 and cursor_previous != cursor_val:
            self.hash_table["cursor"] = cursor_val
            self.save()
        return (changes > 0, deleted, inserted)

class BackendException(Exception):
    def __init__(self, message):
        super().__init__()
        self.message = message

class Backend(repo.Repo):
    """dropshare backend"""

    store = False
    dbx = None

    def __init__(self):
        super(Backend, self).__init__()
        root_path, token = self.get_credentials()
        if not root_path:
            root_path = ''
        self.hasher = DropboxContentHasher
        if tools.reachable():
            self.dbx = Storage(self.git_directory, root_path, token)
            self.store = self.dbx is not None
        else:
            tools.Console.write('Unable to connect Dropbox servers.\n')
            self.store = False

    DS_KEYS = ('root-path', 'token')
    def get_credentials(self, tag=None):
        try:
            if tag is None:
                tag = self.git.config('dropshare.account')
            return map(lambda key: self.git.config(f'dropshare.{tag}.{key}'), Backend.DS_KEYS)
        except GitCommandError:
            self.set_credentials()

    DS_RE = re.compile(r'^dropshare\.([^.]+).([^.]+)=(.*)$')
    def list_credentials(self):
        accounts = dict()
        for line in self.git.config('--global', '--list').split('\n'):
            match = Backend.DS_RE.match(line)
            if match:
                tag = match.group(1).strip()
                key = match.group(2).strip()
                val = match.group(3).strip() if match.group(3) else None
                if tag not in accounts:
                    accounts[tag] = {'description': 'No description provided',
                                     'token': None, 'root_path': None}
                accounts[tag][key] = val
        return accounts

    def set_credentials(self):
        data = self.list_credentials()
        selected, accounts = None, data.keys()
        tools.Console.write("Choose an account (or 0 to enter a new one.\n")
        choices = dict((str(choice), tag) for choice, tag in enumerate(accounts, 1))
        tag, dic = None, dict()
        for choice, tag in choices.items():
            tools.Console.write(f"  ({choice}) {tag}: {data[tag]['description']}\n")
        tools.Console.write(f"  (0) NEW ACCOUNT\n")
        while selected != '0' and selected not in choices.keys():
            selected = input("Enter your choice here: ")
            print(type(selected), selected, selected in choices.keys())

        if selected in choices.keys():
            dic = choices[selected]
        else:
            tools.Console.write("\n = Dropbox Share Credentials:\n")
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
    def data_location(hexdigest):
        try:
            yield posixpath.join(hexdigest[:2], hexdigest[2:4], hexdigest)
        finally:
            pass

    def data_exists(self, hexdigest):
        tools.Console.write(f" * exists {hexdigest}?\n")
        with Backend.data_location(hexdigest) as obj:
            return self.dbx.exists(obj)

    def data_push(self, in_stream, hexdigest, path, special=False):
        with Backend.data_location(hexdigest) as obj:
            if not self.dbx.exists(obj):
                tools.Console.write(f" * push {path} filter={special}\n")
                if self.dbx.upload(in_stream, obj, path):
                    return True
                raise BackendException(f' \u2717 fails to upload {path}.\n')
            return False

    def data_pull(self, out_stream, hexdigest, path, special=False):
        with Backend.data_location(hexdigest) as obj:
            if self.dbx.exists(obj):
                tools.Console.write(f" * pull {path} {hexdigest} filter={special}\n")
                if self.dbx.download(out_stream, obj, path):
                    return True
                raise BackendException(f' \u2717 fails to download {path}.\n')
            raise BackendException(f' \u2717 file {path} NOT found remotely.\n')
