import datetime
import json
import os
import tempfile
import streamlit as st

# Custom module imports
from capital_gains_parser import parse_broker_pnl
from form16_parser import parse_form16
from itr2_json_builder import build_itr2_json
from prefill_parser import parse_prefill_json
from tax_calculator import TaxInputs, compare_regimes

# -----------------------------------------------------------------------------
# Streamlit App Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="ITR-2 Prep & Filing Assistant",
    page_icon="📑",
    layout="wide",
)

st.title("📑 ITR-2 Income Tax Assistant & JSON Builder")
st.caption(
    "Upload your tax documents, compare Old vs. New tax regimes, auto-fill prefill data, "
    "and generate a schema-compliant ITR-2 JSON draft for direct upload."
)

# -----------------------------------------------------------------------------
# Session State Initialization
# -----------------------------------------------------------------------------
if "form16_data" not in st.session_state:
    st.session_state.form16_data = {}
if "cg_trades" not in st.session_state:
    st.session_state.cg_trades = []
if "prefill_data" not in st.session_state:
    st.session_state.prefill_data = {}
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# -----------------------------------------------------------------------------
# Step 1: File Uploads
# -----------------------------------------------------------------------------
st.header("1. Document Uploads")

col_f16, col_cg, col_pf = st.columns(3)

