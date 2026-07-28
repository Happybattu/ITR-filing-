"""
tax_calculator.py
Old vs New regime tax calculator — FY 2025-26 (AY 2026-27)
Source: Finance Act 2025 slabs, confirmed unchanged by Budget 2026.

NOTE: Slabs/rebates change every budget. Update SLABS_NEW / SLABS_OLD
and REBATE constants each year before relying on this.
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# FY 2025-26 (AY 2026-27) constants
# ---------------------------------------------------------------------------

SLABS_NEW = [
    (400000, 0.00),
    (800000, 0.05),
    (1200000, 0.10),
    (1600000, 0.15),
    (2000000, 0.20),
    (2400000, 0.25),
    (float("inf"), 0.30),
]

SLABS_OLD_BELOW60 = [
    (250000, 0.00),
    (500000, 0.05),
    (1000000, 0.20),
    (float("inf"), 0.30),
]

SLABS_OLD_SENIOR = [  # 60-80 yrs
    (300000, 0.00),
    (500000, 0.05),
    (1000000, 0.20),
    (float("inf"), 0.30),
]

SLABS_OLD_SUPER_SENIOR = [  # 80+ yrs
    (500000, 0.00),
    (1000000, 0.20),
    (float("inf"), 0.30),
]

STD_DEDUCTION_NEW = 75000
STD_DEDUCTION_OLD = 50000

REBATE_87A_NEW = {"threshold": 1200000, "max_rebate": 60000}
REBATE_87A_OLD = {"threshold": 500000, "max_rebate": 12500}

CESS_RATE = 0.04

SURCHARGE_SLABS = [
    (5000000, 0.00),
    (10000000, 0.10),
    (20000000, 0.15),
    (50000000, 0.25),
    (float("inf"), 0.25),  # New regime caps surcharge at 25% (no 37% band)
]
SURCHARGE_SLABS_OLD = [
    (5000000, 0.00),
    (10000000, 0.10),
    (20000000, 0.15),
    (50000000, 0.25),
    (float("inf"), 0.37),  # Old regime retains 37% above 5 Cr
]


@dataclass
class TaxInputs:
    gross_salary: float = 0.0
    other_income: float = 0.0          # interest, misc, non-STCG/LTCG
    stcg_111a: float = 0.0             # short-term capital gains (equity, 20%)
    ltcg_112a: float = 0.0             # long-term capital gains (equity, 12.5% above 1.25L exempt)
    age_band: str = "below60"          # below60 | senior | super_senior
    
    # Old-regime-only deductions
    deduction_80c: float = 0.0         # cap 150000
    deduction_80d: float = 0.0         # health insurance
    sec_80c: float = 0.0               # Field alias for app.py compatibility
    sec_80d: float = 0.0               # Field alias for app.py compatibility
    hra_exemption: float = 0.0
    home_loan_interest: float = 0.0    # section 24b, cap 200000 self-occupied
    other_deductions: float = 0.0      # 80CCD(1B), 80E, 80G etc.
    tds_paid: float = 0.0              # from Form 16 / 26AS

    def __post_init__(self):
        # Synchronize sec_80c / deduction_80c and sec_80d / deduction_80d
        if self.sec_80c > 0 and self.deduction_80c == 0:
            self.deduction_80c = self.sec_80c
        elif self.deduction_80c > 0 and self.sec_80c == 0:
            self.sec_80c = self.deduction_80c

        if self.sec_80d > 0 and self.deduction_80d == 0:
            self.deduction_80d = self.sec_80d
        elif self.deduction_80d > 0 and self.sec_80d == 0:
            self.sec_80d = self.deduction_80d


def _slab_tax(taxable: float, slabs: list[tuple[float, float]]) -> float:
    tax = 0.0
    lower = 0.0
    for upper, rate in slabs:
        if taxable > lower:
            tax += (min(taxable, upper) - lower) * rate
        lower = upper
        if taxable <= upper:
            break
    return tax


def _surcharge(tax_before_cess: float, total_income: float, slabs: list[tuple[float, float]]) -> float:
    for upper, rate in slabs:
        if total_income <= upper:
            return tax_before_cess * rate
    return 0.0


def _cg_tax(stcg: float, ltcg: float) -> float:
    """Capital gains taxed at special rates, same under both regimes."""
    ltcg_taxable = max(0.0, ltcg - 125000)  # 1.25L exemption per FY25-26 rules
    return stcg * 0.20 + ltcg_taxable * 0.125


def compute_new_regime(i: TaxInputs) -> dict:
    taxable_salary = max(0.0, i.gross_salary - STD_DEDUCTION_NEW)
    taxable_ordinary = taxable_salary + i.other_income
    cg_tax = _cg_tax(i.stcg_111a, i.ltcg_112a)
    total_income = taxable_ordinary + i.stcg_111a + i.ltcg_112a

    slab_tax = _slab_tax(taxable_ordinary, SLABS_NEW)
    tax_before_rebate = slab_tax + cg_tax

    # 87A rebate applies only if TOTAL taxable income
    rebate = 0.0
    if taxable_ordinary <= REBATE_87A_NEW["threshold"]:
        rebate = min(slab_tax, REBATE_87A_NEW["max_rebate"])

    tax_after_rebate = max(0.0, tax_before_rebate - rebate)
    surcharge = _surcharge(tax_after_rebate, total_income, SURCHARGE_SLABS)
    cess = (tax_after_rebate + surcharge) * CESS_RATE
    total_tax = tax_after_rebate + surcharge + cess

    return {
        "regime": "new",
        "taxable_income": round(taxable_ordinary + i.stcg_111a + max(0, i.ltcg_112a - 125000), 2),
        "slab_tax": round(slab_tax, 2),
        "capital_gains_tax": round(cg_tax, 2),
        "rebate_87a": round(rebate, 2),
        "surcharge": round(surcharge, 2),
        "cess": round(cess, 2),
        "total_tax": round(total_tax, 2),
        "tds_paid": i.tds_paid,
        "net_payable_or_refund": round(total_tax - i.tds_paid, 2),
    }


def compute_old_regime(i: TaxInputs) -> dict:
    slabs = {
        "below60": SLABS_OLD_BELOW60,
        "senior": SLABS_OLD_SENIOR,
        "super_senior": SLABS_OLD_SUPER_SENIOR,
    }[i.age_band]

    taxable_salary = max(0.0, i.gross_salary - STD_DEDUCTION_OLD - i.hra_exemption)
    chapter_via = min(i.deduction_80c, 150000) + i.deduction_80d + i.other_deductions
    home_loan = min(i.home_loan_interest, 200000)

    taxable_ordinary = max(
        0.0, taxable_salary + i.other_income - chapter_via - home_loan
    )
    cg_tax = _cg_tax(i.stcg_111a, i.ltcg_112a)
    total_income = taxable_ordinary + i.stcg_111a + i.ltcg_112a

    slab_tax = _slab_tax(taxable_ordinary, slabs)
    tax_before_rebate = slab_tax + cg_tax

    rebate = 0.0
    if taxable_ordinary <= REBATE_87A_OLD["threshold"]:
        rebate = min(slab_tax, REBATE_87A_OLD["max_rebate"])

    tax_after_rebate = max(0.0, tax_before_rebate - rebate)
    surcharge = _surcharge(tax_after_rebate, total_income, SURCHARGE_SLABS_OLD)
    cess = (tax_after_rebate + surcharge) * CESS_RATE
    total_tax = tax_after_rebate + surcharge + cess

    return {
        "regime": "old",
        "taxable_income": round(taxable_ordinary + i.stcg_111a + max(0, i.ltcg_112a - 125000), 2),
        "slab_tax": round(slab_tax, 2),
        "capital_gains_tax": round(cg_tax, 2),
        "rebate_87a": round(rebate, 2),
        "surcharge": round(surcharge, 2),
        "cess": round(cess, 2),
        "total_tax": round(total_tax, 2),
        "tds_paid": i.tds_paid,
        "net_payable_or_refund": round(total_tax - i.tds_paid, 2),
        "deductions_claimed": round(chapter_via + home_loan + i.hra_exemption + STD_DEDUCTION_OLD, 2),
    }


def compare_regimes(i: TaxInputs) -> dict:
    new = compute_new_regime(i)
    old = compute_old_regime(i)
    better = "new" if new["total_tax"] <= old["total_tax"] else "old"
    savings = abs(new["total_tax"] - old["total_tax"])
    
    # Fully compatible dictionary structure for app.py
    return {
        "new": new,
        "old": old,
        "new_regime": new,
        "old_regime": old,
        "recommended": better,
        "recommended_regime": better,
        "savings": round(savings, 2),
    }


if __name__ == "__main__":
    sample = TaxInputs(
        gross_salary=1500000,
        other_income=20000,
        sec_80c=150000,
        sec_80d=25000,
        hra_exemption=120000,
        tds_paid=145000,
    )
    result = compare_regimes(sample)
    import json
    print(json.dumps(result, indent=2))
    
