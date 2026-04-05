# Anamnese_App

Spreekuurtool voor gestructureerde pijnanamnese tijdens consult.

**Geen LLM, geen Ollama, geen klinische analyse.**
Klinische analyse en DD zijn geparkeerd in `future/` voor v2+.
De basisdekking-coach (v1.2) is actief — zie sectie hieronder.

---

## Architectuur

```
Consult (Anamnese_App)
        ↓ export .md
Anonymisering (Anamnese_Anonymizer → PatientData_Preprocessing)
        ↓
Online AI / EPD
```

**Strikte scheiding:**
- `Anamnese_App` — spreekuurtool, draait lokaal, geen netwerk
- `Anamnese_Anonymizer` — veiligheidslaag, leunt op `PatientData_Preprocessing`
- `PatientData_Preprocessing` — backend anonymisering, wordt NOOIT geïmporteerd in Anamnese_App

---

## Snel starten

```bash
# Dubbelklik in Finder:
Run_Anamnese_App.command

# Of via terminal:
bash scripts/bootstrap_and_run.sh
```

Open: **http://localhost:8503**

---

## Workflow v1

1. **Sidebar** — patiënt-ID + datum invullen (maakt consultmap aan)
2. **Patiëntgegevens** — initialen, leeftijd, geslacht
3. **HPI** — begin, beloop, provocatie, verlichting, functionele impact
4. **Pijnkenmerken** — locaties, NRS, karakter, referred pain, slaap
5. **Mechanisme** — handmatige inschatting dominant mechanisme
6. **Medicatie** — relevant (naam · dosering · startdatum)
7. **Plan** — diagnostiek, voorlichting, niet-farm., farm., interventioneel
8. **Vrije notities** — plak transcript of aanvullingen
9. **Dekkingsmeter** — checkt 8 verplichte kernvelden (leeg / twijfelachtig / bruikbaar)
10. **Basisdekking gesprek** — coach signaleert open anamnese-onderdelen (9 kern + 6 experimenteel)
11. **Export** — download `.md` of sla op in consultmap

---

## Dekkingsmeter

Verplichte kernvelden (uit `knowledge/required_fields.json`):

| Veld | Sectie |
|---|---|
| `HPI.begin` | HPI |
| `HPI.beloop` | HPI |
| `HPI.provocatie` | HPI |
| `HPI.verlichting` | HPI |
| `pijn.locaties` | Pijnkenmerken |
| `pijn.intensiteit_NRS` | Pijnkenmerken |
| `pijn.karakter` | Pijnkenmerken |
| `mechanisme_suspect.dominant` | Mechanisme |

Exporteren is altijd mogelijk, ook als velden leeg zijn (met waarschuwing).

---

## Opslag

Consulten worden lokaal opgeslagen:
```
data/
└── patienten/
    └── {patiënt-id}/
        └── {datum}/
            ├── state.json         ← alle veldwaarden
            └── exports/
                └── {datum}_{id}_{initialen}_anamnese.md
```

---

## Basisdekking-coach (v1.2)

De coach beoordeelt per kernonderwerp of voldoende informatie beschikbaar is.
Hij scant alle aanwezige tekst: handmatig ingevulde velden, transcript en notities.

### Doel

Tijdens het spreekuur signaleren welke anamnese-onderdelen nog onderbelicht zijn,
zodat de arts gericht een vervolgvraag kan stellen. De coach is een hintlaag —
geen klinische interpretatie, geen mechanisme-classificatie, geen differentiaaldiagnose.

### Kernset (9 topics)

| Topic | Veldbron |
|---|---|
| Intensiteit | `pijn.intensiteit_NRS` |
| Begin en duur | `HPI.begin` |
| Beloop | `HPI.beloop` |
| Provocatie | `HPI.provocatie` |
| Verlichting | `HPI.verlichting` |
| Functie en activiteiten | `HPI.functionele_impact` |
| Slaap | `pijn.slaapverstoring` |
| Stemming en cognities | `psychosociaal.notities` |
| Hulpvraag en verwachting | *(geen veld — alleen keywords)* |

### Scores per topic

| Status | Betekenis |
|---|---|
| ✅ voldoende | Drie of meer signalen aanwezig (veldscore + keyword-groepshits ≥ 3) |
| ⚠️ deels | Één of twee signalen — onderwerp aangestipt maar niet volledig |
| ❌ onvoldoende | Geen signaal — vervolgvraag wordt getoond |

Scoring: `veldscore` (bruikbaar=2, twijfelachtig=1, leeg=0) + unieke keyword-groepshits.
Elke keyword-groep levert maximaal 1 punt, ongeacht hoeveel woorden matchen.

### Experimentele topics (collapsed, niet meegeteld in kernset)

Zes topics worden als experimenteel getoond omdat ze bekende beperkingen hebben:
`pijnkarakter`, `medicatie`, `lokalisatie`, `hoofdklacht`, `reden van consult`,
`eerdere behandeling`.

Voornaamste reden: **negaties worden niet herkend**. "Geen brandende pijn" triggert
het keyword "brandend" toch. Dit is een fundamentele beperking van keyword-heuristiek
die niet oplosbaar is zonder LLM.

### Bekende beperkingen

1. **Negaties** — "geen pijn bij bewegen" telt mee als provocatie-signaal.
2. **Woordvolgorde** — "slaapt slecht" en "slecht slapen" zijn aparte keywords;
   alleen bekende varianten worden herkend.
3. **Compound-woorden** — "slaapproblemen" matcht niet automatisch op "slaap".
4. **Sprekerattributie** — artsnotities en patiëntuitspraken worden niet onderscheiden.
5. **Context** — twee keywords in één zin tellen elk mee, ook als ze tegenstrijdig zijn.

### Wanneer wordt een LLM-coach zinvol?

De heuristische coach is voldoende als hulpmiddel voor **aanwezigheidsdetectie**:
is een onderwerp wel of niet ter sprake gekomen?

Een LLM-coach wordt zinvol zodra je ook **interpretatie** nodig hebt:
- Onderscheid tussen echte en ontkende informatie ("geen pijn" ≠ pijn)
- Beoordeling of een antwoord klinisch adequaat is, niet alleen aanwezig
- Mechanisme-inschatting op basis van combinatie van bevindingen
- Sprekerattributie (arts vs. patiënt)

De architectuur (`domain/coach_backend.py`) is voorbereid voor deze wissel:
vervang `HeuristicCoach` door `LLMCoach` in `get_coach()` zonder UI-aanpassing.
Zie `future/PARKEER_NOTITIE.md` voor de parkeernotitie over de LLM-variant.

---

## Geparkeerd voor v2+

- LLM-coach (Ollama/MLX — vervangt heuristische coach via `get_coach()`)
- Validators (DD-kwaliteitscheck, rode-vlaggen-detectie)
- LLM-analyse (multi-agent EFIC/IASP mechanisme-classificatie)

Zie `future/PARKEER_NOTITIE.md`.