# --- 1a. Form-16 Upload ---
with col_f16:
    st.subheader("1a. Form-16 (PDF)")
    form16_file = st.file_uploader("Upload Form-16", type=["pdf"], key="f16_uploader")

    if form16_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(form16_file.read())
            tmp_path = tmp.name
        
        try:
            parsed_f16 = parse_form16(tmp_path)
            st.session_state.form16_data = parsed_f16
            st.success("Form-16 parsed successfully!")
            with st.expander("View Extracted Form-16"):
                st.json(parsed_f16)
        except Exception as e:
            st.error(f"Error parsing Form-16: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

# --- 1b. Capital Gains Upload ---
with col_cg:
    st.subheader("1b. Capital Gains (P&L)")
    cg_file = st.file_uploader("Upload Broker Statement", type=["xlsx", "xls", "csv"], key="cg_uploader")

    if cg_file is not None:
        file_ext = "." + cg_file.name.split(".")[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            tmp.write(cg_file.read())
            tmp_path = tmp.name
        
        try:
            parsed_cg = parse_broker_pnl(tmp_path)
            st.session_state.cg_trades = parsed_cg
            st.success(f"Parsed {len(parsed_cg)} trade record(s)!")
            with st.expander("View Capital Gains Sample"):
                st.json(parsed_cg[:5] if len(parsed_cg) > 5 else parsed_cg)
        except Exception as e:
            st.error(f"Error parsing P&L file: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

# --- 1c. Prefill JSON Upload ---
with col_pf:
    st.subheader("1c. IT Portal Prefill (JSON)")
    prefill_file = st.file_uploader("Upload IT Prefill JSON", type=["json"], key="pf_uploader")

    if prefill_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            tmp.write(prefill_file.read())
            tmp_path = tmp.name
        
        try:
            extracted_prefill = parse_prefill_json(tmp_path)
            st.session_state.prefill_data.update(extracted_prefill)
            st.success("Prefill JSON loaded successfully!")
            with st.expander("View Extracted Profile Details"):
                st.json(extracted_prefill)
        except Exception as e:
            st.error(f"Error parsing Prefill JSON: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

st.markdown("---")

# -----------------------------------------------------------------------------
# Step 2: Input Review & Manual Adjustments
# -----------------------------------------------------------------------------
st.header("2. Review & Adjust Tax Inputs")

f16 = st.session_state.form16_data

col_in1, col_in2 = st.columns(2)

with col_in1:
    gross_salary = st.number_input(
        "Gross Salary (₹)",
        value=float(f16.get("gross_salary", 0.0)),
        step=1000.0,
    )
    sec_80c = st.number_input(
        "Section 80C Deductions (₹)",
        value=float(f16.get("sec_80c", 0.0)),
        step=1000.0,
    )
    sec_80d = st.number_input(
        "Section 80D Health Insurance (₹)",
        value=float(f16.get("sec_80d", 0.0)),
        step=1000.0,
    )

with col_in2:
    stcg_111a = st.number_input("Equity STCG Sec 111A (₹)", value=0.0, step=1000.0)
    ltcg_112a = st.number_input("Equity LTCG Sec 112A (₹)", value=0.0, step=1000.0)
    tds_paid = st.number_input(
        "TDS Paid (Form 26AS / Form 16) (₹)",
        value=float(f16.get("tds_paid", 0.0)),
        step=1000.0,
    )

st.markdown("---")

# -----------------------------------------------------------------------------
# Step 3: Tax Regime Comparison
# -----------------------------------------------------------------------------
st.header("3. Compare Tax Regimes (Old vs. New)")

if st.button("Calculate & Compare Tax Regimes", type="primary"):
    tax_inputs = TaxInputs(
        gross_salary=gross_salary,
        sec_80c=sec_80c,
        sec_80d=sec_80d,
        stcg_111a=stcg_111a,
        ltcg_112a=ltcg_112a,
        tds_paid=tds_paid,
    )
    comparison_res = compare_regimes(tax_inputs)
    st.session_state.last_result = {
        "inputs": tax_inputs,
        "comparison": comparison_res,
        "recommended": comparison_res["recommended_regime"],
    }

if st.session_state.last_result is not None:
    res = st.session_state.last_result["comparison"]
    st.subheader(f"💡 Recommended Regime: **{res['recommended_regime'].upper()} REGIME**")
    
    col_reg1, col_reg2 = st.columns(2)
    with col_reg1:
        st.markdown("#### Old Tax Regime")
        st.write(f"**Taxable Income:** ₹{res['old_regime']['taxable_income']:,.2f}")
        st.write(f"**Total Tax Payable:** ₹{res['old_regime']['total_tax']:,.2f}")
    with col_reg2:
        st.markdown("#### New Tax Regime")
        st.write(f"**Taxable Income:** ₹{res['new_regime']['taxable_income']:,.2f}")
        st.write(f"**Total Tax Payable:** ₹{res['new_regime']['total_tax']:,.2f}")

st.markdown("---")

# -----------------------------------------------------------------------------
# Step 4: Personal Details & ITR-2 JSON Generation
# -----------------------------------------------------------------------------
st.header("4. Generate Schema-Compliant ITR-2 JSON")

if st.session_state.last_result is None:
    st.warning("Please calculate and compare tax regimes in Step 3 before generating the JSON payload.")
else:
    regime_choice = st.radio(
        "Select regime for filing:",
        ["new", "old"],
        index=0 if st.session_state.last_result["recommended"] == "new" else 1,
        horizontal=True,
        format_func=lambda x: "New Tax Regime" if x == "new" else "Old Tax Regime",
    )

    pf = st.session_state.prefill_data

    default_dob = None
    if pf.get("dob"):
        try:
            default_dob = datetime.datetime.strptime(pf["dob"], "%Y-%m-%d").date()
        except ValueError:
            default_dob = None

    with st.expander("Personal & Verification Details (Auto-populated from Prefill JSON)", expanded=True):
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            first_name = st.text_input("First Name", value=pf.get("first_name", ""))
            surname = st.text_input("Surname / Last Name", value=pf.get("surname", ""))
            father_name = st.text_input("Father's Name", value=pf.get("father_name", ""))
            pan = st.text_input("PAN", max_chars=10, value=pf.get("pan", ""))
            aadhaar = st.text_input("Aadhaar Number (12 digits)", max_chars=12, value=pf.get("aadhaar", ""))
            dob = st.date_input(
                "Date of Birth",
                value=default_dob if default_dob else datetime.date(1990, 1, 1),
            )
        
        with p_col2:
            address_line = st.text_input("Flat / Residence No.", value=pf.get("address_line", ""))
            locality = st.text_input("Locality / Area", value=pf.get("locality", ""))
            city = st.text_input("City / District", value=pf.get("city", ""))
            state_code = st.text_input("State Code (e.g. 26)", value=str(pf.get("state_code", "26")))
            pincode = st.number_input("PIN Code", min_value=0, max_value=999999, value=int(pf.get("pincode", 144001)))
            mobile = st.number_input("Mobile Number", min_value=0, value=int(pf.get("mobile", 9999999999)))
            email = st.text_input("Email Address", value=pf.get("email", ""))

    if st.button("Build & Validate ITR-2 JSON", type="primary"):
        personal_info = {
            "first_name": first_name,
            "surname": surname,
            "father_name": father_name,
            "pan": pan,
            "aadhaar": aadhaar,
            "dob": str(dob),
            "address_line": address_line,
            "locality": locality,
            "city": city,
            "state_code": state_code,
            "pincode": pincode,
            "mobile": mobile,
            "email": email,
        }

        itr2_dict = build_itr2_json(
            personal_info=personal_info,
            form16=st.session_state.form16_data,
            tax_inputs=st.session_state.last_result["inputs"],
            tax_result=st.session_state.last_result["comparison"],
            cg_trades=st.session_state.cg_trades,
            filing_regime=regime_choice,
            bank_account={},
        )

        json_str = json.dumps(itr2_dict, indent=2)

        st.download_button(
            label="⬇️ Download Official ITR-2 JSON Draft",
            data=json_str,
            file_name=f"ITR2_AY2026-27_{pan.upper() if pan else 'DRAFT'}.json",
            mime="application/json",
        )
        st.success("ITR-2 JSON generated! You can download it above and upload it to the Income Tax portal.")
    
