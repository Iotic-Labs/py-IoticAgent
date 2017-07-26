#!/bin/bash
# sudo pip3 install pdoc
# Ensure generated document order is consistent
export PYTHONHASHSEED=0
echo "Building docs... html -> doc/IoticAgent"
rm -r docs/*
pdoc --html --html-dir docs --overwrite src/IoticAgent/ --template-dir pdoctemplates/
pushd docs
mv IoticAgent/* .
rm -r IoticAgent
popd
