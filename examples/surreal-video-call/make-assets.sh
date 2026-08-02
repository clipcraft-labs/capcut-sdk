#!/bin/sh
set -eu
command -v rsvg-convert >/dev/null 2>&1 || {
  echo "rsvg-convert is required (macOS: brew install librsvg)" >&2
  exit 1
}
for name in intro incoming accepting connected; do
  rsvg-convert -w 1080 -h 1920 "assets/$name.svg" -o "assets/$name.png"
done
