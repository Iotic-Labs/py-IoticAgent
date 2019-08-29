#!/bin/bash
set -eu

# Follow setup instructions as per sphinx-doc readme.
echo "Building docs... html -> doc/IoticAgent"
rm -rf docs/*
pushd sphinx-doc
make html
mv _build/html/* ../docs
popd
