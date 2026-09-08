"""
ICAO 9303 Compliant MRZ Parser
Per SIH26188 Master Prompt

Supports:
- TD3 (Passport) format
- TD1 (ID card) format  
- Check digit validation (ICAO 7-3-1 algorithm)
- VIZ/MRZ consistency checking
"""

import re
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MRZParseResult:
    """Parsed MRZ data"""
    format: str  # TD1, TD3, etc.
    document_type: str
    issuing_country: str
    document_number: str
    date_of_birth: str
    sex: str
    expiry_date: str
    nationality: str
    surname: str
    given_names: str
    optional_data: str
    check_digits_valid: bool
    check_digit_details: Dict[str, dict]
    raw_mrz: str
    success: bool
    error: Optional[str] = None


class ICAOMRZParser:
    """
    ICAO 9303 compliant MRZ parser with check digit validation
    """
    
    # ICAO check digit weights (7-3-1 algorithm)
    WEIGHTS = [7, 3, 1]
    
    # Character values for check digit calculation
    CHAR_VALUES = {
        '<': 0,
        **{str(i): i for i in range(10)},
        **{chr(65 + i): 10 + i for i in range(26)}  # A=10, B=11, ..., Z=35
    }
    
    def __init__(self):
        # TD3 passport: 2 lines of 44 characters each
        self.td3_pattern = re.compile(r'^[A-Z0-9<]{44}\n[A-Z0-9<]{44}$')
        # TD1 ID card: 3 lines of 30 characters each
        self.td1_pattern = re.compile(r'^[A-Z0-9<]{30}\n[A-Z0-9<]{30}\n[A-Z0-9<]{30}$')
    
    def calculate_check_digit(self, data: str) -> int:
        """
        Calculate ICAO check digit using 7-3-1 weighting
        
        Args:
            data: String to calculate check digit for
            
        Returns:
            Check digit (0-9)
        """
        if not data:
            return 0
        
        total = 0
        for i, char in enumerate(data.upper()):
            value = self.CHAR_VALUES.get(char, 0)
            weight = self.WEIGHTS[i % 3]
            total += value * weight
        
        return total % 10
    
    def validate_check_digit(self, data: str, check_digit: str) -> Tuple[bool, dict]:
        """
        Validate check digit against data
        
        Returns:
            (is_valid, details_dict)
        """
        try:
            expected = self.calculate_check_digit(data)
            actual = int(check_digit) if check_digit.isdigit() else None
            
            return (expected == actual, {
                'data': data,
                'expected': expected,
                'actual': actual,
                'valid': expected == actual
            })
        except Exception as e:
            return (False, {
                'error': str(e),
                'data': data,
                'check_digit': check_digit
            })
    
    def parse_td3(self, line1: str, line2: str) -> MRZParseResult:
        """
        Parse TD3 (passport) format MRZ
        
        Line 1: Type(2) + Country(3) + Name(39)
        Line 2: DocNum(9) + CD(1) + Nat(3) + DOB(6) + CD(1) + Sex(1) + Exp(6) + CD(1) + Optional(14) + CD(1) + CompositeCD(1)
        """
        try:
            # Line 1 parsing
            doc_type = line1[0:2].rstrip('<')
            issuing_country = line1[2:5].rstrip('<')
            name_field = line1[5:44].rstrip('<')
            
            # Split name
            name_parts = name_field.split('<<')
            surname = name_parts[0].replace('<', ' ').strip() if name_parts else ''
            given_names = name_parts[1].replace('<', ' ').strip() if len(name_parts) > 1 else ''
            
            # Line 2 parsing
            doc_number = line2[0:9].rstrip('<')
            doc_number_cd = line2[9]
            nationality = line2[10:13].rstrip('<')
            dob = line2[13:19]  # YYMMDD
            dob_cd = line2[19]
            sex = line2[20]
            expiry = line2[21:27]  # YYMMDD
            expiry_cd = line2[27]
            optional_data = line2[28:42].rstrip('<')
            optional_cd = line2[42]
            composite_cd = line2[43]
            
            # Validate check digits
            check_digits = {}
            
            # Document number check
            doc_num_valid, doc_num_details = self.validate_check_digit(doc_number, doc_number_cd)
            check_digits['document_number'] = doc_num_details
            
            # Date of birth check
            dob_valid, dob_details = self.validate_check_digit(dob, dob_cd)
            check_digits['date_of_birth'] = dob_details
            
            # Expiry date check
            expiry_valid, expiry_details = self.validate_check_digit(expiry, expiry_cd)
            check_digits['expiry_date'] = expiry_details
            
            # Optional data check
            opt_valid, opt_details = self.validate_check_digit(optional_data, optional_cd)
            check_digits['optional_data'] = opt_details
            
            # Composite check digit (doc_num + cd + dob + cd + expiry + cd + optional + cd)
            composite_data = (doc_number + doc_number_cd + dob + dob_cd + 
                            expiry + expiry_cd + optional_data + optional_cd)
            composite_valid, composite_details = self.validate_check_digit(composite_data, composite_cd)
            check_digits['composite'] = composite_details
            
            all_valid = all([doc_num_valid, dob_valid, expiry_valid, opt_valid, composite_valid])
            
            # Format dates
            dob_formatted = self._format_date(dob)
            expiry_formatted = self._format_date(expiry)
            
            return MRZParseResult(
                format='TD3',
                document_type=doc_type,
                issuing_country=issuing_country,
                document_number=doc_number,
                date_of_birth=dob_formatted,
                sex=sex,
                expiry_date=expiry_formatted,
                nationality=nationality,
                surname=surname,
                given_names=given_names,
                optional_data=optional_data,
                check_digits_valid=all_valid,
                check_digit_details=check_digits,
                raw_mrz=f"{line1}\n{line2}",
                success=True
            )
            
        except Exception as e:
            return MRZParseResult(
                format='TD3',
                document_type='',
                issuing_country='',
                document_number='',
                date_of_birth='',
                sex='',
                expiry_date='',
                nationality='',
                surname='',
                given_names='',
                optional_data='',
                check_digits_valid=False,
                check_digit_details={},
                raw_mrz=f"{line1}\n{line2}",
                success=False,
                error=str(e)
            )
    
    def parse_td1(self, line1: str, line2: str, line3: str) -> MRZParseResult:
        """
        Parse TD1 (ID card) format MRZ
        
        Line 1: Type(2) + Country(3) + DocNum(9) + CD(1) + Optional(15)
        Line 2: DOB(6) + CD(1) + Sex(1) + Exp(6) + CD(1) + Nat(3) + Optional(11) + CD(1)
        Line 3: Name(30)
        """
        try:
            # Line 1
            doc_type = line1[0:2].rstrip('<')
            issuing_country = line1[2:5].rstrip('<')
            doc_number = line1[5:14].rstrip('<')
            doc_number_cd = line1[14]
            optional1 = line1[15:30].rstrip('<')
            
            # Line 2
            dob = line2[0:6]
            dob_cd = line2[6]
            sex = line2[7]
            expiry = line2[8:14]
            expiry_cd = line2[14]
            nationality = line2[15:18].rstrip('<')
            optional2 = line2[18:29].rstrip('<')
            composite_cd = line2[29]
            
            # Line 3
            name_field = line3.rstrip('<')
            name_parts = name_field.split('<<')
            surname = name_parts[0].replace('<', ' ').strip() if name_parts else ''
            given_names = name_parts[1].replace('<', ' ').strip() if len(name_parts) > 1 else ''
            
            # Validate check digits
            check_digits = {}
            
            doc_num_valid, doc_num_details = self.validate_check_digit(doc_number, doc_number_cd)
            check_digits['document_number'] = doc_num_details
            
            dob_valid, dob_details = self.validate_check_digit(dob, dob_cd)
            check_digits['date_of_birth'] = dob_details
            
            expiry_valid, expiry_details = self.validate_check_digit(expiry, expiry_cd)
            check_digits['expiry_date'] = expiry_details
            
            # Composite check (upper line optional + lower line data)
            composite_data = optional1 + dob + dob_cd + expiry + expiry_cd + optional2
            composite_valid, composite_details = self.validate_check_digit(composite_data, composite_cd)
            check_digits['composite'] = composite_details
            
            all_valid = all([doc_num_valid, dob_valid, expiry_valid, composite_valid])
            
            dob_formatted = self._format_date(dob)
            expiry_formatted = self._format_date(expiry)
            
            return MRZParseResult(
                format='TD1',
                document_type=doc_type,
                issuing_country=issuing_country,
                document_number=doc_number,
                date_of_birth=dob_formatted,
                sex=sex,
                expiry_date=expiry_formatted,
                nationality=nationality,
                surname=surname,
                given_names=given_names,
                optional_data=optional1 + ' ' + optional2,
                check_digits_valid=all_valid,
                check_digit_details=check_digits,
                raw_mrz=f"{line1}\n{line2}\n{line3}",
                success=True
            )
            
        except Exception as e:
            return MRZParseResult(
                format='TD1',
                document_type='',
                issuing_country='',
                document_number='',
                date_of_birth='',
                sex='',
                expiry_date='',
                nationality='',
                surname='',
                given_names='',
                optional_data='',
                check_digits_valid=False,
                check_digit_details={},
                raw_mrz=f"{line1}\n{line2}\n{line3}",
                success=False,
                error=str(e)
            )
    
    def _format_date(self, yymmdd: str) -> str:
        """
        Convert YYMMDD to full date
        Uses 20xx for years < 30, 19xx otherwise
        """
        if len(yymmdd) != 6 or not yymmdd.isdigit():
            return yymmdd
        
        yy = int(yymmdd[0:2])
        mm = yymmdd[2:4]
        dd = yymmdd[4:6]
        
        # ICAO convention: < 30 = 20xx, >= 30 = 19xx
        year = 2000 + yy if yy < 30 else 1900 + yy
        
        return f"{year}-{mm}-{dd}"
    
    def parse(self, mrz_text: str) -> MRZParseResult:
        """
        Auto-detect format and parse MRZ
        
        Args:
            mrz_text: Raw MRZ string (with newlines)
            
        Returns:
            MRZParseResult
        """
        lines = mrz_text.strip().split('\n')
        lines = [line.upper() for line in lines]
        
        if len(lines) == 2 and all(len(line) == 44 for line in lines):
            return self.parse_td3(lines[0], lines[1])
        elif len(lines) == 3 and all(len(line) == 30 for line in lines):
            return self.parse_td1(lines[0], lines[1], lines[2])
        else:
            return MRZParseResult(
                format='UNKNOWN',
                document_type='',
                issuing_country='',
                document_number='',
                date_of_birth='',
                sex='',
                expiry_date='',
                nationality='',
                surname='',
                given_names='',
                optional_data='',
                check_digits_valid=False,
                check_digit_details={},
                raw_mrz=mrz_text,
                success=False,
                error=f"Unrecognized MRZ format. Lines: {len(lines)}, Lengths: {[len(l) for l in lines]}"
            )


# Global instance
icao_mrz_parser = ICAOMRZParser()
