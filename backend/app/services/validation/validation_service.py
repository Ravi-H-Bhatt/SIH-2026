"""
Document Field & Rules Validation Service.

Validates extracted document fields against ICAO rules, regex patterns, ISO country codes, and date logic.
Supports Passports, Visas, and National ID / Aadhaar documents.
"""

import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional


# Full ISO 3166-1 alpha-3 set, plus the ICAO 9303 special-purpose codes that
# legitimately appear in the MRZ issuing-state field.
#
# This replaces a hand-written 30-entry subset that had two defects: it flagged
# most of the world's passports as "non-standard", and it contained "THAI",
# which is not an ISO code at all — so a genuine Thai passport (THA) was flagged
# while the invalid code passed.
ISO_3166_ALPHA3 = {
    "ABW", "AFG", "AGO", "AIA", "ALA", "ALB", "AND", "ARE", "ARG", "ARM",
    "ASM", "ATA", "ATF", "ATG", "AUS", "AUT", "AZE", "BDI", "BEL", "BEN",
    "BES", "BFA", "BGD", "BGR", "BHR", "BHS", "BIH", "BLM", "BLR", "BLZ",
    "BMU", "BOL", "BRA", "BRB", "BRN", "BTN", "BVT", "BWA", "CAF", "CAN",
    "CCK", "CHE", "CHL", "CHN", "CIV", "CMR", "COD", "COG", "COK", "COL",
    "COM", "CPV", "CRI", "CUB", "CUW", "CXR", "CYM", "CYP", "CZE", "DEU",
    "DJI", "DMA", "DNK", "DOM", "DZA", "ECU", "EGY", "ERI", "ESH", "ESP",
    "EST", "ETH", "FIN", "FJI", "FLK", "FRA", "FRO", "FSM", "GAB", "GBR",
    "GEO", "GGY", "GHA", "GIB", "GIN", "GLP", "GMB", "GNB", "GNQ", "GRC",
    "GRD", "GRL", "GTM", "GUF", "GUM", "GUY", "HKG", "HMD", "HND", "HRV",
    "HTI", "HUN", "IDN", "IMN", "IND", "IOT", "IRL", "IRN", "IRQ", "ISL",
    "ISR", "ITA", "JAM", "JEY", "JOR", "JPN", "KAZ", "KEN", "KGZ", "KHM",
    "KIR", "KNA", "KOR", "KWT", "LAO", "LBN", "LBR", "LBY", "LCA", "LIE",
    "LKA", "LSO", "LTU", "LUX", "LVA", "MAC", "MAF", "MAR", "MCO", "MDA",
    "MDG", "MDV", "MEX", "MHL", "MKD", "MLI", "MLT", "MMR", "MNE", "MNG",
    "MNP", "MOZ", "MRT", "MSR", "MTQ", "MUS", "MWI", "MYS", "MYT", "NAM",
    "NCL", "NER", "NFK", "NGA", "NIC", "NIU", "NLD", "NOR", "NPL", "NRU",
    "NZL", "OMN", "PAK", "PAN", "PCN", "PER", "PHL", "PLW", "PNG", "POL",
    "PRI", "PRK", "PRT", "PRY", "PSE", "PYF", "QAT", "REU", "ROU", "RUS",
    "RWA", "SAU", "SDN", "SEN", "SGP", "SGS", "SHN", "SJM", "SLB", "SLE",
    "SLV", "SMR", "SOM", "SPM", "SRB", "SSD", "STP", "SUR", "SVK", "SVN",
    "SWE", "SWZ", "SXM", "SYC", "SYR", "TCA", "TCD", "TGO", "THA", "TJK",
    "TKL", "TKM", "TLS", "TON", "TTO", "TUN", "TUR", "TUV", "TWN", "TZA",
    "UGA", "UKR", "UMI", "URY", "USA", "UZB", "VAT", "VCT", "VEN", "VGB",
    "VIR", "VNM", "VUT", "WLF", "WSM", "YEM", "ZAF", "ZMB", "ZWE",
    # ICAO 9303 special-purpose issuing codes
    "GBD", "GBN", "GBO", "GBP", "GBS",   # British overseas / national variants
    "UNO", "UNA", "UNK",                  # United Nations
    "XBA", "XIM", "XCC", "XCO", "XEC",   # regional development banks
    "XPO", "XOM", "XXA", "XXB", "XXC", "XXX",  # stateless / refugee / unspecified
    "RKS",                                # Kosovo, as printed on its passports
}


