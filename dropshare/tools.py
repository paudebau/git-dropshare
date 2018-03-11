# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license with the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

import sys
import os.path
import re
import fnmatch
import io
import socket
from contextlib import contextmanager

from datetime import datetime
import pytz
import dateutil.tz

class Console:
    write = lambda msg: sys.stderr.write(msg)
    flush = lambda: sys.stderr.flush()

DS_HEAD = b'dropshare\n'
DS_WRITE = lambda hexdigest, path: f'dropshare\n{path}\n{hexdigest}\n'.encode()
DS_READ = re.compile(b'^dropshare\n([^\n]+)\n([0-9A-Za-z]+)$', re.M)

class Peeker:
    """Wrapper for stdin that implements proper peeking
from https://stackoverflow.com/questions/14283025/python-3-reading-bytes-from-stdin-pipe-with-readahead """
    def __init__(self, stream):
        self.stream = stream
        self.buf = io.BytesIO()

    def _append_to_buf(self, contents):
        oldpos = self.buf.tell()
        self.buf.seek(0, io.SEEK_END)
        self.buf.write(contents)
        self.buf.seek(oldpos)

    def _buffered(self):
        oldpos = self.buf.tell()
        data = self.buf.read()
        self.buf.seek(oldpos)
        return data

    def peek(self, size):
        buf = self._buffered()[:size]
        if len(buf) < size:
            contents = self.stream.read(size - len(buf))
            self._append_to_buf(contents)
            return self._buffered()
        return buf

    def read(self, size=None):
        if size is None:
            contents = self.buf.read() + self.stream.read()
            self.buf = io.BytesIO()
            return contents
        contents = self.buf.read(size)
        if len(contents) < size:
            contents += self.stream.read(size - len(contents))
            self.buf = io.BytesIO()
        return contents

    def read_as_blocks(self, block_size=None):
        if block_size is None:
            block_size = BLOCK_SIZE
        return iter(lambda: self.read(block_size), b'')

    def ds_is_stub(self):
        return self.peek(len(DS_HEAD)) == DS_HEAD

    def ds_stub(self):
        match = DS_READ.match(self.peek(250)) # 10 + 64 + max size of path
        if match is None:
            return None
        return (match.group(2).decode(), match.group(1).decode())

    # def readline(self):
    #     line = self.buf.readline()
    #     if not line.endswith(b'\n'):
    #         line += self.stream.readline()
    #         self.buf = io.BytesIO()
    #     return line

    def close(self):
        self.buf = None
        self.stream = None

@contextmanager
def scanner(stream):
    """returns a stdin reader with proper peek"""
    reader = Peeker(stream)
    try:
        yield reader
    finally:
        reader.close()

def ds_stub_string(text):
    with io.BytesIO(text.strip().encode()) as txt_stream:
        with scanner(txt_stream) as stream:
            return stream.ds_stub()


BLOCK_SIZE = 128*1024
def read_as_blocks(stream):
    return iter(lambda: stream.read(BLOCK_SIZE), b'')

IDENTITY = lambda x: x
def cat_stream(in_stream, out_stream, action=IDENTITY):
    for block in read_as_blocks(in_stream):
        out_stream.write(action(block))

def hash_cat_stream(in_stream, out_stream, hash_function):
    for block in read_as_blocks(in_stream):
        hash_function.update(block)
        out_stream.write(block)
    out_stream.seek(0)
    return hash_function.hexdigest()

def hash_file(filename, hash_function):
    if not os.path.exists(filename):
        return ''
    with open(filename, 'rb') as in_stream:
        for block in read_as_blocks(in_stream):
            hash_function.update(block)
        return hash_function.hexdigest()

# int(self.date.replace(tzinfo=datetime.timezone.utc).timestamp())
# DT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
def local_date(timestamp):
    utc_dt = datetime.fromtimestamp(float(timestamp), tz=pytz.timezone("UTC"))
    return utc_dt.astimezone(dateutil.tz.tzlocal())

# Host: 8.8.8.8 (google-public-dns-a.google.com), OpenPort: 53/tcp
def reachable(host="8.8.8.8", port=53, timeout=3):
    if isinstance(port, str):
        port = int(port)
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception:
        return False

# Copied from https://swarm.workshop.perforce.com/projects/richard_brooksby-ravenbrook-git-fusion/
# Extends python fnmatch to suit fnmatch(3) properly

# single * matches anything but /
SINGLE_STAR_RE = re.compile(r'([^*])\.\*([^*])')
SINGLE_STAR_REPL = r'\1[^/]*\2'
# leading **/...
LEADING_DOUBLE_STAR_RE = re.compile(r'^\.\*\.\*\\/')
LEADING_DOUBLE_STAR_REPL = r'([^/]*/)?'
# internal ../**/...
INTERNAL_DOUBLE_STAR_RE = re.compile(r'\/\.\*\.\*\/')
INTERNAL_DOUBLE_STAR_REPL = r'.*'
# trailing .../**
TRAILING_DOUBLE_STAR_RE = re.compile(r'\/\.\*\.\*$')
TRAILING_DOUBLE_STAR_REPL = r'/.+'
# no / matches basename
NO_SLASH_RE = r'(.*/)?'

def path_matches_pattern(path, pattern):
    """Return True if path matches the LFS filter pattern.

    See gitignore and gitattributes documentation for more on this.
    """
    # gitignore documentation to the contrary notwithstanding, a pattern ending
    # with '/' matches nothing when used for gitattributes.
    if pattern.endswith('/'):  # directory pattern
        return False

    # Git documentation quoted here:
    #
    # Git treats the pattern as a shell glob suitable for consumption by
    # fnmatch(3) with the FNM_PATHNAME flag: wildcards in the pattern will not
    # match a / in the pathname.
    #
    # However, Python's fnmatch does not support FNM_PATHNAME, so use fnmatch to
    # create a regex from pattern and then modify it as needed.
    regex = fnmatch.translate(pattern)
    if '/' in pattern:
        regex = re.sub(SINGLE_STAR_RE, SINGLE_STAR_REPL, regex)
        regex = re.sub(LEADING_DOUBLE_STAR_RE, LEADING_DOUBLE_STAR_REPL, regex)
        regex = re.sub(INTERNAL_DOUBLE_STAR_RE, INTERNAL_DOUBLE_STAR_REPL, regex)
        regex = re.sub(TRAILING_DOUBLE_STAR_RE, TRAILING_DOUBLE_STAR_REPL, regex)
    else:
        regex = NO_SLASH_RE + regex
    return bool(re.match(regex, path))

def fnmatch_normalize(pattern):
    if pattern.endswith('/'):  # directory pattern
        return None
    regex = fnmatch.translate(pattern)
    if '/' in pattern:
        regex = re.sub(SINGLE_STAR_RE, SINGLE_STAR_REPL, regex)
        regex = re.sub(LEADING_DOUBLE_STAR_RE, LEADING_DOUBLE_STAR_REPL, regex)
        regex = re.sub(INTERNAL_DOUBLE_STAR_RE, INTERNAL_DOUBLE_STAR_REPL, regex)
        return re.sub(TRAILING_DOUBLE_STAR_RE, TRAILING_DOUBLE_STAR_REPL, regex)
    return NO_SLASH_RE + regex
