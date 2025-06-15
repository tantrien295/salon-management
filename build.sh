#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Initialize database
flask db upgrade

# Install Tailwind CSS
npm install -g tailwindcss
npx tailwindcss -i ./static/css/main.css -o ./static/css/output.css --minify
