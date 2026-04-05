# Geparkeerd materiaal voor v2+

Deze map bevat componenten die bewust buiten v1 zijn gelaten.
Ze zijn klaar voor gebruik zodra de basisapp stabiel is.

## Inhoud

| Bestand | Doel | Wanneer activeren |
|---|---|---|
| `coach_system_full.txt` | Coach-prompt: één vraag + checklist missende velden | v2: coach-knop in UI |
| `coach_system_short.txt` | Coach-prompt: één vraag (compact) | v2: variant voor snelle modus |
| `validators.py` | DD-kwaliteitsvalidatie, rode-vlaggen-detectie, broncheck | v2: na invoer mechanisme_suspect |
| `prompts_yaml_improved.txt` | Volledige multi-agent EFIC/IASP prompt-suite | v3: LLM-analyse module |

## Wat ontbreekt voor activatie

- **coach**: Ollama-client (requests), prompt-rendering in sidebar, open-fields-hint doorgeven
- **validators**: koppeling aan state na opslaan, UI voor waarschuwingen tonen
- **prompts_yaml**: Agent-orchestratie, LLM-response-parsing, output-schema-validatie

## Bewust NIET in v1

- Geen LLM/Ollama (geen requests-dependency in v1)
- Geen mechanisme-classificatie door AI
- Geen DD-generatie
- Geen rode-vlaggen-LLM-check
- Geen transcript-lezer (NDJSON)
- Geen autorefresh

PatientData_Preprocessing wordt NOOIT geïmporteerd in Anamnese_App.
Anonymisering is een losse stap na export, in Anamnese_Anonymizer.
