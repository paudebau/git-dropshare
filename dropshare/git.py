# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license with the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

from abc import ABCMeta, abstractmethod
from typing import NewType, Optional, Tuple, List, Dict, Callable, Any, Iterable, TypeVar, Union, cast, Generic

Sha = NewType('Sha', str)
Ref = NewType('Ref', str)
Branch = NewType('Branch', str)
BaseBranch = NewType('BaseBranch', Branch)
Owner = NewType('Owner', str)
Remote = NewType('Remote', str)
Commitish = Union[Sha,Ref,Branch,BaseBranch]
T = TypeVar('T')

from git import Git as GitCli
from git import Repo as GitRepo
from git.exc import GitCommandError

EMPTY_TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904' # git empty commit tree

__all__ = ['Sha', 'GitCmd', 'GitCli', 'GitCommandError']

class GitCmd(metaclass=ABCMeta):
    @abstractmethod
    def config(self, *args: str, **kwargs: str) -> Optional[str]: pass
    @abstractmethod
    def notes(self, *args: str) -> str: pass
    @abstractmethod
    def show(self, sha: Sha) -> str: pass
    @abstractmethod
    def rev_list(self, **kwargs: bool) -> str: pass
    @abstractmethod
    def rev_parse(self, **kwargs: str) -> str: pass
    @abstractmethod
    def get_object_header(self, sha: Sha) -> str: pass
    @abstractmethod
    def ls_files(self, str) -> str: pass
    @abstractmethod
    def ls_tree(self, str) -> str: pass
    @abstractmethod
    def add(self, str) -> str: pass
    @abstractmethod
    def pull(self, *args: str) -> None: pass
    @abstractmethod
    def fetch(self, *args: str) -> None: pass
    @abstractmethod
    def push(self, *args: str) -> None: pass
    @abstractmethod
    def checkout_index(self, str, **kwargs: bool) -> None: pass
    @abstractmethod
    def log(self, *args: str) -> str: pass
    @abstractmethod
    def log(self, *args: str) -> str: pass
    @abstractmethod
    def status(self) -> str: pass
