"""
ICAO 9303 MRZ (Machine Readable Zone) Parser & Check Digit Validator.

Supports TD1 (3 lines, 30 chars), TD2 (2 lines, 36 chars), and TD3/MRP (2 lines, 44 chars - Passports).
Implements official ICAO 7-3-1 weighting algorithm for check digits.
"""

import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

# TD3 line 2 layout: doc-no(9) cd(1) nat(3) dob(6) cd(1) sex(1) expiry(6) cd(1)
# Anchored so a random alphanumeric run cannot masquerade as a data line.
TD3_LINE2_RE = re.compile(
    r"^(?P<doc>[A-Z0-9<]{9})(?P<doc_cd>\d)(?P<nat>[A-Z<]{3})"
    r"(?P<dob>\d{6})(?P<dob_cd>\d)(?P<sex>[MFX<])"
    r"(?P<exp>\d{6})(?P<exp_cd>\d)"
)

# Non-ICAO variant: no check digits, DDMMYYYY dates.
#   Z43R34255ARE03071978M10022020
NON_ICAO_LINE2_RE = re.compile(
    r"^(?P<doc>[A-Z0-9]{6,10})(?P<nat>[A-Z]{3})(?P<dob>\d{8})"
    r"(?P<sex>[MFX])(?P<exp>\d{8})"
)


def _ddmmyyyy(value: str) -> Optional[str]:
    """DDMMYYYY -> YYYY-MM-DD, or None when the components are impossible."""
    if len(value) != 8 or not value.isdigit():
        return None
    dd, mm, yyyy = value[0:2], value[2:4], value[4:8]
    if not (1 <= int(mm) <= 12) or not (1 <= int(dd) <= 31):
        return None
    if not (1900 <= int(yyyy) <= 2100):
        return None
    return f"{yyyy}-{mm}-{dd}"


def _parse_non_icao_line2(
    match: "re.Match[str]",
    line1: Optional[str],
    lines: List[str],
) -> Dict[str, Any]:
    """
    Parse the check-digit-free MRZ variant.

    `mrz_valid` is always False: with no check digits there is no integrity
    evidence, and reporting True would tell an officer the document had been
    verified when nothing was verified at all.
    """
    nationality = match.group("nat").upper()
    surname = given_names = ""
    if line1:
        repaired = _repair_td3_line1(line1, "")
        name_part = repaired[5:] if _is_known_country(repaired[2:5]) else repaired[2:]
        parts = name_part.split("<<")
        surname = parts[0].replace("<", " ").strip()
        given_names = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""

    holder = f"{given_names} {surname}".strip() or None

    return {
        "mrz_valid": False,
        "document_type": "passport",
        "document_number": match.group("doc"),
        "holder_name": holder,
        "surname": surname,
        "given_names": given_names,
        "issuing_country": nationality if _is_known_country(nationality) else None,
        "nationality": nationality if _is_known_country(nationality) else None,
        "date_of_birth": _ddmmyyyy(match.group("dob")),
        "sex": match.group("sex"),
        "expiry_date": _ddmmyyyy(match.group("exp")),
        "mrz_lines": [l for l in ([line1] if line1 else []) + [match.string]],
        "check_digits": {
            "doc_number_valid": False,
            "dob_valid": False,
            "expiry_valid": False,
        },
        "mrz_format": "non_icao_simplified",
        "flags": [
            "MRZ does not follow ICAO 9303 — no check digits present, so document "
            "integrity cannot be cryptographically verified. Fields were read but "
            "must be confirmed against the visual inspection zone by an officer.",
        ],
    }


def calculate_check_digit(data: str) -> int:
    """
    Computes ICAO 9303 check digit using weights 7, 3, 1.
    '<' character is treated as 0.
    """
    weights = [7, 3, 1]
    total = 0
    for i, char in enumerate(data):
        if char == '<':
            val = 0
        elif char.isdigit():
            val = int(char)
        elif char.isalpha():
            val = ord(char.upper()) - 55  # A=10, B=11 ... Z=35
        else:
            val = 0
        total += val * weights[i % 3]
    return total % 10


def _sanitize_mrz_line(line: str) -> str:
    """Removes spaces, replaces odd characters, and upper-cases."""
    line = line.strip().replace(" ", "").upper()
    # Replace common OCR misreads in MRZ filler
    line = line.replace("«", "<").replace("(", "<").replace("{", "<").replace("[", "<")
    return line


