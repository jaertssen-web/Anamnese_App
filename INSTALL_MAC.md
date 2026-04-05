# Installatie op macOS — Anamnese_App

Minimale installatie: alleen Python 3 + Homebrew nodig. Geen Ollama vereist.

---

## Stap 1 — Homebrew (als nog niet aanwezig)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew --version
```

---

## Stap 2 — Python 3

```bash
brew install python3
python3 --version    # verwacht: 3.10 of hoger
```

---

## Stap 3 — App starten

### Optie A — dubbelklik (aanbevolen)

1. Open `Anamnese_App/` in Finder
2. Rechtermuisknop op `Run_Anamnese_App.command`
3. Kies **Openen** (eerste keer, Gatekeeper omzeilen)
4. Daarna gewoon dubbelklikken

Het script regelt automatisch:
- `.venv` aanmaken
- `streamlit` installeren
- App starten op poort 8503

### Optie B — terminal

```bash
cd "/pad/naar/Anamnese_App"
bash scripts/bootstrap_and_run.sh
```

---

## Stap 4 — App openen

Ga naar: **http://localhost:8503**

---

## Drie apps tegelijk

Alle apps draaien op verschillende poorten:

| App | Poort | Doel |
|---|---|---|
| PatientData_Preprocessing | 8501 | Anonymisering (backend) |
| Anamnese_Anonymizer | 8502 | Anonymisering (UI) |
| Anamnese_App | 8503 | Spreekuurtool |

---

## Probleemoplossing

### Gatekeeper blokkeert .command
```bash
xattr -d com.apple.quarantine "/pad/naar/Run_Anamnese_App.command"
```

### Poort 8503 bezet
```bash
lsof -ti:8503 | xargs kill -9
```

### App herinstalleren
```bash
rm -rf .venv
bash scripts/bootstrap_and_run.sh
```

---

## Systeemvereisten

| Component | Minimum |
|---|---|
| macOS | 12 Monterey |
| Python | 3.10 |
| RAM | 4 GB |
| Schijfruimte | 200 MB |
| Ollama | niet vereist (v1) |
