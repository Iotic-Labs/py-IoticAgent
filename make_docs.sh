#!/bin/bash
# sudo pip3 install pdoc
echo "Building docs... html -> doc/IoticAgent" 
pdoc --html --html-dir doc --overwrite src/IoticAgent/
