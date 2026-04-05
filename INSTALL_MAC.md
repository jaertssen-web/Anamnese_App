# Installatie op macOS — Anamnese_App

Basisinstallatie: Python 3 + Homebrew. Geen Ollama vereist.
Voor audio-transcriptie: ook ffmpeg nodig.

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

## Stap 2b — ffmpeg (vereist voor audio-transcriptie)

```bash
brew install ffmpeg
```

ffmpeg wordt gebruikt door Whisper voor audio-decodering.
Zonder ffmpeg werkt de rest van de app normaal — alleen de audio-upload is uitgeschakeld.

---

## Stap 2c — Microfoontoestemming (voor opnamefunctie)

De opnamefunctie gebruikt de microfoon via de browser. macOS vereist expliciet toestemming.

**Eenmalige instelling:**
1. **macOS Systeeminstellingen → Privacy en beveiliging → Microfoon**
2. Activeer de browser die je gebruikt (Chrome / Firefox / Safari)

**Browsertoestemming:**
- Bij eerste gebruik vraagt de browser automatisch om toestemming
- Klik op "Toestaan"
- Als je per ongeluk hebt geblokkeerd: browserinstellingen → Site-instellingen → Microfoon → toestaan voor `localhost`

**Aanbevolen browser: Chrome.** Safari kan instabiel zijn voor microfoonopname via de MediaRecorder API. Firefox werkt ook.

**Opmerking:** de opname gebeurt volledig lokaal in de browser en op de Mac. Er gaat geen audio naar het internet.

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

## Whisper-modellen

Bij eerste gebruik downloadt Whisper het model automatisch:

| Model | Grootte | Snelheid | Kwaliteit NL |
|---|---|---|---|
| base | 74 MB | snel | goed |
| small | 244 MB | redelijk | beter |
| medium | 769 MB | langzaam op CPU | best voor medisch NL |
| large-v2 | 1.5 GB | traag op CPU | maximaal |

Op Apple Silicon (M1/M2/M3) worden modellen automatisch via Metal (MPS) versneld.

---

## Systeemvereisten

| Component | Minimum | Opmerking |
|---|---|---|
| macOS | 12 Monterey | |
| Python | 3.10 | |
| RAM | 4 GB | 8 GB+ aanbevolen voor medium/large |
| Schijfruimte | 500 MB | inclusief Whisper base-model |
| ffmpeg | vereist voor audio | `brew install ffmpeg` |
| Ollama | niet vereist | LLM-coach geparkeerd voor v2+ |
