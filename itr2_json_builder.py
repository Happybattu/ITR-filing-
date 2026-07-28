"""
itr2_json_builder.py
Builds an ITR-2 JSON (AY 2026-27) for the common case: salaried individual
with equity STCG/LTCG, no house property, no foreign assets, no business
income. Schema fetched directly from incometax.gov.in on 2026-07-28
(ITR-2_2026_Main_V1.1.json) — required fields and patterns below are taken
from that file, not guessed.

SCOPE (deliberately narrow):
  Included : PersonalInfo, FilingStatus, ScheduleS (salary), Schedule112A
             (LTCG equity via STT), ScheduleCGFor23 (STCG equity 111A),
             Schedule80C/80D, PartB-TI, PartB_TTI, TaxesPaid, Verification
  Excluded : House property, foreign assets/income, business/professional
             income, ESOP deferred tax, AMT, non-equity capital gains
             (debt funds, property, unlisted shares). If any of these
             apply to you, this JSON will be incomplete — don't upload it.

IMPORTANT: This produces a schema-shaped JSON, not a portal-guaranteed-
valid one. The e-filing utility runs additional cross-field validation
rules (CBDT_e-Filing_ITR_2_Validation_Rules) beyond the JSON schema shape.
Always open the generated JSON in the official Excel/online utility and
let it validate before submitting — treat this as a first draft, not a
final filing artifact.
"""

import json
from datetime import date


def _round_int(x: float) -> int:
    """ITR schema fields are integers (rupees, no paise)."""
    return int(round(x))


