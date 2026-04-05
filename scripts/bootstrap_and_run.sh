#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# bootstrap_and_run.sh  —  Anamnese_App
#
# Maakt .venv klaar, installeert dependencies en start de Streamlit-app.
# Werkt zonder hardcoded paden. Werkt met spaties in pad (iCloud Drive).
#
# Gebruik:
#   bash scripts/bootstrap_and_run.sh
#
# Dubbelklikken via Finder:
#   Run_Anamnese_App.command
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Paden ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"
REQUIREMENTS="${REPO_ROOT}/requirements.txt"
APP_SCRIPT="${REPO_ROOT}/app/main.py"

# ── Kleuren ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[bootstrap]${NC} $*"; }
warn() { echo -e "${YELLOW}[bootstrap]${NC} $*"; }
err()  { echo -e "${RED}[bootstrap]${NC} $*" >&2; }

# ── Homebrew paths (Apple Silicon + Intel) ───────────────────────────────────
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:${PATH}"

echo ""
log "Anamnese_App — bootstrap"
log "Repo root: ${REPO_ROOT}"
echo ""

cd "${REPO_ROOT}"

# ── Python 3 ─────────────────────────────────────────────────────────────────
if ! command -v python3 > /dev/null 2>&1; then
    err "Python 3 niet gevonden. Installeer via: brew install python3"
    exit 1
fi
log "Python: $(python3 --version)"

# ── requirements.txt ─────────────────────────────────────────────────────────
if [ ! -f "${REQUIREMENTS}" ]; then
    err "requirements.txt niet gevonden: ${REQUIREMENTS}"
    exit 1
fi

# ── Virtuele omgeving ────────────────────────────────────────────────────────
if [ ! -d "${VENV_DIR}" ]; then
    log "Virtuele omgeving aanmaken (.venv)..."
    python3 -m venv "${VENV_DIR}"
fi

log "Virtuele omgeving activeren..."
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

log "pip upgraden..."
pip install --quiet --upgrade pip

log "Dependencies installeren..."
pip install --quiet -r "${REQUIREMENTS}"
log "Dependencies klaar."
echo ""

# ── Streamlit ────────────────────────────────────────────────────────────────
log "Streamlit starten..."
log "Open in browser: http://localhost:8503"
echo ""

# Poort 8503: naast PatientData_Preprocessing (8501) en Anamnese_Anonymizer (8502).
PYTHONPATH="${REPO_ROOT}" streamlit run "${APP_SCRIPT}" \
    --server.port 8503 \
    --server.headless false \
    --browser.gatherUsageStats false
