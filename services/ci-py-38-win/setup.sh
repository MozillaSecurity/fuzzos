#!/bin/sh
set -e -x

# base msys packages
pacman-key --init
pacman-key --populate msys2
pacman --noconfirm -Syu
pacman --noconfirm -Sy \
  mingw-w64-x86_64-curl \
  mingw-w64-x86_64-gcc \
  mingw-w64-x86_64-make \
  mingw-w64-x86_64-python \
  mingw-w64-x86_64-python-pip \
  patch \
  psmisc \
  tar
rm -rf /var/cache/pacman/pkg

python -m pip install pip --upgrade
pip install wheel
pip install tox
rm -rf msys64/mingw64/share/man/ msys64/mingw64/share/doc/ msys64/usr/share/doc/ msys64/usr/share/man/
cp orion/recipes/linux/py-ci.sh .
tar -jcvf msys2.tar.bz2 --hard-dereference msys64 py-ci.sh
killall -TERM gpg-agent
python -V
