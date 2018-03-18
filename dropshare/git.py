# -*- coding: utf-8 -*-

# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license with the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

#import git
from git import Git
from git.exc import GitCommandError
from typing import Optional, Dict
from abc import ABCMeta, abstractmethod

__all__ = ['Sha', 'GitCmd', 'GitCommandError']

Sha = str

class GitCmd(metaclass=ABCMeta):
    @abstractmethod
    def config(self, *str, **kwargs : Dict[str, str]) -> Optional[str]: pass
    @abstractmethod
    def notes(self, *str) -> str: pass
    @abstractmethod
    def show(self, sha: Sha) -> str: pass
    @abstractmethod
    def rev_list(self, **bool) -> str: pass
    @abstractmethod
    def rev_parse(self, **str) -> str: pass
    @abstractmethod
    def get_object_header(self, sha : Sha) -> str: pass
    @abstractmethod
    def ls_files(self, str) -> str: pass
    @abstractmethod
    def ls_tree(self, str) -> str: pass
    @abstractmethod
    def add(self, str) -> str: pass
    @abstractmethod
    def pull(self, *str) -> None: pass
    @abstractmethod
    def fetch(self, *str) -> None: pass
    @abstractmethod
    def push(self, *str) -> None: pass
    @abstractmethod
    def checkout_index(self, str, **bool) -> None: pass
    @abstractmethod
    def log(self, *str) -> str: pass
