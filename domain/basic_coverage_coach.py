"""
domain/basic_coverage_coach.py — Anamnese_App  (v1.2)

Heuristische basisdekking-coach (Fase 1 — zonder LLM).

Beoordeelt per kernonderwerp of voldoende informatie aanwezig is,
door alle beschikbare tekst samen te scannen:
  - handmatig ingevulde velden
  - transcript
  - vrije notities

Output per onderwerp: "voldoende" | "deels" | "onvoldoende"
Alleen bij "onvoldoende": één concrete vervolgvraag.

── Topicsets (v1.2) ──────────────────────────────────────────────
KERN (9 topics — betrouwbaar, field-backed of specifieke keywords):
  intensiteit, begin_duur, beloop, provocatie, verlichting,
  slaap, functie, stemming_cognities, hulpvraag

EXPERIMENTEEL (6 topics — ruis-gevoelig, geen veldbacking of
  negatie-probleem — zie EXPERIMENTAL_TOPIC_IDS):
  reden_consult, hoofdklacht, lokalisatie, pijnkarakter,
  eerdere_behandeling, medicatie

──────────────────────────────────────────────────────────────────
BEKENDE BEPERKINGEN (v1, bewust niet opgelost):

1. NEGATIES worden NIET herkend.
   "geen brandend gevoel" triggert toch het keyword "brandend".
   Dit is een fundamentele beperking van keyword-heuristiek.
   Oplossing in v3: LLM-gebaseerde scan.

2. COMPOUND-WOORDEN kunnen worden gemist.
   "slaapproblemen" matcht niet op losse keywords tenzij opgenomen.
   Mitigatie: woordgroepen in keyword-sets opgenomen waar relevant.

3. CONTEXT wordt niet begrepen.
   Twee keywords in dezelfde zin tellen afzonderlijk mee.
   Dit is een hintlaag, geen klinische interpretatie.

4. SPREKERATTRIBUTIE ontbreekt.
   Artsnotities en patiëntuitspraken worden niet onderscheiden.
──────────────────────────────────────────────────────────────────

DIT IS EEN HINTLAAG — geen klinische interpretatie,
geen mechanisme-classificatie, geen differentiaaldiagnose.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.coverage import field_quality


# ---------------------------------------------------------------------------
# Datamodel
# ---------------------------------------------------------------------------

@dataclass
class CoverageCoachResult:
    onderwerp: str           # machine-id (bijv. "lokalisatie")
    label: str               # leesbare naam (bijv. "Lokalisatie")
    status: str              # "voldoende" | "deels" | "onvoldoende"
    reden: str               # korte toelichting
    vervolgvraag: str | None # alleen bij "onvoldoende"
    bron_hits: list[str] = field(default_factory=list)  # gematchte keywords


# ---------------------------------------------------------------------------
# Topicconfiguatie
# ---------------------------------------------------------------------------

@dataclass
class _TopicConfig:
    id: str
    label: str
    field_paths: list[str]          # corresponderende state-velden
    keyword_groups: list[frozenset] # elke set = 1 groepshit bij ≥1 match
    vervolgvraag: str               # bij "onvoldoende"
    deels_hint: str                 # bij "deels"


# Scoringsdrempels
# score = veldscore (bruikbaar=2, twijfelachtig=1) + unieke keyword-groepshits
_THRESHOLD_VOLDOENDE = 3
_THRESHOLD_DEELS = 1

# ---------------------------------------------------------------------------
# Topicsets — kern vs. experimenteel
# ---------------------------------------------------------------------------

#: Topics die field-backed zijn en specifieke keywords hebben.
#: Worden prominent getoond in de UI.
KERN_TOPIC_IDS: frozenset[str] = frozenset({
    "intensiteit",
    "begin_duur",
    "beloop",
    "provocatie",
    "verlichting",
    "slaap",
    "functie",
    "stemming_cognities",
    "hulpvraag",          # geen veldbacking, maar specifieke keywords; bewust kern
})

#: Topics met bekende beperkingen (negatie-probleem, geen veldbacking,
#: of te brede keywords). Worden apart als experimenteel getoond.
EXPERIMENTAL_TOPIC_IDS: frozenset[str] = frozenset({
    "reden_consult",
    "hoofdklacht",
    "lokalisatie",
    "pijnkarakter",
    "eerdere_behandeling",
    "medicatie",
})


_TOPICS: list[_TopicConfig] = [
    _TopicConfig(
        id="reden_consult",
        label="Reden van consult",
        field_paths=[],
        keyword_groups=[
            frozenset({"reden", "aanleiding", "doorgestuurd", "verwezen", "doorverwijzing", "gestuurd door"}),
            frozenset({"vandaag", "afspraak", "consult", "spreekuur", "hier voor"}),
            frozenset({"vraag", "probleem", "last", "moeilijk", "hulp nodig"}),
        ],
        vervolgvraag="Wat is de directe aanleiding voor dit consult vandaag?",
        deels_hint="Reden deels aanwezig.",
    ),
    _TopicConfig(
        id="hoofdklacht",
        label="Hoofdklacht",
        field_paths=["HPI.begin"],
        keyword_groups=[
            frozenset({"pijnklacht", "pijnlijk", "pijnen", "zeer"}),
            frozenset({"klacht", "last van", "hinder", "last"}),
            frozenset({"voornaamste", "hoofdzakelijk", "met name", "vooral", "ergste klacht"}),
        ],
        vervolgvraag="Kunt u in uw eigen woorden omschrijven wat uw voornaamste klacht is?",
        deels_hint="Hoofdklacht deels omschreven.",
    ),
    _TopicConfig(
        id="lokalisatie",
        label="Lokalisatie",
        field_paths=["pijn.locaties"],
        keyword_groups=[
            frozenset({"linker", "rechter", "links", "rechts", "bilateraal", "beide kanten", "beide"}),
            frozenset({"rug", "nek", "schouder", "arm", "been", "voet", "hand", "heup",
                       "knie", "enkel", "bil", "dijbeen", "kuit", "pols",
                       "hoofd", "buik", "borst", "lies", "kruis", "gewricht"}),
            frozenset({"uitstraling", "uitstraalt", "trekt naar", "straalt", "doortrekken", "referred"}),
        ],
        vervolgvraag="Waar zit de pijn precies, en trekt die ergens naartoe?",
        deels_hint="Locatie deels beschreven, uitstraling onduidelijk.",
    ),
    _TopicConfig(
        id="begin_duur",
        label="Begin en duur",
        field_paths=["HPI.begin"],
        keyword_groups=[
            frozenset({"geleden", "jaar geleden", "maanden geleden", "weken geleden", "dagen geleden",
                       "sinds", "twee jaar", "anderhalf jaar", "een jaar", "drie jaar",
                       "beginmoment"}),   # "er is niet één duidelijk beginmoment" — geldig temporeel signaal
            frozenset({"begon", "begonnen", "opeens", "plotseling", "geleidelijk", "sluipend", "ineens",
                       "geleidelijk ontstaan", "langzaam begonnen"}),
            frozenset({"al lang", "altijd", "chronisch", "al jaren", "al maanden", "langdurig", "lang",
                       "aanhoudend"}),     # "aanhoudende pijn" = duur-kenmerk
            frozenset({"na operatie", "na een operatie", "na de operatie",
                       "na een ongeluk", "na een val", "na een blessure",
                       "na een bevalling", "na een ingreep", "na het",
                       "sinds een operatie", "na de ingreep"}),  # "SINDS een operatie" = veelgebruikte NL variant
            # Specifieke duurkwalificatoren ("drie maanden geleden" geeft al group 1 hit via "geleden",
            # deze groep geeft een extra hit voor teksten die wél een getal noemen maar geen temporele werkwoorden.
            frozenset({"drie maanden", "zes maanden", "negen maanden", "twee maanden", "een maand",
                       "drie weken", "zes weken", "enkele weken", "enkele maanden", "twee jaar geleden"}),
        ],
        vervolgvraag="Wanneer zijn de klachten begonnen, en hoe lang heeft u er al last van?",
        deels_hint="Begin/duur deels aanwezig.",
    ),
    _TopicConfig(
        id="beloop",
        label="Beloop",
        field_paths=["HPI.beloop"],
        keyword_groups=[
            frozenset({"progressief", "verslechterd", "erger geworden", "toenemend", "slechter geworden",
                       "geleidelijk erger", "toename", "neemt toe",
                       "neemt het toe"}),  # "bij gebruik neemt het toe" — "het" staat tussen "neemt" en "toe"
            frozenset({"stabiel", "gelijkgebleven", "wisselend", "fluctueert", "pieken en dalen",
                       "wisselt", "wisseling"}),
            frozenset({"beter geworden", "verbeterd", "afgenomen", "minder geworden"}),
            frozenset({"constant", "continu", "altijd aanwezig", "intermitterend", "aanvallen", "episodisch",
                       "aanhoudend"}),
            frozenset({"sindsdien", "in de loop van de tijd", "later ook", "aanvankelijk",
                       "naarmate de tijd", "in de loop der tijd"}),
            # Temporele variatiepatronen: beloop verschilt per dag/moment
            frozenset({"per dag", "in de avond", "'s avonds", "'s morgens", "door de dag",
                       "gedurende de dag"}),
        ],
        vervolgvraag="Hoe is het verloop van de klachten in de tijd: gaat het erger, beter of wisselend?",
        deels_hint="Beloop deels beschreven.",
    ),
    _TopicConfig(
        id="pijnkarakter",
        label="Pijnkarakter",
        field_paths=["pijn.karakter"],
        keyword_groups=[
            frozenset({"brandend", "branderig", "heet gevoel", "branderigheid"}),
            frozenset({"stekend", "schietend", "elektrisch", "elektrische schokken", "prikkelend"}),
            frozenset({"dof", "zeurend", "kloppend", "drukkend", "bonzend", "zwaar gevoel"}),
            frozenset({"tintelend", "tinteling", "doof", "gevoelloos", "slaap in"}),
            frozenset({"krampen", "krampend", "samentrekkend", "spastisch"}),
        ],
        vervolgvraag="Hoe voelt de pijn aan — brandend, stekend, dof, tintelend, of anders?",
        deels_hint="Pijnkarakter deels beschreven.",
    ),
    _TopicConfig(
        id="intensiteit",
        label="Intensiteit",
        field_paths=["pijn.intensiteit_NRS"],
        keyword_groups=[
            frozenset({"nrs", "pijnscore", "schaal van", "cijfer", "een tien", "gemiddeld"}),
            frozenset({"heftig", "erg", "ernstig", "ondraaglijk", "invaliderend", "hevig", "verschrikkelijk",
                       "pieken", "piekpijn"}),
            frozenset({"licht", "matig", "dragelijk", "mild", "beetje pijn", "weinig pijn"}),
            frozenset({"op zijn ergst", "op z'n ergst", "slechte dag", "op de slechte dag",
                       "best zwaar", "niet te harden", "op goede dagen", "op slechte dagen"}),
        ],
        vervolgvraag="Hoe heftig is de pijn gemiddeld? Kunt u een cijfer geven van 0 tot 10?",
        deels_hint="Intensiteit deels aanwezig — NRS ontbreekt of onduidelijk.",
    ),
    _TopicConfig(
        id="provocatie",
        label="Provocatie",
        field_paths=["HPI.provocatie"],
        keyword_groups=[
            frozenset({"erger bij", "slechter bij", "verergert", "neemt toe", "provoceert", "uitlokt", "opkomt bij"}),
            frozenset({"bewegen", "lopen", "staan", "zitten", "liggen", "bukken", "tillen", "draaien"}),
            frozenset({"kou", "koude", "warmte", "aanraking", "druk", "stress", "inspanning"}),
        ],
        vervolgvraag="Wat maakt de pijn erger?",
        deels_hint="Provocerende factoren deels beschreven.",
    ),
    _TopicConfig(
        id="verlichting",
        label="Verlichting",
        field_paths=["HPI.verlichting"],
        keyword_groups=[
            frozenset({"beter bij", "minder bij", "verlicht", "helpt", "vermindering", "neemt af bij"}),
            frozenset({"rust", "rusten", "liggen", "ontspanning", "stilzitten"}),
            frozenset({"warmte", "warm bad", "warme douche", "warmtekussen", "heating"}),
            frozenset({"medicatie", "pijnstiller", "paracetamol", "ibuprofen", "tramadol"}),
        ],
        vervolgvraag="Wat maakt de pijn minder?",
        deels_hint="Verlichtende factoren deels beschreven.",
    ),
    _TopicConfig(
        id="functie",
        label="Functie en activiteiten",
        field_paths=["HPI.functionele_impact"],
        keyword_groups=[
            frozenset({"kan niet meer", "lukt niet", "lukt me niet", "niet meer in staat", "moeite met",
                       "met moeite", "lukt niet meer goed", "heeft moeite", "gaat niet meer"}),
            frozenset({"lopen", "staan", "zitten", "traplopen", "fietsen", "sporten", "werken", "huishouden",
                       "zware taken", "minder uren", "aangepast werk", "parttime"}),
            frozenset({"beperkt", "beperkingen", "invaliderend", "afhankelijk", "hulp nodig", "rolstoel",
                       "aanpassingen", "aanpassen"}),
            frozenset({"nauwelijks", "amper", "slecht", "moeilijk", "niet goed",
                       "nog maar"}),   # "gaat nog maar met moeite" — duidelijke capaciteitsbeperking
        ],
        vervolgvraag="Wat kunt u door de pijn niet meer of nauwelijks doen?",
        deels_hint="Functionele impact deels beschreven.",
    ),
    _TopicConfig(
        id="slaap",
        label="Slaap",
        field_paths=["pijn.slaapverstoring"],
        keyword_groups=[
            frozenset({"slaap", "slapen", "nacht", "nachtelijk", "nachtpijn", "slaapproblemen",
                       "'s nachts", "nachten"}),
            frozenset({"wakker", "wakker worden", "wakker liggen", "doorslapen", "inslapen"}),
            frozenset({"vermoeid", "moe", "uitgeput", "niet uitgerust", "slaaptekort",
                       "slecht geslapen", "onrustige nacht"}),
            frozenset({"moeilijk inslapen", "meerdere keren wakker", "pijnlijk wakker",
                       "geen goede houding", "houding vinden"}),
            # Aparte groep voor woordvolgorde-varianten van "slecht slapen":
            # "slecht slapen" (infinitief) ≠ "slaapt slecht" (persoonsvorm) — beide klinisch relevant
            frozenset({"slecht slapen", "slaapt slecht", "slaap slecht", "slapen slecht"}),
        ],
        vervolgvraag="Heeft de pijn invloed op uw slaap? Wordt u er 's nachts wakker van?",
        deels_hint="Slaap deels aangestipt.",
    ),
    _TopicConfig(
        id="stemming_cognities",
        label="Stemming en cognities",
        field_paths=["psychosociaal.notities"],
        keyword_groups=[
            frozenset({"somber", "depressief", "neerslachtig", "verdrietig", "geen zin meer"}),
            frozenset({"angst", "bang", "piekeren", "stress", "zorgen", "gespannen", "nerveus"}),
            frozenset({"catastroferen", "wordt nooit beter", "hopeloos", "uitzichtloos", "het helpt toch niet"}),
            frozenset({"vermijdt", "durft niet", "bang voor bewegen", "voorzichtig", "bewegen is gevaarlijk"}),
        ],
        vervolgvraag="Hoe gaat het met uw stemming? Heeft de pijn invloed op uw gemoedstoestand?",
        deels_hint="Stemming/cognities deels aangestipt.",
    ),
    _TopicConfig(
        id="eerdere_behandeling",
        label="Eerdere behandeling",
        field_paths=[],
        keyword_groups=[
            frozenset({"fysiotherapie", "fysio", "oefentherapie", "manuele therapie", "revalidatie", "ergotherapie"}),
            frozenset({"behandeld", "behandeling gehad", "therapie gehad", "geprobeerd", "al gedaan"}),
            frozenset({"operatie", "injectie", "blok", "zenuwbehandeling", "chirurgie", "infiltratie"}),
            frozenset({"eerder", "vroeger", "al eens", "daarvoor", "in het verleden"}),
        ],
        vervolgvraag="Heeft u al behandelingen gehad voor deze klacht? Zo ja, welke, en hielp dat?",
        deels_hint="Eerdere behandelingen deels beschreven.",
    ),
    _TopicConfig(
        id="medicatie",
        label="Medicatie",
        field_paths=["medicatie_relevant"],
        keyword_groups=[
            frozenset({"paracetamol", "acetaminophen"}),
            frozenset({"ibuprofen", "naproxen", "diclofenac", "aspirine", "nsaid"}),
            frozenset({"tramadol", "morfine", "oxycodon", "fentanyl", "tapentadol", "opioïd", "opiaat"}),
            frozenset({"pregabalin", "gabapentine", "amitriptyline", "duloxetine", "nortriptyline"}),
            frozenset({"pijnstiller", "medicijn", "medicatie", "tablet", "capsule", "zalf", "pleister"}),
        ],
        vervolgvraag="Welke pijnstillers of andere medicatie gebruikt u momenteel, en helpt dat?",
        deels_hint="Medicatie deels beschreven.",
    ),
    _TopicConfig(
        id="hulpvraag",
        label="Hulpvraag en verwachting",
        field_paths=[],
        keyword_groups=[
            frozenset({"verwacht", "verwachting", "hoop op", "hopen dat", "wil graag",
                       "wil weten", "wil dat", "wil vooral", "hoopt dat"}),
            frozenset({"hulpvraag", "vraag aan u", "vraag aan jou", "zou willen", "nodig hebben",
                       "vraagt of", "vraag of"}),
            frozenset({"diagnose", "weten wat er is", "begrijpen", "uitleg", "verklaring", "oorzaak",
                       "of er nog onderzoek mogelijk is", "of er nog een scan mogelijk is",
                       "wat er aan de hand is"}),
            frozenset({"beter worden", "verbetering", "oplossing", "behandeling starten", "doorverwijzing",
                       "of er nog behandeling mogelijk is", "wat nog mogelijk is",
                       "wat er nog mogelijk is",
                       "behandeling mogelijk",   # "een behandeling mogelijk is" — "of een" breekt de langere zin
                       "pijn minder"}),           # "wil dat de pijn minder alles gaat bepalen"
            # Korte "wat/of er nog"-fragmenten in spreektaal, los van de langere varianten in groep 4
            frozenset({"wat er nog", "of er nog", "of er iets aan", "wat er verder"}),
        ],
        vervolgvraag="Wat verwacht u van dit consult? Wat is uw concrete hulpvraag?",
        deels_hint="Hulpvraag deels aanwezig.",
    ),
]


# ---------------------------------------------------------------------------
# Tekstverzameling
# ---------------------------------------------------------------------------

def _build_scan_text(state: dict) -> str:
    """
    Combineert alle beschikbare tekst uit velden, transcript en notities.
    Retourneert lowercase string voor keyword-matching.

    BEPERKING: negaties worden niet herkend. Zie module-docstring.
    """
    parts: list[str] = []

    for section_key in ("HPI", "pijn", "mechanisme_suspect"):
        section = state.get(section_key, {}) or {}
        for val in section.values():
            if isinstance(val, str) and val:
                parts.append(val)
            elif isinstance(val, list):
                parts.extend(str(v) for v in val if v)

    for item in state.get("medicatie_relevant", []) or []:
        if item:
            parts.append(str(item))

    psych = state.get("psychosociaal", {}) or {}
    if psych.get("notities"):
        parts.append(psych["notities"])

    transcript = state.get("transcript", {}) or {}
    if transcript.get("tekst"):
        parts.append(transcript["tekst"])

    if state.get("notities_vrij"):
        parts.append(state["notities_vrij"])

    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _best_field_quality(state: dict, field_paths: list[str]) -> str:
    if not field_paths:
        return "leeg"
    order = {"bruikbaar": 2, "twijfelachtig": 1, "leeg": 0}
    best = "leeg"
    for path in field_paths:
        q = field_quality(state, path)
        if order[q] > order[best]:
            best = q
    return best


def _count_keyword_hits(scan_text: str, groups: list[frozenset]) -> tuple[int, list[str]]:
    """
    Telt unieke groepshits (max 1 per groep).
    Retourneert (aantal_hits, lijst_van_gematchte_keywords).
    """
    hits = 0
    matched: list[str] = []
    for group in groups:
        for kw in sorted(group):      # deterministisch door sortering
            if kw in scan_text:
                hits += 1
                matched.append(kw)
                break
    return hits, matched


def _evaluate_topic(
    topic: _TopicConfig,
    state: dict,
    scan_text: str,
) -> CoverageCoachResult:
    best_fq = _best_field_quality(state, topic.field_paths)
    veldscore = {"bruikbaar": 2, "twijfelachtig": 1, "leeg": 0}[best_fq]

    kw_hits, matched = _count_keyword_hits(scan_text, topic.keyword_groups)
    total = veldscore + kw_hits

    if total >= _THRESHOLD_VOLDOENDE:
        status = "voldoende"
        reden = ""
        vervolgvraag = None
    elif total >= _THRESHOLD_DEELS:
        status = "deels"
        reden = topic.deels_hint
        vervolgvraag = None
    else:
        status = "onvoldoende"
        reden = "Geen of nauwelijks signaal in tekst of velden."
        vervolgvraag = topic.vervolgvraag

    return CoverageCoachResult(
        onderwerp=topic.id,
        label=topic.label,
        status=status,
        reden=reden,
        vervolgvraag=vervolgvraag,
        bron_hits=matched,
    )


# ---------------------------------------------------------------------------
# Publieke API
# ---------------------------------------------------------------------------

def evaluate_basic_coverage(state: dict) -> list[CoverageCoachResult]:
    """
    Evalueert alle 15 kernonderwerpen op basis van alle beschikbare tekst.

    Volgorde: onvoldoende → deels → voldoende (meest urgente eerst).
    """
    scan_text = _build_scan_text(state)
    results = [_evaluate_topic(t, state, scan_text) for t in _TOPICS]

    order = {"onvoldoende": 0, "deels": 1, "voldoende": 2}
    results.sort(key=lambda r: order[r.status])
    return results
