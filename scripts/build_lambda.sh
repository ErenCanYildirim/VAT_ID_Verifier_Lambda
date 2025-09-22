#!/bin/bash

echo "Building Lambda package..."

rm -rf lambda_package
mkdir lambda_package

cp lambda_function.py lambda_package/

pip install requests==2.31.0 -t lambda_package/

echo "Lambda package ready"