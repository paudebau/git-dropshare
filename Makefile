# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license which the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

# N.B. The installation is made in USER environment

ROOT = $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
WHEELS  = $(ROOT)dist
VERSION = $(shell python3 -c 'import dropshare;print(dropshare.__version__)')
SOURCES = $(wildcard $(ROOT)dropshare/*.py)
PACKAGE = $(WHEELS)/git_dropshare-$(VERSION)-py3-none-any.whl
INSTALL = $(HOME)/.local/lib/python3.6/site-packages/git_dropshare-$(VERSION).dist-info/RECORD

.PHONY: all
all: $(INSTALL)
	@echo 'Run $(HOME)/.local/bin/git-ds --help.'

.PHONY: upload
upload: $(PACKAGE)
	@twine upload -r pypi $(PACKAGE)

.PHONY: typing
typing:
	@python3 -m mypy --ignore-missing-imports $(HOME)/.local/bin/git-dsx

$(PACKAGE): $(SOURCES)
	@echo "Build $(PACKAGE) ..."
	@pip wheel . --wheel-dir $(WHEELS)

$(INSTALL): $(PACKAGE)
	@pip install $(PACKAGE) --user
	@echo 'Package installed in the USER environment;'
	@echo 'Check pip install --help for other options.'
