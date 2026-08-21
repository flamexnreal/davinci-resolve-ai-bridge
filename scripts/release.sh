#!/usr/bin/env bash
# Automated release script for davinci-resolve-ai-bridge-mcp
set -e

VERSION=$1
if [ -z "$VERSION" ]; then
  echo "Usage: ./scripts/release.sh <version> (e.g. ./scripts/release.sh 1.5.1)"
  exit 1
fi

echo "=== Building Production Assets ==="
npm run build

echo "=== Syncing Local Runtime ==="
cp bridge/operations.py ~/.resolve-ai-bridge/bridge/operations.py 2>/dev/null || true
cp bridge/audio_analysis.py ~/.resolve-ai-bridge/bridge/audio_analysis.py 2>/dev/null || true
cp bridge/frame_capture.py ~/.resolve-ai-bridge/bridge/frame_capture.py 2>/dev/null || true

echo "=== Publishing to npm ==="
npm publish --access public

echo "=== Release $VERSION Complete & Live! ==="