def build_itr2_json(
    *,
    personal_info: dict,
    form16: dict,
    tax_inputs,          # tax_calculator.TaxInputs
    tax_result: dict,    # one of compare_regimes(...)["new"] or ["old"]
    cg_trades: list,      # from capital_gains_parser.parse_broker_pnl(...)["trades"]
    filing_regime: str,   # "new" or "old"
    bank_account: dict,
) -> dict:
    """
    personal_info = {
        "first_name": str, "surname": str, "pan": str, "dob": "YYYY-MM-DD",
        "aadhaar": str, "address_line": str, "locality": str, "city": str,
        "state_code": str,  # e.g. "09" for Delhi, "06" for Chandigarh/Punjab region
        "pincode": int, "mobile": int, "email": str,
    }
    bank_account = {"ifsc": str, "account_no": str, "bank_name": str, "account_type": "SB"|"CA"}
    """

    today = date.today().isoformat()

    # ---- STCG/LTCG split from parsed broker trades --------------------
    stcg_112a_eligible = sum(t["pnl"] for t in cg_trades if t["term"] == "ST")
    ltcg_112a_total = sum(t["pnl"] for t in cg_trades if t["term"] == "LT")
    ltcg_exempt = min(125000, max(0, ltcg_112a_total))
    ltcg_taxable = max(0, ltcg_112a_total - 125000)

    gross_salary = _round_int(tax_inputs.gross_salary)
    std_deduction = 75000 if filing_regime == "new" else 50000

    d80c = _round_int(min(tax_inputs.deduction_80c, 150000)) if filing_regime == "old" else 0
    d80d = _round_int(tax_inputs.deduction_80d) if filing_regime == "old" else 0

    itr = {
        "ITR": {
            "ITR2": {
                "CreationInfo": {
                    "SWVersionNo": "1.0",
                    "SWCreatedBy": "SW00000001",
                    "JSONCreatedBy": "SW00000001",
                    "JSONCreationDate": today,
                    "IntermediaryCity": personal_info.get("city", "Delhi"),
                    "Digest": "-",
                },
                "Form_ITR2": {
                    "FormName": "ITR-2",
                    "Description": "For Individuals and HUFs not having income from profits and gains of business or profession",
                    "AssessmentYear": "2026",
                    "SchemaVer": "Ver1.0",
                    "FormVer": "Ver1.0",
                },
                "PartA_GEN1": {
                    "PersonalInfo": {
                        "AssesseeName": {
                            "FirstName": personal_info["first_name"],
                            "SurNameOrOrgName": personal_info["surname"],
                        },
                        "PAN": personal_info["pan"],
                        "Address": {
                            "ResidenceNo": personal_info["address_line"],
                            "LocalityOrArea": personal_info["locality"],
                            "CityOrTownOrDistrict": personal_info["city"],
                            "StateCode": personal_info["state_code"],
                            "CountryCode": "91",
                            "PinCode": personal_info["pincode"],
                            "CountryCodeMobile": 91,
                            "MobileNo": personal_info["mobile"],
                            "EmailAddress": personal_info["email"],
                        },
                        "SecondaryAdd": "N",
                        "DOB": personal_info["dob"],
                        "Status": "I",
                        "AadhaarCardNo": personal_info["aadhaar"],
                    },
                    "FilingStatus": {
                        "ReturnFileSec": 11,
                        "OptOutNewTaxRegime": "N" if filing_regime == "new" else "Y",
                        "SeventhProvisio139": "N",
                        "ResidentialStatus": "RES",
                        "HeldUnlistedEqShrPrYrFlg": "N",
                        "FiiFpiFlag": "N",
                        "ItrFilingDueDate": "2026-07-31",
                    },
                },
                "ScheduleS": {
                    "Salaries": [
                        {
                            "NameOfEmployer": form16.get("employer_name", "").strip() or "Employer",
                            "NatureOfEmployment": "OTH",
                            "AddressDetail": {
                                "AddrDetail": personal_info["address_line"],
                                "CityOrTownOrDistrict": personal_info["city"],
                                "StateCode": personal_info["state_code"],
                            },
                            "Salarys": {
                                "GrossSalary": gross_salary,
                                "Salary": gross_salary,
                                "ValueOfPerquisites": 0,
                                "ProfitsinLieuOfSalary": 0,
                                "IncomeNotified89A": 0,
                                "IncomeNotifiedOther89A": 0,
                            },
                        }
                    ],
                    "TotalGrossSalary": gross_salary,
                    "AllwncExtentExemptUs10": 0,
                    "NetSalary": gross_salary,
                    "DeductionUS16": std_deduction,
                    "DeductionUnderSection16ia": std_deduction,
                    "EntertainmntalwncUs16ii": 0,
                    "ProfessionalTaxUs16iii": 0,
                    "TotIncUnderHeadSalaries": max(0, gross_salary - std_deduction),
                },
                # --- Short-term equity gains (section 111A, taxed @20%) ---
                "ScheduleCGFor23": {
                    "ShortTermCapGainFor23": {
                        "NRITransacSec48Dtl": {"NRItaxSTTPaid": 0, "NRItaxSTTNotPaid": 0},
                        "NRISecur115AD": {},
                        "SaleOnOtherAssets": {},
                        "EquityMFonSTT": [
                            {
                                "MFSectionCode": "1A",
                                "EquityMFonSTTDtls": {
                                    "FullValueConsdRecvUnqshr": 0,
                                    "FullValueConsdSec50CA": 0,
                                    "FullValueConsdOthUnqshr": _round_int(stcg_112a_eligible) + 0,
                                    "FullConsideration": _round_int(stcg_112a_eligible),
                                    "DeductSec48": {"AquisitCost": 0, "ImproveCost": 0, "ExpOnTrans": 0, "TotalDedn": 0},
                                    "BalanceCG": _round_int(stcg_112a_eligible),
                                    "CapgainonAssets": _round_int(stcg_112a_eligible),
                                } if stcg_112a_eligible else {
                                    "FullValueConsdRecvUnqshr": 0, "FullValueConsdSec50CA": 0,
                                    "FullValueConsdOthUnqshr": 0, "FullConsideration": 0,
                                    "DeductSec48": {"TotalDedn": 0}, "BalanceCG": 0, "CapgainonAssets": 0,
                                },
                            }
                        ],
                        "TotalAmtDeemedStcg": 0,
                        "PassThrIncNatureSTCG": 0,
                        "TotalAmtNotTaxUsDTAAStcg": 0,
                        "TotalAmtTaxUsDTAAStcg": 0,
                        "TotalSTCG": _round_int(stcg_112a_eligible),
                    },
                    "LongTermCapGain23": {
                        # LTCG on listed equity via STT goes in Schedule112A instead;
                        # this node stays empty for our scope (no property/unlisted shares)
                        "UnutilizedLtcgFlag": "X",
                        "TotalAmtDeemedLtcg": 0,
                        "PassThrIncNatureLTCG": 0,
                        "TotalAmtNotTaxUsDTAALtcg": 0,
                    },
                    "SumOfCGIncm": _round_int(stcg_112a_eligible + ltcg_taxable),
                    "IncmFromVDATrnsf": 0,
                    "TotScheduleCGFor23": _round_int(stcg_112a_eligible + ltcg_taxable),
                    "CurrYrLosses": {},
                    "AccruOrRecOfCG": {},
                },
                # --- Long-term equity gains (section 112A, taxed @12.5% above 1.25L) ---
                "Schedule112A": {
                    "Schedule112ADtls": [
                        {
                            "ShareOnOrBefore": "N",
                            "ISIN": t.get("symbol", "")[:12] or "NA",
                            "ShareUnitName": t.get("symbol", "Equity"),
                            "NumSharesUnits": 1,
                            "SalePricePerShareUnit": _round_int(t["pnl"]) if t["pnl"] else 0,
                            "FullConsiderationValue": _round_int(t["pnl"]),
                            "TotalFairMktValueSale": 0,
                            "TotalSaleValueAsper50": 0,
                            "COAWihoutIndx": 0,
                            "FMV": 0,
                            "COAWithIndx": 0,
                            "TotExpOnTransfer": 0,
                        }
                        for t in cg_trades if t["term"] == "LT"
                    ] or [],
                    "SaleValue112A": _round_int(ltcg_112a_total),
                    "CostAcqWithoutIndx112A": 0,
                    "AcquisitionCost112A": 0,
                    "LTCGBeforelowerB1B2112A": _round_int(ltcg_112a_total),
                    "FairMktValueCapAst112A": 0,
                    "ExpExclCnctTransfer112A": 0,
                    "Deductions112A": _round_int(ltcg_exempt),
                    "Balance112A": _round_int(ltcg_taxable),
                    "TotalBalance112A": _round_int(ltcg_taxable),
                },
                "ScheduleVIA": {
                    "UsrDeductUndChapVIA": {
                        "Section80C": d80c,
                        "Section80D": d80d,
                    },
                    "TotalChapVIADeductions": d80c + d80d,
                } if filing_regime == "old" else {},
                "Schedule80C": {
                    "Section80C": {"TotalDeductionUs80C": d80c}
                } if d80c else {},
                "Schedule80D": {
                    "Section80D": {"TotalDeductionUs80D": d80d}
                } if d80d else {},
                "PartB-TI": {
                    "Salaries": max(0, gross_salary - std_deduction),
                    "IncomeFromHP": 0,
                    "CapGain": {
                        "ShortTerm": {
                            "ShortTerm20Per": _round_int(stcg_112a_eligible),
                            "ShortTerm30Per": 0,
                            "ShortTermAppRate": 0,
                            "ShortTermSplRateDTAA": 0,
                            "TotalShortTerm": _round_int(stcg_112a_eligible),
                        },
                        "LongTerm": {
                            "LongTerm12_5Per": _round_int(ltcg_taxable),
                            "LongTermSplRateDTAA": 0,
                            "TotalLongTerm": _round_int(ltcg_taxable),
                        },
                        "ShortTermLongTermTotal": _round_int(stcg_112a_eligible + ltcg_taxable),
                        "CapGains30Per115BBH": 0,
                        "TotalCapGains": _round_int(stcg_112a_eligible + ltcg_taxable),
                    },
                    "IncFromOS": {
                        "OtherSrcThanOwnRaceHorse": _round_int(tax_inputs.other_income),
                        "IncChargblSplRate": 0,
                        "FromOwnRaceHorse": 0,
                        "TotIncFromOS": _round_int(tax_inputs.other_income),
                    },
                    "TotalTI": _round_int(
                        max(0, gross_salary - std_deduction) + stcg_112a_eligible + ltcg_taxable + tax_inputs.other_income
                    ),
                    "CurrentYearLoss": 0,
                    "BalanceAfterSetoffLosses": _round_int(
                        max(0, gross_salary - std_deduction) + stcg_112a_eligible + ltcg_taxable + tax_inputs.other_income
                    ),
                    "BroughtFwdLossesSetoff": 0,
                    "GrossTotalIncome": _round_int(
                        max(0, gross_salary - std_deduction) + stcg_112a_eligible + ltcg_taxable + tax_inputs.other_income
                    ),
                    "IncChargTaxSplRate111A112": _round_int(stcg_112a_eligible + ltcg_taxable),
                    "DeductionsUnderScheduleVIA": d80c + d80d,
                    "TotalIncome": tax_result["taxable_income"],
                    "IncChargeableTaxSplRates": _round_int(stcg_112a_eligible + ltcg_taxable),
                    "NetAgricultureIncomeOrOtherIncomeForRate": 0,
                    "AggregateIncome": tax_result["taxable_income"],
                    "LossesOfCurrentYearCarriedFwd": 0,
                    "DeemedIncomeUs115JC": 0,
                },
                "PartB_TTI": {
                    "TaxPayDeemedTotIncUs115JC": 0,
                    "Surcharge": tax_result["surcharge"],
                    "HealthEduCess": tax_result["cess"],
                    "TotalTaxPayablDeemedTotInc": 0,
                    "ComputationOfTaxLiability": {
                        "TaxPayableOnTI": {
                            "TaxAtNormalRatesOnAggrInc": tax_result["slab_tax"],
                            "TaxAtSpecialRates": tax_result["capital_gains_tax"],
                            "RebateOnAgriInc": 0,
                            "TaxPayableOnTotInc": tax_result["slab_tax"] + tax_result["capital_gains_tax"],
                        },
                        "Rebate87A": tax_result["rebate_87a"],
                        "TaxPayableOnRebate": tax_result["slab_tax"] + tax_result["capital_gains_tax"] - tax_result["rebate_87a"],
                        "Surcharge25ofSI": 0,
                        "SurchargeOnAboveCrore": tax_result["surcharge"],
                        "Surcharge25ofSIBeforeMarginal": 0,
                        "SurchargeOnAboveCroreBeforeMarginal": tax_result["surcharge"],
                        "TotalSurcharge": tax_result["surcharge"],
                        "EducationCess": tax_result["cess"],
                        "GrossTaxLiability": tax_result["total_tax"],
                        "GrossTaxPayable": tax_result["total_tax"],
                        "CreditUS115JD": 0,
                        "TaxPayAfterCreditUs115JD": tax_result["total_tax"],
                        "NetTaxLiability": tax_result["total_tax"],
                        "IntrstPay": {
                            "IntrstPayUs234A": 0, "IntrstPayUs234B": 0, "IntrstPayUs234C": 0,
                            "LateFilingFee234F": 0, "TotalIntrstPay": 0,
                        },
                        "AggregateTaxInterestLiability": tax_result["total_tax"],
                    },
                    "TaxPaid": {
                        "TaxesPaid": {
                            "AdvanceTax": 0,
                            "TDS": _round_int(tax_inputs.tds_paid),
                            "TCS": 0,
                            "SelfAssessmentTax": 0,
                            "TotalTaxesPaid": _round_int(tax_inputs.tds_paid),
                        },
                        "BalTaxPayable": max(0, _round_int(tax_result["net_payable_or_refund"])),
                    },
                    "Refund": {
                        "RefundDue": max(0, -_round_int(tax_result["net_payable_or_refund"])),
                        "BankAccountDtls": {
                            "BankDtlsFlag": "Y",
                            "AddtnlBankDetails": [
                                {
                                    "IFSCCode": bank_account["ifsc"],
                                    "BankName": bank_account["bank_name"],
                                    "BankAccountNo": bank_account["account_no"],
                                    "AccountType": bank_account.get("account_type", "SB"),
                                }
                            ],
                        },
                    },
                    "AssetOutIndiaFlag": "NO",
                },
                "Verification": {
                    "Declaration": {
                        "AssesseeVerName": f"{personal_info['first_name']} {personal_info['surname']}",
                        "FatherName": personal_info.get("father_name", "NA"),
                        "AssesseeVerPAN": personal_info["pan"],
                    },
                    "Capacity": "S",
                    "Date": today,
                    "Place": personal_info["city"],
                },
            }
        }
    }

    return itr


