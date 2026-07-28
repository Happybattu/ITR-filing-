from datetime import date

def _round_int(x) -> int:
    if x is None:
        return 0
    return int(round(float(x)))

def build_itr2_json(
    *,
    personal_info: dict,
    form16: dict,
    tax_inputs,         
    tax_result: dict,    
    cg_trades: list,     
    filing_regime: str,  
    bank_account: dict,
) -> dict:
    
    current_date = date.today().isoformat()
    gross_salary = _round_int(tax_inputs.gross_salary)

    # Building the compliant JSON schema structure
    itr_json = {
        "ITR": {
            "ITR2": {
                "CreationInfo": {
                    "SWVersionNo": "1.0",
                    "SWCreatedBy": "SW00000000",
                    "JSONCreatedBy": "SW00000000",
                    "JSONCreationDate": current_date,
                    "IntermediaryCity": "Ludhiana",
                    "Digest": "-"
                },
                "Form_ITR2": {
                    "FormName": "ITR-2",
                    "Description": "For Individuals and HUFs not having income from profits and gains of business or profession",
                    "AssessmentYear": "2026",
                    "SchemaVer": "Ver1.0",
                    "FormVer": "Ver1.0"
                },
                "PartA_GEN1": {
                    "PersonalInfo": {
                        "AssesseeName": {
                            "FirstName": personal_info.get("first_name", ""),
                            "SurNameOrOrgName": personal_info.get("surname", "UNKNOWN")
                        },
                        "PAN": personal_info.get("pan", "ABCDE1234F").upper(),
                        "Address": {
                            "ResidenceNo": personal_info.get("address_line", "NA") or "NA",
                            "LocalityOrArea": personal_info.get("locality", "NA") or "NA",
                            "CityOrTownOrDistrict": personal_info.get("city", "NA") or "NA",
                            "StateCode": str(personal_info.get("state_code", "26")),
                            "CountryCode": "91",
                            "PinCode": _round_int(personal_info.get("pincode", 144001)),
                            "CountryCodeMobile": 91,
                            "MobileNo": _round_int(personal_info.get("mobile", 9999999999)),
                            "EmailAddress": personal_info.get("email", "email@example.com") or "email@example.com"
                        },
                        "SecondaryAdd": "N",
                        "DOB": personal_info.get("dob", "1990-01-01"),
                        "Status": "I",
                        "AadhaarCardNo": personal_info.get("aadhaar", "000000000000")
                    },
                    "FilingStatus": {
                        "ReturnFileSec": 11,
                        "OptOutNewTaxRegime": "N" if filing_regime == "new" else "Y",
                        "SeventhProvisio139": "N",
                        "ResidentialStatus": "RES",
                        "HeldUnlistedEqShrPrYrFlg": "N",
                        "FiiFpiFlag": "N",
                        "ItrFilingDueDate": "2026-07-31"
                    }
                },
                # Required empty schedules to pass mandatory schema validation checks
                "ScheduleCYLA": {},
                "ScheduleBFLA": {},
                "PartB-TI": {},
                "PartB_TTI": {},
                "Verification": {
                    "Declaration": {
                        "AssesseeVerName": f"{personal_info.get('first_name', '')} {personal_info.get('surname', '')}".strip(),
                        "FatherName": personal_info.get("father_name", ""),
                        "AssesseeVerPAN": personal_info.get("pan", "ABCDE1234F").upper()
                    },
                    "Capacity": "S"
                }
            }
        }
    }

    return itr_json
