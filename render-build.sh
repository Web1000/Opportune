#!/usr/bin/env bash
# Render build script. Installs Python deps and the Tectonic LaTeX engine
# (Linux x86_64) so the tailored-resume PDF endpoint works on the server.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# --- Tectonic LaTeX engine -------------------------------------------------
# config.py auto-detects ./bin/tectonic, so no env var is needed once it's here.
mkdir -p bin
if [ ! -x bin/tectonic ]; then
  echo "Downloading Tectonic 0.16.9 (Linux x86_64)..."
  curl -fsSL "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.16.9/tectonic-0.16.9-x86_64-unknown-linux-gnu.tar.gz" \
    | tar -xz -C bin
  chmod +x bin/tectonic
fi
echo "Tectonic installed:"
bin/tectonic --version
