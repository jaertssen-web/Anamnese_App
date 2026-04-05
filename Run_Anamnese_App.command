#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Run_Anamnese_App.command
#
# Dubbelklikbare launcher voor macOS Finder.
# Eerste keer: rechtermuisknop → Openen (Gatekeeper omzeilen).
# ─────────────────────────────────────────────────────────────────────────────

SELF="$(cd "$(dirname "$0")" && pwd)"
exec "${SELF}/scripts/bootstrap_and_run.sh"
