#!/bin/bash

if [ $# != 1 ]
then
    echo "usage: $0 NEW_VERSION"
    exit 1
fi

NEW_VERSION=$1
CURRENT_VERSION=$(cat setup.py | grep -Po "version='\K.*(?=')")
find -name "*.py" -not -path '*/\.*' | parallel sed -i "s#$CURRENT_VERSION#$NEW_VERSION#g" {}