def parse_mrz_lines(mrz_text: str, visual_fallback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Parses raw MRZ text block and returns extracted structured fields along with validation status.
    Supports 2-line TD3, 3-line TD1, 2-line TD2, and single-line TD3 recovery.
    """
    raw_lines = [l for l in mrz_text.split('\n') if l.strip()]
    lines = [_sanitize_mrz_line(l) for l in raw_lines]

    if not lines:
        return {
            "mrz_valid": False,
            "error": "No MRZ lines detected",
            "fields": {},
            "flags": ["No MRZ lines found on document"]
        }

    # ── Reassemble a TD3 pair from partially-read lines ──────────────────────
    # OCR engines (Google Vision in particular) collapse or drop the trailing
    # '<' filler run, so line 1 often arrives far shorter than 44 characters —
    # e.g. "P<USATHIEF<<JOHN<<<<". The old length>=38 gate rejected those, fell
    # through to the line-2-only path, and lost the holder's name entirely.
    # Filler is positionally meaningless, so right-padding is lossless.
    line1_candidate = next(
        (l for l in lines if re.match(r"^[PIVAC][A-Z<]?[A-Z]{3}[A-Z<]", l)), None
    )
    line2_candidate = next((l for l in lines if TD3_LINE2_RE.match(l)), None)

    if line1_candidate and line2_candidate:
        return _parse_td3(
            line1_candidate.ljust(44, "<")[:44],
            line2_candidate.ljust(44, "<")[:44],
        )

    # ── Non-ICAO "simplified" MRZ variant ────────────────────────────────────
    # Checked BEFORE the length-based TD1/TD2 guesses below. Those guesses look
    # only at line length, so a 44-char TD3 line 1 satisfied the TD2 test
    # (>= 34 chars) and got sliced with TD2 offsets — reading the issuing state
    # out of the middle of a surname ("FAR" from P<FARSI) and an expiry date out
    # of the birth-date field. Structure must win over length.
    #
    # Variant layout has no check digits and full DDMMYYYY dates:
    #     Z43R34255ARE03071978M10022020<<<<
    #     |docno   |nat|dob   |s|expiry
    for line in lines:
        variant = NON_ICAO_LINE2_RE.match(line)
        if variant:
            return _parse_non_icao_line2(variant, line1_candidate, lines)

    # TD3 / Passport (2 lines, ~44 chars each)
    if len(lines) >= 2 and len(lines[0]) >= 38 and len(lines[1]) >= 38:
        return _parse_td3(lines[0][:44], lines[1][:44])

    # TD1 / ID Card (3 lines, ~30 chars each)
    elif len(lines) >= 3 and len(lines[0]) >= 28:
        return _parse_td1(lines[0][:30], lines[1][:30], lines[2][:30])

    # TD2 (2 lines, ~36 chars each). Requires BOTH lines to be TD2-sized —
    # a 44-char TD3 line must not qualify.
    elif len(lines) >= 2 and 34 <= len(lines[0]) <= 38 and len(lines[1]) >= 34:
        return _parse_td2(lines[0][:36], lines[1][:36])

    # Check if any line looks like TD3 Line 2 (Passport data line with check digits)
    # Line 2 format: DocNum (9) + CD (1) + Nat (3) + DOB (6) + CD (1) + Sex (1) + Exp (6) + CD (1)...
    for line in lines:
        cleaned = re.sub(r'[^A-Z0-9<]', '', line)
        if len(cleaned) >= 20 and ('<' in cleaned or any(c.isdigit() for c in cleaned)):
            # Try to test if this is a TD3 Line 2
            parsed_line2 = _try_parse_td3_line2(cleaned, visual_fallback)
            if parsed_line2:
                return parsed_line2
    
    # Fallback attempt on raw string
    return _parse_generic_mrz(lines)


def _is_known_country(code: str) -> bool:
    """True when `code` is an ISO-3166 alpha-3 code we recognise."""
    if not code or len(code) != 3 or not code.isalpha():
        return False
    from app.services.geo.geo_reference import COUNTRY_CENTROIDS

    return code.upper() in COUNTRY_CENTROIDS


def _repair_td3_line1(line1: str, line2: str) -> str:
    """
    Reinsert the issuing-state code into MRZ line 1 when OCR dropped it.

    TD3 line 1 is `P<` + 3-letter state + surname + `<<` + given names. Real
    scans of UAE passports came back as `P<FARSI<<AHMAD<AL<<<` — the `ARE` was
    lost, so positional slicing read the state as "FAR" and the surname as "SI",
    producing holder "AHMAD AL SI" from a country code that does not exist.

    If positions 2-5 are not a country we know, but line 2's nationality field
    is, the code is treated as missing and spliced back in. Line 2's nationality
    is the trustworthy source here because it sits inside a check-digit-verified
    run, whereas line 1 has no check digit of its own.
    """
    if len(line1) < 5:
        return line1

    candidate_state = line1[2:5]
    if _is_known_country(candidate_state):
        return line1

    nationality = line2[10:13] if len(line2) >= 13 else ""
    if not _is_known_country(nationality):
        # Cannot establish the real state — leave the line untouched rather than
        # inventing one. _parse_td3 will surface it as an unknown country.
        return line1

    return f"{line1[:2]}{nationality.upper()}{line1[2:]}"


def _try_parse_td3_line2(line2: str, visual: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Recovers passport information from TD3 Line 2 even if Line 1 was occluded or cropped.
    Line 2 format:
    0-8: Document Number (9 chars)
    9: Doc Number Check Digit (1 digit)
    10-12: Nationality (3 alpha chars, e.g. IND, USA)
    13-18: Date of Birth (YYMMDD)
    19: DOB Check Digit (1 digit)
    20: Sex (M/F/X)
    21-26: Expiry Date (YYMMDD)
    27: Expiry Check Digit (1 digit)
    """
    # Require the actual ICAO TD3 line-2 layout. Positional slicing alone let
    # fragments of line 1 (e.g. "P<USATHIEF<<JOHN<<<<") be treated as a data
    # line, yielding document_number="PUSATHIE" with a fabricated birth date.
    match = TD3_LINE2_RE.match(line2)
    if not match:
        return None

    doc_num_raw = match.group("doc")
    doc_num = doc_num_raw.replace('<', '')
    doc_num_cd = match.group("doc_cd")

    # Nationality: correct only the two OCR confusions that are unambiguous in
    # an alpha-only field (1->I, 0->O). Do not default to a country — guessing
    # the issuing state of an unreadable passport is not acceptable.
    nat_clean = match.group("nat").replace('1', 'I').replace('0', 'O').replace('<', '')
    nationality = nat_clean if len(nat_clean) == 3 else None

    dob_raw, dob_cd = match.group("dob"), match.group("dob_cd")
    sex_raw = match.group("sex")
    sex = sex_raw if sex_raw in ("M", "F") else "U"
    expiry_raw, expiry_cd = match.group("exp"), match.group("exp_cd")

    # Validate check digits. A digit is always present here because the regex
    # requires it, so there is no "assume valid" branch any more.
    flags = []
    doc_num_valid = str(calculate_check_digit(doc_num_raw)) == doc_num_cd
    if not doc_num_valid:
        flags.append("Document number check digit mismatch")

    dob_valid = str(calculate_check_digit(dob_raw)) == dob_cd
    if not dob_valid:
        flags.append("Date of birth check digit mismatch")

    expiry_valid = str(calculate_check_digit(expiry_raw)) == expiry_cd
    if not expiry_valid:
        flags.append("Expiry date check digit mismatch")

    flags.append("MRZ line 1 not recovered — name taken from visual inspection zone")

    # Format dates
    formatted_dob = _format_mrz_date(dob_raw, is_dob=True) if dob_raw else (visual.get("date_of_birth") if visual else None)
    formatted_expiry = _format_mrz_date(expiry_raw, is_dob=False) if (expiry_raw and len(expiry_raw) == 6) else (visual.get("expiry_date") if visual else None)

    # Reconcile with the visual zone for the name and any missing field.
    holder_name = None
    surname = ""
    given_names = ""
    if visual:
        if visual.get("holder_name"):
            holder_name = visual["holder_name"]
            surname = visual.get("surname", "")
            given_names = visual.get("given_names", "")
        # Filling a gap from the VIZ is fine, but it is NOT check-digit
        # verification, so the *_valid flags must not be flipped to True here.
        if not formatted_expiry and visual.get("expiry_date"):
            formatted_expiry = visual["expiry_date"]
            flags.append("Expiry date taken from visual zone, not check-digit verified")
        if not formatted_dob and visual.get("date_of_birth"):
            formatted_dob = visual["date_of_birth"]
            flags.append("Date of birth taken from visual zone, not check-digit verified")
        if sex == "U" and visual.get("sex"):
            sex = visual["sex"]

    # A partially recovered MRZ is never "valid". Line 1 is missing, so the
    # composite check digit cannot be computed at all.
    mrz_valid = False

    return {
        "mrz_valid": mrz_valid,
        "document_type": "passport",
        "document_number": doc_num,
        "holder_name": holder_name,
        "surname": surname,
        "given_names": given_names,
        "issuing_country": nationality,
        "nationality": nationality,
        "date_of_birth": formatted_dob,
        "sex": sex,
        "expiry_date": formatted_expiry,
        "mrz_lines": [line2],
        "check_digits": {
            "doc_number_valid": doc_num_valid,
            "dob_valid": dob_valid,
            "expiry_valid": expiry_valid,
        },
        "flags": flags
    }



def _parse_td3(line1: str, line2: str) -> Dict[str, Any]:
    """
    Parse TD3 (2 lines of 44 characters) - Standard Passport.
    Line 1: P<COUNTRYNAME<<GIVEN<NAMES<<<<<<<<<<<<<<<<<<<<<
    Line 2: NUMBER<C COUNTRY DOB C SEX EXP C PERSONAL_NUM C CHECK_OVERALL
    """
    flags = []

    # Recover a dropped issuing-state code before any positional slicing.
    line1 = _repair_td3_line1(line1, line2).ljust(44, "<")[:44]

    doc_type = line1[0:2].replace('<', '')
    issuing_country = line1[2:5].replace('<', '')
    if not _is_known_country(issuing_country):
        flags.append(
            f"MRZ line 1 issuing-state code '{issuing_country}' is not a recognised "
            "ISO-3166 alpha-3 code — line 1 may be misread"
        )

    # Names parsing: SURNAME<<GIVEN_NAMES
    name_part = line1[5:]
    name_components = name_part.split('<<')
    surname = name_components[0].replace('<', ' ').strip()
    given_names = name_components[1].replace('<', ' ').strip() if len(name_components) > 1 else ""
    holder_name = f"{given_names} {surname}".strip() if given_names else surname

    doc_num = line2[0:9].replace('<', '')
    doc_num_cd = line2[9]
    
    nationality = line2[10:13].replace('<', '')
    dob = line2[13:19]
    dob_cd = line2[19]
    
    sex = line2[20]
    sex = "M" if sex == "M" else ("F" if sex == "F" else "X")
    
    expiry = line2[21:27]
    expiry_cd = line2[27]
    
    optional_data = line2[28:42]
    composite_cd = line2[43] if len(line2) > 43 else ""

    # Validate Check Digits
    doc_num_valid = str(calculate_check_digit(line2[0:9])) == doc_num_cd
    dob_valid = str(calculate_check_digit(dob)) == dob_cd
    expiry_valid = str(calculate_check_digit(expiry)) == expiry_cd

    if not doc_num_valid:
        flags.append("Document number check digit mismatch")
    if not dob_valid:
        flags.append("Date of birth check digit mismatch")
    if not expiry_valid:
        flags.append("Expiry date check digit mismatch")

    mrz_valid = doc_num_valid and dob_valid and expiry_valid

    # Format dates (YYMMDD -> YYYY-MM-DD)
    formatted_dob = _format_mrz_date(dob, is_dob=True)
    formatted_expiry = _format_mrz_date(expiry, is_dob=False)

    return {
        "mrz_valid": mrz_valid,
        "document_type": "passport",
        "document_number": doc_num,
        "holder_name": holder_name,
        "surname": surname,
        "given_names": given_names,
        "issuing_country": issuing_country,
        "nationality": nationality,
        "date_of_birth": formatted_dob,
        "sex": sex,
        "expiry_date": formatted_expiry,
        "mrz_lines": [line1, line2],
        "check_digits": {
            "doc_number_valid": doc_num_valid,
            "dob_valid": dob_valid,
            "expiry_valid": expiry_valid,
        },
        "flags": flags
    }


def _parse_td1(line1: str, line2: str, line3: str) -> Dict[str, Any]:
    """Parse TD1 (3 lines of 30 characters) - ID Cards."""
    doc_num = line1[5:14].replace('<', '')
    doc_num_cd = line1[14]
    doc_num_valid = str(calculate_check_digit(line1[5:14])) == doc_num_cd

    dob = line2[0:6]
    dob_cd = line2[6]
    dob_valid = str(calculate_check_digit(dob)) == dob_cd

    sex = line2[7]
    expiry = line2[8:14]
    expiry_cd = line2[14]
    expiry_valid = str(calculate_check_digit(expiry)) == expiry_cd

    nationality = line2[15:18].replace('<', '')

    names = line3.split('<<')
    surname = names[0].replace('<', ' ').strip()
    given = names[1].replace('<', ' ').strip() if len(names) > 1 else ""

    return {
        "mrz_valid": doc_num_valid and dob_valid and expiry_valid,
        "document_type": "id_card",
        "document_number": doc_num,
        "holder_name": f"{given} {surname}".strip(),
        "issuing_country": line1[2:5].replace('<', ''),
        "nationality": nationality,
        "date_of_birth": _format_mrz_date(dob, is_dob=True),
        "sex": sex,
        "expiry_date": _format_mrz_date(expiry, is_dob=False),
        "mrz_lines": [line1, line2, line3],
        "check_digits": {
            "doc_number_valid": doc_num_valid,
            "dob_valid": dob_valid,
            "expiry_valid": expiry_valid,
        },
        "flags": []
    }


def _parse_td2(line1: str, line2: str) -> Dict[str, Any]:
    """Parse TD2 (2 lines of 36 characters)."""
    doc_num = line2[0:9].replace('<', '')
    doc_num_cd = line2[9]
    doc_num_valid = str(calculate_check_digit(line2[0:9])) == doc_num_cd

    dob = line2[13:19]
    dob_cd = line2[19]
    dob_valid = str(calculate_check_digit(dob)) == dob_cd

    expiry = line2[21:27]
    expiry_cd = line2[27]
    expiry_valid = str(calculate_check_digit(expiry)) == expiry_cd

    name_components = line1[5:].split('<<')
    surname = name_components[0].replace('<', ' ').strip()
    given = name_components[1].replace('<', ' ').strip() if len(name_components) > 1 else ""

    return {
        "mrz_valid": doc_num_valid and dob_valid and expiry_valid,
        "document_type": "travel_document",
        "document_number": doc_num,
        "holder_name": f"{given} {surname}".strip(),
        "issuing_country": line1[2:5].replace('<', ''),
        "nationality": line2[10:13].replace('<', ''),
        "date_of_birth": _format_mrz_date(dob, is_dob=True),
        "sex": line2[20],
        "expiry_date": _format_mrz_date(expiry, is_dob=False),
        "mrz_lines": [line1, line2],
        "check_digits": {
            "doc_number_valid": doc_num_valid,
            "dob_valid": dob_valid,
            "expiry_valid": expiry_valid,
        },
        "flags": []
    }


def _parse_generic_mrz(lines: List[str]) -> Dict[str, Any]:
    """
    Last-resort result for text that resembles an MRZ but does not parse.

    Reports nothing it cannot read. The previous version returned
    document_number from a bare `[A-Z0-9]{8,10}` match anywhere in the joined
    lines — which picked up fragments of line 1 such as "PUSATHIE" — plus
    hardcoded dob=1990-01-01, sex=M, expiry=2030-01-01. Downstream that meant
    the risk engine scored fabricated demographics as if they were extracted
    evidence. Everything unreadable is now explicitly None.
    """
    return {
        "mrz_valid": False,
        "document_type": "passport",
        "document_number": None,
        "holder_name": None,
        "surname": "",
        "given_names": "",
        "issuing_country": None,
        "nationality": None,
        "date_of_birth": None,
        "sex": "U",
        "expiry_date": None,
        "mrz_lines": lines,
        "check_digits": {"doc_number_valid": False, "dob_valid": False, "expiry_valid": False},
        "flags": [
            "MRZ detected but could not be decoded — no ICAO 9303 structure matched. "
            "Fields must be confirmed visually by an officer."
        ],
    }


def _format_mrz_date(yy_mm_dd: str, is_dob: bool) -> Optional[str]:
    """
    Converts YYMMDD into YYYY-MM-DD, or returns None when unparseable.

    Previously returned the literal "2030-01-01" on any failure. That fabricated
    an expiry date for unreadable documents, and because the caller treated a
    truthy date as evidence of a valid MRZ, unreadable passports were reported
    as `mrz_valid: True`. Never invent a date — return None and let the caller
    record the field as missing.
    """
    if len(yy_mm_dd) != 6 or not yy_mm_dd.isdigit():
        return None

    yy = int(yy_mm_dd[0:2])
    mm, dd = yy_mm_dd[2:4], yy_mm_dd[4:6]

    # Reject impossible components rather than emitting e.g. 2030-99-45.
    if not (1 <= int(mm) <= 12) or not (1 <= int(dd) <= 31):
        return None

    if is_dob:
        # A two-digit year in the future cannot be a birth year.
        current_yy = datetime.now(timezone.utc).year % 100
        year = 2000 + yy if yy <= current_yy else 1900 + yy
    else:
        year = 2000 + yy if yy <= 70 else 1900 + yy

    return f"{year}-{mm}-{dd}"
