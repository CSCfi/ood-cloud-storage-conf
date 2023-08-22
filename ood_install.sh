#!/bin/bash

bin/python -m pip install --prefix="$PWD/deps" --ignore-installed --upgrade pip
bin/python -m pip install --prefix="$PWD/deps" --ignore-installed -r requirements.txt
