#!/bin/bash
# This script installs psycopg2 with system dependencies
set -e

# Install system dependencies
apt-get update
apt-get install -y libpq-dev python3-dev

# Install psycopg2
pip install psycopg2-binary
