#!/bin/bash -exu

# Exit because PRs do not have access to secrets.
# The MonorepoManager executes a PR build though but does prevent a push for PRs.
if [ "$TRAVIS_PULL_REQUEST" != "false" ]; then
 exit 0
fi

sudo apt-get install -y -qq --no-install-recommends --no-install-suggests pass

# Download the latest version of `docker-credential-pass`
LATEST_VERSION=$(curl -s "https://github.com/docker/docker-credential-helpers/releases/latest" | grep -o 'tag/[v.0-9]*' | awk -F/ '{print $2}')
echo "$LATEST_VERSION"
curl -LO "https://github.com/docker/docker-credential-helpers/releases/download/$LATEST_VERSION/docker-credential-pass-$LATEST_VERSION-amd64.tar.gz"
tar xvf "docker-credential-pass-$LATEST_VERSION-amd64.tar.gz"
sudo mv docker-credential-pass /usr/local/bin

# Setup a dummy secret key for the `pass` credentials store initialization required by the Docker client.
GPG_TTY="$(tty)" gpg2 --batch --gen-key <<-EOF
%echo Generating a standard key
Key-Type: DSA
Key-Length: 1024
Subkey-Type: ELG-E
Subkey-Length: 1024
Name-Real: Christoph Diehl
Name-Email: cdiehl@mozilla.com
Expire-Date: 0
%commit
%echo done
EOF

key=$(gpg2 --no-auto-check-trustdb --list-secret-keys | grep ^sec | cut -d/ -f2 | cut -d" " -f1)
pass init "$key"

mkdir -p ~/.docker
echo '{"credsStore": "pass"}' > ~/.docker/config.json
chmod 0600 ~/.docker/config.json

# Pass the encrypted DOCKER_PASS to the `docker` client. Encrypted in the build logs.
# Uses previously setup `credsStore` in ~/.docker/config.json as credentials store.
# We perform a `docker logout` after the session in Travis ends.
echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