def save_itr2_json(itr_dict: dict, output_path: str) -> None:
    with open(output_path, "w") as f:
        json.dump(itr_dict, f, indent=2)


if __name__ == "__main__":
    # Smoke test with dummy data — NOT real filing data
    from tax_calculator import TaxInputs, compare_regimes

    dummy_personal = {
        "first_name": "Test", "surname": "User", "pan": "ABCDE1234F",
        "dob": "1990-01-01", "aadhaar": "123456789012",
        "address_line": "123 Test Street", "locality": "Test Locality",
        "city": "Delhi", "state_code": "09", "pincode": 110001,
        "mobile": 9999999999, "email": "test@example.com",
        "father_name": "Father Name",
    }
    dummy_bank = {"ifsc": "HDFC0000001", "bank_name": "HDFC Bank", "account_no": "123456789012"}
    dummy_form16 = {"employer_name": "Test Employer Pvt Ltd"}
    dummy_trades = [
        {"symbol": "RELIANCE", "term": "ST", "pnl": 2500.0},
        {"symbol": "TCS", "term": "LT", "pnl": 3500.0},
    ]

    inputs = TaxInputs(gross_salary=1500000, tds_paid=145000, stcg_111a=2500, ltcg_112a=3500)
    result = compare_regimes(inputs)

    itr_json = build_itr2_json(
        personal_info=dummy_personal,
        form16=dummy_form16,
        tax_inputs=inputs,
        tax_result=result["new"],
        cg_trades=dummy_trades,
        filing_regime="new",
        bank_account=dummy_bank,
    )
    save_itr2_json(itr_json, "sample_itr2_output.json")
    print("Wrote sample_itr2_output.json")
    print(f"Total tax (new regime): Rs.{result['new']['total_tax']:,.0f}")