class ValidationService:
    def validate_extracted_data(
        self,
        extracted_fields: Dict[str, Any],
        mrz_valid: bool = True
    ) -> Dict[str, Any]:
        """
        Runs document validation rules against extracted data fields.
        """
        flags: List[str] = []
        field_results: Dict[str, Dict[str, Any]] = {}
        warnings_count = 0
        doc_type = extracted_fields.get("document_type", "passport")
        mrz_required = extracted_fields.get("mrz_required", doc_type == "passport")

        # 0. Holder name readability.
        #
        # "TRAVELER" is the OCR layer's placeholder for an unreadable name. It
        # was recognised nowhere as a placeholder, so an unreadable name was
        # stored, screened against the watchlist and fed to the identity graph
        # as though it were a real identity, with no flag raised.
        holder_name = str(extracted_fields.get("holder_name") or "").strip().upper()
        if not holder_name or holder_name in ("TRAVELER", "TRAVELLER", "UNKNOWN", "UNREADABLE NAME"):
            flags.append(
                "Holder name could not be read from the document — identity is "
                "unresolved and cannot be reliably screened"
            )
            warnings_count += 1
            field_results["holder_name"] = {"valid": False, "reason": "Unreadable or placeholder"}
        else:
            field_results["holder_name"] = {"valid": True}

        # 1. Document Number Validation
        doc_num = str(extracted_fields.get("document_number", "")).strip()
        clean_doc_num = re.sub(r"[\s-]", "", doc_num)

        if not clean_doc_num or clean_doc_num in ["UNKNOWN", "NOT_DETECTED"]:
            flags.append("Missing or unreadable document number")
            warnings_count += 1
            field_results["document_number"] = {"valid": False, "reason": "Missing or unreadable"}
        elif not re.match(r"^[A-Z0-9]{6,16}$", clean_doc_num):
            flags.append(f"Non-standard document number format: {doc_num}")
            warnings_count += 1
            field_results["document_number"] = {"valid": False, "reason": "Format anomaly"}
        else:
            field_results["document_number"] = {"valid": True, "formatted": doc_num}

        # 2. Expiry Date Logic Check
        expiry_str = extracted_fields.get("expiry_date", "")
        if expiry_str:
            try:
                expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                today = date.today()
                if expiry_dt < today:
                    flags.append(f"Expired document (Expired on {expiry_str})")
                    warnings_count += 1
                    field_results["expiry_date"] = {"valid": False, "reason": "Document expired"}
                elif (expiry_dt - today).days < 90:
                    flags.append(f"Document near expiry (Expires within 90 days: {expiry_str})")
                    field_results["expiry_date"] = {"valid": True, "warning": "Near expiry"}
                else:
                    field_results["expiry_date"] = {"valid": True}
            except ValueError:
                flags.append(f"Invalid expiry date format: {expiry_str}")
                warnings_count += 1
                field_results["expiry_date"] = {"valid": False, "reason": "Date parse error"}
        else:
            if not mrz_required or doc_type in ["id_card", "aadhaar", "national_id"]:
                field_results["expiry_date"] = {"valid": True, "note": "Lifelong validity (National ID / Aadhaar)"}
            else:
                flags.append("Missing expiry date")
                warnings_count += 1
                field_results["expiry_date"] = {"valid": False, "reason": "Missing field"}

        # 3. Date of Birth Reasonableness Check
        dob_str = extracted_fields.get("date_of_birth", "")
        if dob_str:
            try:
                dob_dt = datetime.strptime(dob_str, "%Y-%m-%d").date()
                today = date.today()
                age = (today - dob_dt).days // 365
                if dob_dt > today:
                    flags.append(f"Future birth date detected: {dob_str}")
                    warnings_count += 1
                    field_results["date_of_birth"] = {"valid": False, "reason": "Future date"}
                elif age > 120 or age < 0:
                    flags.append(f"Unrealistic holder age ({age} years)")
                    warnings_count += 1
                    field_results["date_of_birth"] = {"valid": False, "reason": "Unrealistic age"}
                else:
                    field_results["date_of_birth"] = {"valid": True, "calculated_age": age}
            except ValueError:
                flags.append(f"Invalid date of birth format: {dob_str}")
                warnings_count += 1
                field_results["date_of_birth"] = {"valid": False, "reason": "Date parse error"}

        # 4. Country Code Validation (ISO 3166)
        #
        # An unrecognised issuing state now increments warnings_count. It
        # previously did not, and since risk_engine only reads `flags` when
        # `is_valid` is False (and is_valid == warnings_count == 0), a bogus
        # country code with no other warning was silently dropped and never
        # scored.
        issuing_country = str(extracted_fields.get("issuing_country") or "").strip().upper()
        if not issuing_country:
            flags.append("Issuing country could not be determined from the document")
            warnings_count += 1
            field_results["issuing_country"] = {"valid": False, "reason": "Not detected"}
        elif len(issuing_country) != 3:
            flags.append(f"Issuing country code is not 3 letters: {issuing_country}")
            warnings_count += 1
            field_results["issuing_country"] = {"valid": False, "reason": "Malformed code"}
        elif issuing_country not in ISO_3166_ALPHA3:
            flags.append(f"Unrecognised ISO 3166-1 alpha-3 country code: {issuing_country}")
            warnings_count += 1
            field_results["issuing_country"] = {"valid": False, "reason": "Unrecognised ISO code"}
        else:
            field_results["issuing_country"] = {"valid": True, "code": issuing_country}

        # 5. MRZ Validation Status Integration
        if mrz_required and not mrz_valid:
            flags.append("MRZ check digit validation failed")
            warnings_count += 1

        is_valid = warnings_count == 0

        return {
            "is_valid": is_valid,
            "warnings_count": warnings_count,
            "field_results": field_results,
            "flags": flags
        }


validation_service = ValidationService()
