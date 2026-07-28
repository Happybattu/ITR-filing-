from datetime import date

def _round_int(x) -> int:
    """Ensure strict integer output for ITR schema fields."""
    if x is None:
        return 0
    return int(round(float(x)))


def build_itr2_json(
    *,
    personal_info: dict,
    form16: dict,
    tax_inputs,          # tax_calculator.TaxInputs
    tax_result: dict,    # tax comparison dictionary
    cg_trades: list,     # capital gain trades
    filing_regime: str,  # "new" or "old"
    bank_account: dict,
) -> dict:
    """
    Builds an ITR JSON matching the official e-filing schema layout.
    """
    
    # Calculate salary & deductions
    gross_salary = _round_int(tax_inputs.gross_salary)
    std_deduction = 75000 if filing_regime == "new" else 50000
    net_salary = max(0, gross_salary - std_deduction)
    
    # Chapter VI-A deductions (disallowed under New Regime)
    d80c = 0 if filing_regime == "new" else _round_int(min(tax_inputs.deduction_80c, 150000))
    d80d = 0 if filing_regime == "new" else _round_int(tax_inputs.deduction_80d)

    # Capital gains totals
    stcg_total = sum(t["pnl"] for t in cg_trades if t.get("term") == "ST")
    ltcg_total = sum(t["pnl"] for t in cg_trades if t.get("term") == "LT")

    # Construct schema matching the official e-filing JSON structure
    itr_json = {
        "personalInfo": {
            "fatherName": personal_info.get("father_name", ""),
            "assesseeName": {
                "firstName": personal_info.get("first_name", ""),
                "surNameOrOrgName": personal_info.get("surname", "")
            },
            "pan": personal_info.get("pan", "").upper(),
            "aadhaarCardNo": personal_info.get("aadhaar", ""),
            "dob": personal_info.get("dob", ""),
            "status": "I",
            "address": {
                "residenceNo": personal_info.get("address_line", ""),
                "residenceName": "",
                "roadOrStreet": personal_info.get("locality", ""),
                "localityOrArea": personal_info.get("locality", ""),
                "cityOrTownOrDistrict": personal_info.get("city", ""),
                "stateCode": str(personal_info.get("state_code", "26")),
                "countryCode": "91",
                "pinCode": _round_int(personal_info.get("pincode", 0)),
                "countryCodeMobile": 91,
                "mobileNo": _round_int(personal_info.get("mobile", 0)),
                "emailAddress": personal_info.get("email", "")
            }
        },
        "filingStatus": {
            "residentialStatus": "RES",
            "OptOutNewTaxRegime": "N" if filing_regime == "new" else "Y",
            "SeventhProvisio139": "N",
            "ItrFilingDueDate": "2026-07-31"
        },
        "form26as": {
            "tdsOnSalaries": {
                "tdsOnSalary": [
                    {
                        "employerOrDeductorOrCollectDetl": {
                            "employerOrDeductorOrCollecterName": form16.get("employer_name", "EMPLOYER"),
                            "tan": form16.get("tan", "TAN123456X")
                        },
                        "incChrgSal": gross_salary,
                        "totalTDSSal": _round_int(tax_inputs.tds_paid)
                    }
                ]
            },
            "scheduleOS": {
                "incOthThanOwnRaceHorse": {
                    "dividendGross": _round_int(tax_inputs.other_income),
                    "DividendOthThan22e": _round_int(tax_inputs.other_income)
                }
            }
        },
        "insights": {
            "salaries": {
                "salary": [
                    {
                        "nameOfEmployer": form16.get("employer_name", "EMPLOYER"),
                        "tanOfEmployer": form16.get("tan", "TAN123456X"),
                        "salarys": {
                            "salary": gross_salary,
                            "valueOfPerquisites": 0,
                            "profitsinLieuOfSalary": 0
                        }
                    }
                ]
            }
        },
        "bankAccountDtls": [
            {
                "addtnlBankDetails": [
                    {
                        "bankName": bank_account.get("bank_name", ""),
                        "bankAccountNo": bank_account.get("account_no", ""),
                        "ifsccode": bank_account.get("ifsc", "").upper(),
                        "AccountType": "SB",
                        "useForRefund": "true"
                    }
                ]
            }
        ],
        "verification": {
            "declaration": {
                "assesseeVerName": f"{personal_info.get('first_name', '')} {personal_info.get('surname', '')}".strip(),
                "fatherName": personal_info.get("father_name", ""),
                "assesseeVerPAN": personal_info.get("pan", "").upper()
            },
            "capacity": "S"
        }
    }

    return itr_json
