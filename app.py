"""
app.py — ITR Helper (personal use)
Streamlit UI: upload Form 16 -> review/edit extracted fields -> compare
old vs new regime tax liability.

Run with: streamlit run app.py
"""

import streamlit as st
import tempfile
import os

from form16_parser import parse_form16
from tax_calculator import TaxInputs, compare_regimes
from capital_gains_parser import parse_broker_pnl

st.set_page_config(page_title="ITR Helper", page_icon="🧾", layout="centered")
st.title("🧾 ITR Helper — Personal Use")
st.caption("FY 2025-26 (AY 2026-27) · Old vs New regime comparison · Not a substitute for filing on incometax.gov.in")

if "fields" not in st.session_state:
    st.session_state.fields = {
        "gross_salary": 0.0,
        "hra_exemption": 0.0,
        "deduction_80c": 0.0,
        "deduction_80d": 0.0,
        "tds_paid": 0.0,
    }

# --- Step 1: Form 16 upload -------------------------------------------------
st.header("1. Upload Form 16 (optional)")
uploaded = st.file_uploader("Form 16 PDF (Part B)", type=["pdf"])

if uploaded is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    try:
        extracted = parse_form16(tmp_path)
        st.session_state.fields.update({
            "gross_salary": extracted.get("gross_salary", 0.0),
            "hra_exemption": extracted.get("hra_exemption", 0.0),
            "deduction_80c": extracted.get("deduction_80c", 0.0),
            "deduction_80d": extracted.get("deduction_80d", 0.0),
            "tds_paid": extracted.get("tds_paid", 0.0),
        })
        if extracted.get("_extraction_warnings"):
            for w in extracted["_extraction_warnings"]:
                st.warning(w)
        else:
            st.success("Fields extracted — please verify against your Form 16 below.")
        with st.expander("Raw extracted text (first 2000 chars, for verification)"):
            st.text(extracted.get("_raw_text_preview", ""))
    except Exception as e:
        st.error(f"Couldn't parse this PDF automatically ({e}). Enter figures manually below.")
    finally:
        os.unlink(tmp_path)

# --- Step 2: Editable fields -------------------------------------------------
st.header("2. Verify / enter your figures")

col1, col2 = st.columns(2)
with col1:
    gross_salary = st.number_input("Gross salary (₹)", value=float(st.session_state.fields["gross_salary"]), step=1000.0)
    other_income = st.number_input("Other income — interest, etc. (₹)", value=0.0, step=1000.0)
    stcg = st.number_input("Short-term capital gains — equity, 111A (₹)", value=0.0, step=1000.0)
    ltcg = st.number_input("Long-term capital gains — equity, 112A (₹)", value=0.0, step=1000.0)
    age_band = st.selectbox("Age band", ["below60", "senior", "super_senior"], format_func=lambda x: {
        "below60": "Below 60", "senior": "60-80 (Senior)", "super_senior": "80+ (Super senior)"
    }[x])

with col2:
    hra = st.number_input("HRA exemption claimed (₹) — old regime only", value=float(st.session_state.fields["hra_exemption"]), step=1000.0)
    d80c = st.number_input("Section 80C (₹, max 1,50,000) — old regime only", value=float(st.session_state.fields["deduction_80c"]), step=1000.0, max_value=150000.0)
    d80d = st.number_input("Section 80D — health insurance (₹) — old regime only", value=float(st.session_state.fields["deduction_80d"]), step=500.0)
    home_loan = st.number_input("Home loan interest 24(b) (₹, max 2,00,000) — old regime only", value=0.0, step=1000.0, max_value=200000.0)
    other_ded = st.number_input("Other deductions — 80CCD(1B), 80E, 80G etc. (₹) — old regime only", value=0.0, step=1000.0)
    tds = st.number_input("Total TDS already paid (₹)", value=float(st.session_state.fields["tds_paid"]), step=1000.0)

# --- Step 3: Compute ---------------------------------------------------------
st.header("3. Regime comparison")

if st.button("Compare old vs new regime", type="primary"):
    inputs = TaxInputs(
        gross_salary=gross_salary,
        other_income=other_income,
        stcg_111a=stcg,
        ltcg_112a=ltcg,
        age_band=age_band,
        deduction_80c=d80c,
        deduction_80d=d80d,
        hra_exemption=hra,
        home_loan_interest=home_loan,
        other_deductions=other_ded,
        tds_paid=tds,
    )
    result = compare_regimes(inputs)

    c1, c2 = st.columns(2)
    for col, key, label in [(c1, "new", "New Regime"), (c2, "old", "Old Regime")]:
        r = result[key]
        with col:
            st.subheader(label)
            st.metric("Total tax liability", f"₹{r['total_tax']:,.0f}")
            st.write(f"Taxable income: ₹{r['taxable_income']:,.0f}")
            st.write(f"Slab tax: ₹{r['slab_tax']:,.0f}")
            if r["capital_gains_tax"]:
                st.write(f"Capital gains tax: ₹{r['capital_gains_tax']:,.0f}")
            if r["rebate_87a"]:
                st.write(f"87A rebate: −₹{r['rebate_87a']:,.0f}")
            if r["surcharge"]:
                st.write(f"Surcharge: ₹{r['surcharge']:,.0f}")
            st.write(f"Cess (4%): ₹{r['cess']:,.0f}")
            net = r["net_payable_or_refund"]
            if net > 0:
                st.error(f"Tax payable: ₹{net:,.0f}")
            else:
                st.success(f"Refund due: ₹{abs(net):,.0f}")

    better_label = "New Regime" if result["recommended"] == "new" else "Old Regime"
    st.info(f"**{better_label}** is better for you by **₹{result['savings']:,.0f}**")

    st.caption(
        "This is an estimate for planning purposes only — final filing must be done on "
        "incometax.gov.in or a portal registered as an ERI. Verify all figures against "
        "your Form 16, Form 26AS, and AIS/TIS before relying on this."
    )

st.divider()
st.caption("Next to build: 26AS/AIS import, capital gains CSV import from broker P&L, JSON export in ITR schema format.")
