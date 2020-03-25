# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
.PHONY: login ling_scripts lint_dockers lint test help

SHELL=bash
BASH_FUNC_retry%%=() { \
	i=0; \
	while [ $$i -lt 9 ]; do \
		"$$@" && return || { echo "$$@ failed, retrying after 30s..." 1>&2; sleep 30; }; \
		i="$${i+1}"; \
	done; \
	"$$@"; \
}
export BASH_FUNC_retry%%

login: ## Login to Docker Hub
	docker login --username="$(DOCKER_USER)"

lint_scripts: ## Lint shellscripts
	retry docker pull koalaman/shellcheck:latest
	find . -not -path '*/\.*' \
		-exec /bin/bash -c '[ $$(file -b --mime-type {}) == "text/x-shellscript" ]' /bin/bash '{}' ';' \
		-print | xargs docker run --rm -v "$(PWD)":/mnt koalaman/shellcheck:latest -x -a -Calways

lint_dockers: ## Lint Dockerfiles
	retry docker pull hadolint/hadolint:latest
	find . -type f -name "Dockerfile" ! -path '*/windows/*' | xargs docker run --rm -v "$(PWD)":/mnt -w /mnt hadolint/hadolint:latest hadolint \
		--ignore DL3002 \
		--ignore DL3003 \
		--ignore DL3007 \
		--ignore DL3008 \
		--ignore DL3009 \
		--ignore DL3013 \
		--ignore DL3018 \
		--ignore DL4001 \
		--ignore DL4006 \
		--ignore SC2086

lint: lint_scripts lint_dockers

test:
	docker run --rm \
		-v /var/run/docker.sock:/var/run/docker.sock \
		-v "$(PWD)/base/fuzzos/tests":/tests \
		gcr.io/gcp-runtimes/container-structure-test:latest \
			test \
			--quiet \
			--image mozillasecurity/fuzzos:latest \
			--config /tests/fuzzos_metadata_test.yaml \
			--config /tests/fuzzos_command_test.yaml

help: ## Show this help message.
	@echo 'Usage: make [command] ...'
	@echo
	@echo "Available commands:"
	@grep -E "^(.+)\:\ ##\ (.+)" ${MAKEFILE_LIST} | column -t -c 2 -s ":#"
