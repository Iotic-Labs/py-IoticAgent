#!/bin/bash
# sudo pip3 install pdoc
echo "Building docs... html -> doc/IoticAgent"
rm -r docs/*
pdoc --html --html-dir docs --overwrite src/IoticAgent/ --template-dir pdoctemplates/
pushd docs
mv IoticAgent/* .
rm -r IoticAgent
popd
