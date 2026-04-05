# validators.py - Validatie logica
import json
from typing import Dict, Any, List

def validate_other_info(other_info: Dict[str, Any]) -> List[str]:
    """Valideer 'Overige gegevens' structuur."""
    errors = []
    
    if not isinstance(other_info, dict):
        errors.append("❌ other_info is geen dict")
        return errors
    
    json_str = json.dumps(other_info, ensure_ascii=False).lower()
    
    # 1. Beleid check
    forbidden_terms = ["beleid", "behandel", "therapie", "voorschrijf"]
    if any(term in json_str for term in forbidden_terms):
        errors.append("⚠️ Beleid/behandeling hoort niet in 'Overige gegevens' (feiten-only)")
    
    # 2. Bron check
    if "bron" not in json_str:
        errors.append("💡 Advies: voeg 'bron' toe per item (EPD, brief, patiënt)")
    
    # 3. Zekerheid check
    if "zekerheid" not in json_str and "certainty" not in json_str:
        errors.append("💡 Advies: voeg 'zekerheid' toe (hoog/middel/laag)")
    
    # 4. Rode vlaggen detectie
    red_flags = {
        "diabetes": "Diabetes verhoogt risico op neuropathie",
        "chemo": "Chemotherapie → CIPN risico",
        "hiv": "HIV → distale symmetrische polyneuropathie",
        "trauma": "Trauma → CRPS/zenuwletsel risico",
        "maligniteit": "Maligniteit → paraneoplastisch/compressie",
        "immunosuppressie": "Verhoogd infectierisico (bijv. herpes zoster)",
    }
    
    detected_flags = [flag for flag in red_flags if flag in json_str]
    if detected_flags:
        if "rode" not in json_str and "flag" not in json_str and "risk" not in json_str:
            flag_list = ", ".join(detected_flags)
            errors.append(f"⚠️ Rode vlaggen gedetecteerd ({flag_list}) maar niet expliciet benoemd")
    
    # 5. Medicatie compleetheid
    if "medicatie" in json_str or "medication" in json_str:
        med_data = str(other_info.get("medicatie", other_info.get("medication", "")))
        required = ["naam", "dose", "dosering", "start"]
        missing = [f for f in required if f not in med_data.lower()]
        if len(missing) >= 3:  # Als bijna alles ontbreekt
            errors.append("💡 Medicatie incompleet: voeg naam, dosering, startdatum toe")
    
    # 6. Beeldvorming zonder conclusie
    if "mri" in json_str or "ct" in json_str or "echo" in json_str:
        imaging_str = str(other_info.get("beeldvorming", other_info.get("imaging", "")))
        if imaging_str and len(imaging_str) < 50:
            errors.append("💡 Beeldvorming vermeld: voeg conclusie/bevindingen toe")
    
    return errors

def validate_case_json(case_json: Dict[str, Any]) -> List[str]:
    """Valideer Case JSON compleetheid."""
    errors = []
    
    # Meta velden
    meta = case_json.get("meta", {})
    required_meta = ["case_id", "intake_datum", "output_mode"]
    for field in required_meta:
        if field not in meta:
            errors.append(f"❌ Meta incomplete: '{field}' ontbreekt")
    
    # Anamnese
    if "anamnese_raw" not in case_json and "anamnese" not in case_json:
        errors.append("⚠️ Geen anamnese data aanwezig")
    
    # Flags
    flags = case_json.get("flags", {})
    if not flags:
        errors.append("💡 Advies: voeg 'flags' sectie toe (rode vlaggen, missende data)")
    
    return errors

def validate_dd_output(dd_text: str) -> List[str]:
    """Valideer DD-output kwaliteit."""
    errors = []
    
    dd_lower = dd_text.lower()
    
    # 1. Mechanisme scores aanwezig?
    if "%" not in dd_text and "procent" not in dd_lower:
        errors.append("💡 Advies: kwantificeer mechanisme-zekerheid (bijv. 'Neuropathisch: 70%')")
    
    # 2. Baron bij neuropathie?
    if "neuropath" in dd_lower and "cluster" not in dd_lower and "fenotype" not in dd_lower:
        errors.append("💡 Bij neuropathische pijn: overweeg Baron-fenotypering")
    
    # 3. Centrale sensitisatie als modulator?
    if "centrale sensitisatie" in dd_lower or "central sensitization" in dd_lower:
        if "modulator" not in dd_lower and "bijdraagt" not in dd_lower:
            errors.append("⚠️ Centrale sensitisatie: benoem als modulator, niet als primair mechanisme")
    
    # 4. Syndroom voor mechanisme?
    syndromes = ["crps", "fibromyalgie", "trigeminusneuralgie", "radiculopathie"]
    early_mention = dd_text[:500].lower()  # Eerste 500 chars
    if any(syn in early_mention for syn in syndromes):
        if "nociceptief" not in early_mention and "neuropath" not in early_mention:
            errors.append("⚠️ Syndroom vermeld voor mechanisme - draai volgorde om")
    
    # 5. Beleid in DD?
    treatment_terms = ["voorschrijf", "start met", "behandel met", "geef"]
    if any(term in dd_lower for term in treatment_terms):
        errors.append("⚠️ Behandeladvies hoort niet in DD (komt in aparte beleidsfase)")
    
    return errors
