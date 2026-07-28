import json

def parse_prefill_json(file_path: str) -> dict:
    """
    Parses an official ITD Prefill JSON file and extracts PersonalInfo
    and other available details for auto-population.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    itr2 = data.get("ITR", {}).get("ITR2", {})
    gen1 = itr2.get("PartA_GEN1", {})
    personal = gen1.get("PersonalInfo", {})
    address = personal.get("Address", {})
    name = personal.get("AssesseeName", {})

    return {
        "first_name": name.get("FirstName", ""),
        "surname": name.get("SurNameOrOrgName", ""),
        "pan": personal.get("PAN", ""),
        "aadhaar": personal.get("AadhaarCardNo", ""),
        "dob": personal.get("DOB", ""),
        "address_line": address.get("ResidenceNo", ""),
        "locality": address.get("LocalityOrArea", ""),
        "city": address.get("CityOrTownOrDistrict", ""),
        "state_code": address.get("StateCode", "26"),
        "pincode": address.get("PinCode", 0),
        "mobile": address.get("MobileNo", 0),
        "email": address.get("EmailAddress", ""),
    }
  
