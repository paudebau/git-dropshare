# Copyright 2018 Philippe Audebaud <paudebau@gmail.com>

# This software falls under the GNU general public license, version 3 or later.
# It comes WITHOUT ANY WARRANTY WHATSOEVER.
# You should have received a copy of the license which the software.
# If not, see http://www.gnu.org/licenses/gpl-3.0.html

WHEELS = 'dist'
PACKAGE = 'git_dropshare'

all: install
	@echo 'Run $HOME/.local/bin/git-ds --help for help.'

wheel:
	@/bin/rm -f $(WHEELS)/git_dropshare*
	pip wheel . --wheel-dir $(WHEELS)

install: wheel
	pip install $(WHEELS)/$(PACKAGE)-*.whl --user
	@echo 'The package has installed in the USER environment;'
	@echo 'Check pip install --help for other installation options.'

typing:
	@python3 -m mypy --ignore-missing-imports $(HOME)/.local/bin/git-dsx

upload: install
	@twine upload -r pypi $(WHEELS)/$(PACKAGE)-*.whl
