#!/bin/sh
set -eu
MW_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$MW_DIR/retail_app/start.sh"
