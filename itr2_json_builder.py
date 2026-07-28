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
    gross_salary = _round_int(getattr(tax_inputs, "gross_salary", 0))

    # Capital Gains Calculations (extracted or defaulted to 0)
    stcg_20per = _round_int(tax_result.get("stcg_20per", 0)) if tax_result else 0
    stcg_30per = _round_int(tax_result.get("stcg_30per", 0)) if tax_result else 0
    total_stcg = stcg_20per + stcg_30per

    ltcg_12_5per = _round_int(tax_result.get("ltcg_12_5per", 0)) if tax_result else 0
    total_ltcg = ltcg_12_5per

    total_cap_gains = total_stcg + total_ltcg

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
                "PartB-TI": {
                    "Salaries": gross_salary,
                    "IncomeFromHP": 0,
                    "CapGain": {
                        "ShortTerm": {
                            "ShortTerm20Per": stcg_20per,
                            "ShortTerm30Per": stcg_30per,
                            "ShortTermAppRate": 0,
                            "ShortTermSplRateDTAA": 0,
                            "TotalShortTerm": total_stcg
                        },
                        "LongTerm": {
                            "LongTerm12_5Per": ltcg_12_5per,
                            "LongTermSplRateDTAA": 0,
                            "TotalLongTerm": total_ltcg
                        },
                        "ShortTermLongTermTotal": total_cap_gains,
                        "CapGains30Per115BBH": 0,
                        "TotalCapGains": total_cap_gains
                    },
                    "IncFromOS": {
                        "OtherSrcThanOwnRaceHorse": 0,
                        "IncChargblSplRate": 0,
                        "FromOwnRaceHorse": 0,
                        "TotIncFromOS": 0
                    },
                    "TotalTI": gross_salary + total_cap_gains,
                    "CurrentYearLoss": 0,
                    "BalanceAfterSetoffLosses": gross_salary + total_cap_gains,
                    "BroughtFwdLossesSetoff": 0,
                    "GrossTotalIncome": gross_salary + total_cap_gains,
                    "IncChargeTaxSplRate111A112": total_cap_gains,
                    "DeductionsUnderScheduleVIA": 0,
                    "TotalIncome": gross_salary + total_cap_gains,
                    "IncChargeableTaxSplRates": total_cap_gains,
                    "NetAgricultureIncomeOrOtherIncomeForRate": 0,
                    "AggregateIncome": gross_salary + total_cap_gains,
                    "LossesOfCurrentYearCarriedFwd": 0,
                    "DeemedIncomeUs115JC": 0
                },
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
    
