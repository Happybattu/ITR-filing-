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
from capital_gains_parser import parse_broker_pnl
from tax_calculator import TaxInputs, compare_regimes
from itr2_json_builder import build_itr2_json, save_itr2_json

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

# --- Step 1b: Broker capital gains upload -----------------------------------
st.header("1b. Upload broker capital gains P&L (optional)")
st.caption("Zerodha Console 'Tax P&L' export, or similar CSV/Excel from your broker")
broker_file = st.file_uploader("Broker P&L file", type=["csv", "xlsx", "xls"], key="broker_upload")

if "cg_totals" not in st.session_state:
    st.session_state.cg_totals = {"stcg_total": 0.0, "ltcg_total": 0.0}
if "cg_trades" not in st.session_state:
    st.session_state.cg_trades = []

if broker_file is not None:
    suffix = "." + broker_file.name.split(".")[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(broker_file.read())
        tmp_path = tmp.name

    try:
        cg_result = parse_broker_pnl(tmp_path)
        st.session_state.cg_totals = {
            "stcg_total": cg_result["stcg_total"],
            "ltcg_total": cg_result["ltcg_total"],
        }
        st.session_state.cg_trades = cg_result["trades"]
        st.success(f"Parsed {cg_result['trade_count']} trade(s): STCG ₹{cg_result['stcg_total']:,.0f}, LTCG ₹{cg_result['ltcg_total']:,.0f}")
        for w in cg_result["warnings"]:
            st.warning(w)
        with st.expander("Trade-by-trade breakdown"):
            st.dataframe(cg_result["trades"])
    except Exception as e:
        st.error(f"Couldn't parse this file automatically ({e}). Enter STCG/LTCG totals manually below.")
    finally:
        os.unlink(tmp_path)

# --- Step 2: Editable fields -------------------------------------------------
st.header("2. Verify / enter your figures")

col1, col2 = st.columns(2)
with col1:
    gross_salary = st.number_input("Gross salary (₹)", value=float(st.session_state.fields["gross_salary"]), step=1000.0)
    other_income = st.number_input("Other income — interest, etc. (₹)", value=0.0, step=1000.0)
    stcg = st.number_input("Short-term capital gains — equity, 111A (₹)", value=float(st.session_state.cg_totals["stcg_total"]), step=1000.0)
    ltcg = st.number_input("Long-term capital gains — equity, 112A (₹)", value=float(st.session_state.cg_totals["ltcg_total"]), step=1000.0)
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

    # Persist so Step 4 (JSON export) can use these after this rerun
    st.session_state.last_inputs = inputs
    st.session_state.last_result = result

# --- Step 4: Generate ITR-2 JSON ---------------------------------------------
st.header("4. Generate ITR-2 JSON (draft)")
st.caption(
    "Scope: salary + equity STCG/LTCG + 80C/80D only. No house property, foreign "
    "assets, or business income. Run step 3 first."
)

if "last_result" not in st.session_state:
    st.info("Click **Compare old vs new regime** in step 3 first — the JSON builder needs that output.")
else:
    regime_choice = st.radio(
        "File under which regime?",
        ["new", "old"],
        index=0 if st.session_state.last_result["recommended"] == "new" else 1,
        horizontal=True,
        format_func=lambda x: "New Regime" if x == "new" else "Old Regime",
    )

    with st.expander("Personal & bank details (required for the JSON — nothing is pre-filled)", expanded=True):
        pc1, pc2 = st.columns(2)
        with pc1:
            first_name = st.text_input("First name")
            surname = st.text_input("Surname")
            father_name = st.text_input("Father's name")
            pan = st.text_input("PAN", max_chars=10, help="Format: ABCDE1234F")
            aadhaar = st.text_input("Aadhaar number (12 digits)", max_chars=12)
            dob = st.date_input("Date of birth")
        with pc2:
            address_line = st.text_input("Address (house/flat, street)")
            locality = st.text_input("Locality / area")
            city = st.text_input("City", value="Jalandhar")
            state_code = st.text_input("State code (2 digits — see ITR-2 schema list)", value="26", help="Punjab=26, Delhi=09, etc.")
            pincode = st.number_input("PIN code", min_value=100000, max_value=999999, step=1, value=144001)
            mobile = st.number_input("Mobile number", min_value=1000000000, max_value=9999999999, step=1, value=9999999999)
            email = st.text_input("Email")

        st.markdown("**Bank account (for refund)**")
        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            bank_name = st.text_input("Bank name")
        with bc2:
            account_no = st.text_input("Account number")
        with bc3:
            ifsc = st.text_input("IFSC code")

    if st.button("Generate ITR-2 JSON", type="primary"):
        missing = [
            label for label, val in [
                ("First name", first_name), ("Surname", surname), ("PAN", pan),
                ("Aadhaar", aadhaar), ("Address", address_line), ("Locality", locality),
                ("City", city), ("Email", email), ("Bank name", bank_name),
                ("Account number", account_no), ("IFSC", ifsc),
            ] if not val
        ]
        if missing:
            st.error(f"Missing required fields: {', '.join(missing)}")
        else:
            personal_info = {
                "first_name": first_name, "surname": surname, "father_name": father_name,
                "pan": pan.upper(), "aadhaar": aadhaar, "dob": dob.isoformat(),
                "address_line": address_line, "locality": locality, "city": city,
                "state_code": state_code, "pincode": int(pincode), "mobile": int(mobile),
                "email": email,
            }
            bank_account = {"ifsc": ifsc.upper(), "bank_name": bank_name, "account_no": account_no}

            try:
                itr_json = build_itr2_json(
                    personal_info=personal_info,
                    form16={"employer_name": ""},
                    tax_inputs=st.session_state.last_inputs,
                    tax_result=st.session_state.last_result[regime_choice],
                    cg_trades=st.session_state.cg_trades,
                    filing_regime=regime_choice,
                    bank_account=bank_account,
                )
                json_str = __import__("json").dumps(itr_json, indent=2)
                st.success("JSON generated. Download it and validate in the official offline utility before uploading anywhere.")
                st.download_button(
                    "Download ITR-2 JSON",
                    data=json_str,
                    file_name="itr2_draft.json",
                    mime="application/json",
                )
                with st.expander("Preview JSON"):
                    st.json(itr_json)
            except Exception as e:
                st.error(f"Couldn't build the JSON: {e}")

    st.caption(
        "This JSON matches the AY 2026-27 schema shape but has NOT been checked against "
        "the department's cross-field validation rules. Always run it through the "
        "official Excel/online utility before submitting."
    )
    
