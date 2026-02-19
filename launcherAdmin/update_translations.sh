#!/bin/bash

# Ask user for language code (e.g., it, fr, es)
read -p "Enter language code (e.g. it, fr, es): " lang

# Define the output path
output_file="translations/${lang}.ts"

# Ensure translations directory exists
mkdir -p translations

# Run pylupdate6
pylupdate6 \
  main.py \
  windows/*.py \
  widgets/*.py \
  workers/*.py \
  -ts "$output_file"

echo "✅ Translation file created at: $output_file"