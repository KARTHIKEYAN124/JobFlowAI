#!/bin/sh
set -eu

n8n import:workflow --separate --input=/workflows

if [ "${N8N_AUTO_ACTIVATE:-false}" = "true" ]; then
  n8n update:workflow --all --active=true
  echo "Imported and activated JobFlow workflows."
else
  echo "Imported JobFlow workflows as inactive. Test credentials, then set N8N_AUTO_ACTIVATE=true and rerun."
fi
