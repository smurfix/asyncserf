
all:
	@echo "Use setup.py directly."
	@exit 1

# need to use python3 sphinx-build
PATH := /usr/share/sphinx/scripts/python3:${PATH}

PACKAGE = aioserf
PYTHON ?= python3
export PYTHONPATH=$(shell pwd)

PYTEST ?= ${PYTHON} $(shell which pytest-3)
TEST_OPTIONS ?= -xvvv --full-trace
PYLINT_RC ?= .pylintrc

BUILD_DIR ?= build
INPUT_DIR ?= docs/source

# Sphinx options (are passed to build_docs, which passes them to sphinx-build)
#   -W       : turn warning into errors
#   -a       : write all files
#   -b html  : use html builder
#   -i [pat] : ignore pattern

SPHINXBUILD ?= sphinx3-build
SPHINXOPTS ?= -a -W -b html
AUTOSPHINXOPTS := -i *~ -i *.sw* -i Makefile*

SPHINXBUILDDIR ?= $(BUILD_DIR)/sphinx/html
ALLSPHINXOPTS ?= -d $(BUILD_DIR)/sphinx/doctrees $(SPHINXOPTS) docs

check:
	flake8 aioserf setup.py tests examples
doc:
	$(SPHINXBUILD) -a $(INPUT_DIR) $(BUILD_DIR)

livehtml: docs
	sphinx-autobuild $(AUTOSPHINXOPTS) $(ALLSPHINXOPTS) $(SPHINXBUILDDIR)

test:
	$(PYTEST) $(PACKAGE) $(TEST_OPTIONS)
tag:
	@-git tag v$(shell python3 setup.py -V)

pypi:   tag
	@if python3 setup.py -V 2>/dev/null | grep -qs + >/dev/null 2>&1 ; \
		then echo "You need a clean, tagged tree" >&2; exit 1 ; fi
	python3 setup.py sdist upload
	## version depends on tag, so re-tagging doesn't make sense

upload: pypi
	git push-all --tags

