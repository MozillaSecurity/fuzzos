#!/bin/bash
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

set -e
set -x
set -o pipefail

# Install taskcluster CLI
cd "${0%/*}"
./taskcluster.sh

# shellcheck source=recipes/linux/common.sh
source "${0%/*}/common.sh"

git init bugmon-tc
(
  cd bugmon-tc
  git remote add -t master origin https://github.com/MozillaSecurity/bugmon-tc.git
  retry git fetch -v --depth 1 --no-tags origin master
  git reset --hard FETCH_HEAD
  pip3 install .
)

# Cleanup grizzly scripts
rm /home/worker/launch-grizzly*

#### Create aritfact directory
mkdir /bugmon-artifacts

#### Fix ownership
chown -R worker:worker /bugmon-artifacts
chown -R worker:worker /home/worker