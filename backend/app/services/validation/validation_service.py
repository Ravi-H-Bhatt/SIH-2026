"""
Document Field & Rules Validation Service.

Validates extracted document fields against ICAO rules, regex patterns, ISO country codes, and date logic.
Supports Passports, Visas, and National ID / Aadhaar documents.
"""

import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional


# ISO 3166-1 alpha-3 country codes subset (Common countries for border screening)
ISO_3166_ALPHA3 = {
    "IND", "USA", "GBR", "CAN", "AUS", "DEU", "FRA", "JPN", "CHN", "SGP",
    "ARE", "SAU", "NLD", "CHE", "ESP", "ITA", "BRA", "ZAF", "RUS", "MEX",
    "KOR", "MYS", "THAI", "IDN", "NZL", "TUR", "EGY", "NGA", "ARG", "COL"
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
        issuing_country = extracted_fields.get("issuing_country", "")
        if issuing_country and len(issuing_country) == 3:
            if issuing_country not in ISO_3166_ALPHA3:
                flags.append(f"Non-standard ISO country code: {issuing_country}")
                field_results["issuing_country"] = {"valid": False, "reason": "Unrecognized ISO code"}
            else:
                field_results["issuing_country"] = {"valid": True}

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
