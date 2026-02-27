"""HL7 v2.3, v2.5, and v2.8 segment/field definitions and data types."""

import copy

# ========== DATA TYPES ==========

DATA_TYPES = {
    "ST": {"name": "String Data", "primitive": True},
    "NM": {"name": "Numeric", "primitive": True},
    "ID": {"name": "Coded Value for HL7 Tables", "primitive": True},
    "IS": {"name": "Coded Value for User Tables", "primitive": True},
    "SI": {"name": "Sequence ID", "primitive": True},
    "TX": {"name": "Text Data", "primitive": True},
    "FT": {"name": "Formatted Text", "primitive": True},
    "DT": {"name": "Date", "primitive": True},
    "DTM": {"name": "Date/Time", "primitive": True},
    "TM": {"name": "Time", "primitive": True},
    "CQ": {"name": "Composite Quantity with Units", "components": [
        {"name": "Quantity", "dt": "NM"}, {"name": "Units", "dt": "CE"}]},
    "HD": {"name": "Hierarchic Designator", "components": [
        {"name": "Namespace ID", "dt": "IS"}, {"name": "Universal ID", "dt": "ST"},
        {"name": "Universal ID Type", "dt": "ID"}]},
    "EI": {"name": "Entity Identifier", "components": [
        {"name": "Entity Identifier", "dt": "ST"}, {"name": "Namespace ID", "dt": "IS"},
        {"name": "Universal ID", "dt": "ST"}, {"name": "Universal ID Type", "dt": "ID"}]},
    "CE": {"name": "Coded Element", "components": [
        {"name": "Identifier", "dt": "ST"}, {"name": "Text", "dt": "ST"},
        {"name": "Name of Coding System", "dt": "ID"}, {"name": "Alternate Identifier", "dt": "ST"},
        {"name": "Alternate Text", "dt": "ST"}, {"name": "Name of Alternate Coding System", "dt": "ID"}]},
    "CWE": {"name": "Coded with Exceptions", "components": [
        {"name": "Identifier", "dt": "ST"}, {"name": "Text", "dt": "ST"},
        {"name": "Name of Coding System", "dt": "ID"}, {"name": "Alternate Identifier", "dt": "ST"},
        {"name": "Alternate Text", "dt": "ST"}, {"name": "Name of Alternate Coding System", "dt": "ID"},
        {"name": "Coding System Version ID", "dt": "ST"}, {"name": "Alternate Coding System Version ID", "dt": "ST"},
        {"name": "Original Text", "dt": "ST"}]},
    "CNE": {"name": "Coded with No Exceptions", "components": [
        {"name": "Identifier", "dt": "ST"}, {"name": "Text", "dt": "ST"},
        {"name": "Name of Coding System", "dt": "ID"}, {"name": "Alternate Identifier", "dt": "ST"},
        {"name": "Alternate Text", "dt": "ST"}, {"name": "Name of Alternate Coding System", "dt": "ID"},
        {"name": "Coding System Version ID", "dt": "ST"}, {"name": "Alternate Coding System Version ID", "dt": "ST"},
        {"name": "Original Text", "dt": "ST"}]},
    "CX": {"name": "Extended Composite ID with Check Digit", "components": [
        {"name": "ID Number", "dt": "ST"}, {"name": "Check Digit", "dt": "ST"},
        {"name": "Check Digit Scheme", "dt": "ID"}, {"name": "Assigning Authority", "dt": "HD"},
        {"name": "Identifier Type Code", "dt": "ID"}, {"name": "Assigning Facility", "dt": "HD"},
        {"name": "Effective Date", "dt": "DT"}, {"name": "Expiration Date", "dt": "DT"},
        {"name": "Assigning Jurisdiction", "dt": "CWE"}, {"name": "Assigning Agency", "dt": "CWE"}]},
    "XPN": {"name": "Extended Person Name", "components": [
        {"name": "Family Name", "dt": "FN"}, {"name": "Given Name", "dt": "ST"},
        {"name": "Second Name", "dt": "ST"}, {"name": "Suffix", "dt": "ST"},
        {"name": "Prefix", "dt": "ST"}, {"name": "Degree", "dt": "IS"},
        {"name": "Name Type Code", "dt": "ID"}, {"name": "Name Representation Code", "dt": "ID"},
        {"name": "Name Context", "dt": "CE"}, {"name": "Name Validity Range", "dt": "DR"},
        {"name": "Name Assembly Order", "dt": "ID"}, {"name": "Effective Date", "dt": "TS"},
        {"name": "Expiration Date", "dt": "TS"}, {"name": "Professional Suffix", "dt": "ST"}]},
    "XCN": {"name": "Extended Composite ID and Name", "components": [
        {"name": "Person Identifier", "dt": "ST"}, {"name": "Family Name", "dt": "FN"},
        {"name": "Given Name", "dt": "ST"}, {"name": "Second Name", "dt": "ST"},
        {"name": "Suffix", "dt": "ST"}, {"name": "Prefix", "dt": "ST"},
        {"name": "Degree", "dt": "IS"}, {"name": "Source Table", "dt": "IS"},
        {"name": "Assigning Authority", "dt": "HD"}, {"name": "Name Type Code", "dt": "ID"},
        {"name": "Identifier Check Digit", "dt": "ST"}, {"name": "Check Digit Scheme", "dt": "ID"},
        {"name": "Identifier Type Code", "dt": "ID"}, {"name": "Assigning Facility", "dt": "HD"},
        {"name": "Name Representation Code", "dt": "ID"}, {"name": "Name Context", "dt": "CE"},
        {"name": "Name Validity Range", "dt": "DR"}, {"name": "Name Assembly Order", "dt": "ID"},
        {"name": "Effective Date", "dt": "TS"}, {"name": "Expiration Date", "dt": "TS"},
        {"name": "Professional Suffix", "dt": "ST"}, {"name": "Assigning Jurisdiction", "dt": "CWE"},
        {"name": "Assigning Agency", "dt": "CWE"}]},
    "XAD": {"name": "Extended Address", "components": [
        {"name": "Street Address", "dt": "SAD"}, {"name": "Other Designation", "dt": "ST"},
        {"name": "City", "dt": "ST"}, {"name": "State or Province", "dt": "ST"},
        {"name": "Zip or Postal Code", "dt": "ST"}, {"name": "Country", "dt": "ID"},
        {"name": "Address Type", "dt": "ID"}, {"name": "Other Geographic Designation", "dt": "ST"},
        {"name": "County/Parish Code", "dt": "IS"}, {"name": "Census Tract", "dt": "IS"},
        {"name": "Address Representation Code", "dt": "ID"}, {"name": "Address Validity Range", "dt": "DR"},
        {"name": "Effective Date", "dt": "TS"}, {"name": "Expiration Date", "dt": "TS"}]},
    "XTN": {"name": "Extended Telecommunication Number", "components": [
        {"name": "Telephone Number", "dt": "ST"}, {"name": "Telecommunication Use Code", "dt": "ID"},
        {"name": "Equipment Type", "dt": "ID"}, {"name": "Email Address", "dt": "ST"},
        {"name": "Country Code", "dt": "NM"}, {"name": "Area/City Code", "dt": "NM"},
        {"name": "Local Number", "dt": "NM"}, {"name": "Extension", "dt": "NM"},
        {"name": "Any Text", "dt": "ST"}, {"name": "Extension Prefix", "dt": "ST"},
        {"name": "Speed Dial Code", "dt": "ST"}, {"name": "Unformatted Number", "dt": "ST"}]},
    "PL": {"name": "Person Location", "components": [
        {"name": "Point of Care", "dt": "IS"}, {"name": "Room", "dt": "IS"},
        {"name": "Bed", "dt": "IS"}, {"name": "Facility", "dt": "HD"},
        {"name": "Location Status", "dt": "IS"}, {"name": "Person Location Type", "dt": "IS"},
        {"name": "Building", "dt": "IS"}, {"name": "Floor", "dt": "IS"},
        {"name": "Location Description", "dt": "ST"}, {"name": "Comprehensive Location ID", "dt": "EI"},
        {"name": "Assigning Authority for Location", "dt": "HD"}]},
    "MSG": {"name": "Message Type", "components": [
        {"name": "Message Code", "dt": "ID"}, {"name": "Trigger Event", "dt": "ID"},
        {"name": "Message Structure", "dt": "ID"}]},
    "PT": {"name": "Processing Type", "components": [
        {"name": "Processing ID", "dt": "ID"}, {"name": "Processing Mode", "dt": "ID"}]},
    "VID": {"name": "Version Identifier", "components": [
        {"name": "Version ID", "dt": "ID"}, {"name": "Internationalization Code", "dt": "CE"},
        {"name": "International Version ID", "dt": "CE"}]},
    "TS": {"name": "Time Stamp", "components": [
        {"name": "Time", "dt": "DTM"}, {"name": "Degree of Precision", "dt": "ID"}]},
    "FN": {"name": "Family Name", "components": [
        {"name": "Surname", "dt": "ST"}, {"name": "Own Surname Prefix", "dt": "ST"},
        {"name": "Own Surname", "dt": "ST"}, {"name": "Surname Prefix from Partner", "dt": "ST"},
        {"name": "Surname from Partner", "dt": "ST"}]},
    "SAD": {"name": "Street Address", "components": [
        {"name": "Street or Mailing Address", "dt": "ST"}, {"name": "Street Name", "dt": "ST"},
        {"name": "Dwelling Number", "dt": "ST"}]},
    "RP": {"name": "Reference Pointer", "components": [
        {"name": "Pointer", "dt": "ST"}, {"name": "Application ID", "dt": "HD"},
        {"name": "Type of Data", "dt": "ID"}, {"name": "Subtype", "dt": "ID"}]},
    "DR": {"name": "Date/Time Range", "components": [
        {"name": "Range Start Date/Time", "dt": "TS"}, {"name": "Range End Date/Time", "dt": "TS"}]},
    "DLN": {"name": "Driver's License Number", "components": [
        {"name": "License Number", "dt": "ST"}, {"name": "Issuing State", "dt": "IS"},
        {"name": "Expiration Date", "dt": "DT"}]},
    "FC": {"name": "Financial Class", "components": [
        {"name": "Financial Class Code", "dt": "IS"}, {"name": "Effective Date", "dt": "TS"}]},
    "DLD": {"name": "Discharge to Location", "components": [
        {"name": "Discharge Location", "dt": "IS"}, {"name": "Effective Date", "dt": "TS"}]},
    "CP": {"name": "Composite Price", "components": [
        {"name": "Price", "dt": "MO"}, {"name": "Price Type", "dt": "ID"},
        {"name": "From Value", "dt": "NM"}, {"name": "To Value", "dt": "NM"},
        {"name": "Range Units", "dt": "CE"}, {"name": "Range Type", "dt": "ID"}]},
    "MO": {"name": "Money", "components": [
        {"name": "Quantity", "dt": "NM"}, {"name": "Denomination", "dt": "ID"}]},
    "SN": {"name": "Structured Numeric", "components": [
        {"name": "Comparator", "dt": "ST"}, {"name": "Num1", "dt": "NM"},
        {"name": "Separator/Suffix", "dt": "ST"}, {"name": "Num2", "dt": "NM"}]},
    "ED": {"name": "Encapsulated Data", "components": [
        {"name": "Source Application", "dt": "HD"}, {"name": "Type of Data", "dt": "ID"},
        {"name": "Data Subtype", "dt": "ID"}, {"name": "Encoding", "dt": "ID"},
        {"name": "Data", "dt": "TX"}]},
    "CF": {"name": "Coded Element with Formatted Values", "components": [
        {"name": "Identifier", "dt": "ST"}, {"name": "Formatted Text", "dt": "FT"},
        {"name": "Name of Coding System", "dt": "ID"}, {"name": "Alternate Identifier", "dt": "ST"},
        {"name": "Alternate Formatted Text", "dt": "FT"}, {"name": "Name of Alternate Coding System", "dt": "ID"}]},
    "TQ": {"name": "Timing/Quantity", "components": [
        {"name": "Quantity", "dt": "CQ"}, {"name": "Interval", "dt": "RI"},
        {"name": "Duration", "dt": "ST"}, {"name": "Start Date/Time", "dt": "TS"},
        {"name": "End Date/Time", "dt": "TS"}, {"name": "Priority", "dt": "ST"},
        {"name": "Condition", "dt": "ST"}, {"name": "Text", "dt": "TX"},
        {"name": "Conjunction", "dt": "ID"}, {"name": "Order Sequencing", "dt": "OSD"},
        {"name": "Occurrence Duration", "dt": "CE"}, {"name": "Total Occurrences", "dt": "NM"}]},
    "RI": {"name": "Repeat Interval", "components": [
        {"name": "Repeat Pattern", "dt": "IS"}, {"name": "Explicit Time Interval", "dt": "ST"}]},
    "XON": {"name": "Extended Composite Name for Organizations", "components": [
        {"name": "Organization Name", "dt": "ST"}, {"name": "Organization Name Type Code", "dt": "IS"},
        {"name": "ID Number", "dt": "NM"}, {"name": "Check Digit", "dt": "NM"},
        {"name": "Check Digit Scheme", "dt": "ID"}, {"name": "Assigning Authority", "dt": "HD"},
        {"name": "Identifier Type Code", "dt": "ID"}, {"name": "Assigning Facility", "dt": "HD"},
        {"name": "Name Representation Code", "dt": "ID"}, {"name": "Organization Identifier", "dt": "ST"}]},
    "GTS": {"name": "General Timing Specification", "primitive": True},
    "RPT": {"name": "Repeat Pattern", "components": [
        {"name": "Repeat Pattern Code", "dt": "CWE"}, {"name": "Calendar Alignment", "dt": "ID"},
        {"name": "Phase Range Begin Value", "dt": "NM"}, {"name": "Phase Range End Value", "dt": "NM"},
        {"name": "Period Quantity", "dt": "NM"}, {"name": "Period Units", "dt": "IS"},
        {"name": "Institution Specified Time", "dt": "ID"}, {"name": "Event", "dt": "ID"},
        {"name": "Event Offset Quantity", "dt": "NM"}, {"name": "Event Offset Units", "dt": "IS"},
        {"name": "General Timing Specification", "dt": "GTS"}]},
}


# ========== HL7 v2.3 SEGMENT DEFINITIONS ==========

def _f(name, dt, opt="O", rep=False, length=0):
    """Shorthand for field definition."""
    return {"name": name, "dt": dt, "opt": opt, "rep": rep, "len": length}


HL7_V23 = {
    "MSH": {"name": "Message Header", "fields": {
        1: _f("Field Separator", "ST", "R", False, 1),
        2: _f("Encoding Characters", "ST", "R", False, 4),
        3: _f("Sending Application", "HD", "O", False, 180),
        4: _f("Sending Facility", "HD", "O", False, 180),
        5: _f("Receiving Application", "HD", "O", False, 180),
        6: _f("Receiving Facility", "HD", "O", False, 180),
        7: _f("Date/Time of Message", "TS", "O", False, 26),
        8: _f("Security", "ST", "O", False, 40),
        9: _f("Message Type", "MSG", "R", False, 15),
        10: _f("Message Control ID", "ST", "R", False, 20),
        11: _f("Processing ID", "PT", "R", False, 3),
        12: _f("Version ID", "VID", "R", False, 60),
        13: _f("Sequence Number", "NM", "O", False, 15),
        14: _f("Continuation Pointer", "ST", "O", False, 180),
        15: _f("Accept Acknowledgment Type", "ID", "O", False, 2),
        16: _f("Application Acknowledgment Type", "ID", "O", False, 2),
        17: _f("Country Code", "ID", "O", False, 3),
        18: _f("Character Set", "ID", "O", True, 16),
        19: _f("Principal Language of Message", "CE", "O", False, 250),
    }},
    "EVN": {"name": "Event Type", "fields": {
        1: _f("Event Type Code", "ID", "B", False, 3),
        2: _f("Recorded Date/Time", "TS", "R", False, 26),
        3: _f("Date/Time Planned Event", "TS", "O", False, 26),
        4: _f("Event Reason Code", "IS", "O", False, 3),
        5: _f("Operator ID", "XCN", "O", True, 250),
        6: _f("Event Occurred", "TS", "O", False, 26),
    }},
    "PID": {"name": "Patient Identification", "fields": {
        1: _f("Set ID", "SI", "O", False, 4),
        2: _f("Patient ID", "CX", "B", False, 20),
        3: _f("Patient Identifier List", "CX", "R", True, 250),
        4: _f("Alternate Patient ID", "CX", "B", True, 20),
        5: _f("Patient Name", "XPN", "R", True, 250),
        6: _f("Mother's Maiden Name", "XPN", "O", True, 250),
        7: _f("Date/Time of Birth", "TS", "O", False, 26),
        8: _f("Administrative Sex", "IS", "O", False, 1),
        9: _f("Patient Alias", "XPN", "B", True, 250),
        10: _f("Race", "CE", "O", True, 250),
        11: _f("Patient Address", "XAD", "O", True, 250),
        12: _f("County Code", "IS", "B", False, 4),
        13: _f("Phone Number - Home", "XTN", "O", True, 250),
        14: _f("Phone Number - Business", "XTN", "O", True, 250),
        15: _f("Primary Language", "CE", "O", False, 250),
        16: _f("Marital Status", "CE", "O", False, 250),
        17: _f("Religion", "CE", "O", False, 250),
        18: _f("Patient Account Number", "CX", "O", False, 250),
        19: _f("SSN Number", "ST", "B", False, 16),
        20: _f("Driver's License Number", "DLN", "B", False, 25),
        21: _f("Mother's Identifier", "CX", "O", True, 250),
        22: _f("Ethnic Group", "CE", "O", True, 250),
        23: _f("Birth Place", "ST", "O", False, 250),
        24: _f("Multiple Birth Indicator", "ID", "O", False, 1),
        25: _f("Birth Order", "NM", "O", False, 2),
        26: _f("Citizenship", "CE", "O", True, 250),
        27: _f("Veterans Military Status", "CE", "O", False, 250),
        28: _f("Nationality", "CE", "B", False, 250),
        29: _f("Patient Death Date/Time", "TS", "O", False, 26),
        30: _f("Patient Death Indicator", "ID", "O", False, 1),
    }},
    "PV1": {"name": "Patient Visit", "fields": {
        1: _f("Set ID", "SI", "O", False, 4),
        2: _f("Patient Class", "IS", "R", False, 1),
        3: _f("Assigned Patient Location", "PL", "O", False, 80),
        4: _f("Admission Type", "IS", "O", False, 2),
        5: _f("Preadmit Number", "CX", "O", False, 250),
        6: _f("Prior Patient Location", "PL", "O", False, 80),
        7: _f("Attending Doctor", "XCN", "O", True, 250),
        8: _f("Referring Doctor", "XCN", "O", True, 250),
        9: _f("Consulting Doctor", "XCN", "O", True, 250),
        10: _f("Hospital Service", "IS", "O", False, 3),
        11: _f("Temporary Location", "PL", "O", False, 80),
        12: _f("Preadmit Test Indicator", "IS", "O", False, 2),
        13: _f("Re-admission Indicator", "IS", "O", False, 2),
        14: _f("Admit Source", "IS", "O", False, 6),
        15: _f("Ambulatory Status", "IS", "O", True, 2),
        16: _f("VIP Indicator", "IS", "O", False, 2),
        17: _f("Admitting Doctor", "XCN", "O", True, 250),
        18: _f("Patient Type", "IS", "O", False, 2),
        19: _f("Visit Number", "CX", "O", False, 250),
        20: _f("Financial Class", "FC", "O", True, 50),
        21: _f("Charge Price Indicator", "IS", "O", False, 2),
        22: _f("Courtesy Code", "IS", "O", False, 2),
        23: _f("Credit Rating", "IS", "O", False, 2),
        24: _f("Contract Code", "IS", "O", True, 2),
        25: _f("Contract Effective Date", "DT", "O", True, 8),
        26: _f("Contract Amount", "NM", "O", True, 12),
        27: _f("Contract Period", "NM", "O", True, 3),
        28: _f("Interest Code", "IS", "O", False, 2),
        29: _f("Transfer to Bad Debt Code", "IS", "O", False, 1),
        30: _f("Transfer to Bad Debt Date", "DT", "O", False, 8),
        31: _f("Bad Debt Agency Code", "IS", "O", False, 10),
        32: _f("Bad Debt Transfer Amount", "NM", "O", False, 12),
        33: _f("Bad Debt Recovery Amount", "NM", "O", False, 12),
        34: _f("Delete Account Indicator", "IS", "O", False, 1),
        35: _f("Delete Account Date", "DT", "O", False, 8),
        36: _f("Discharge Disposition", "IS", "O", False, 3),
        37: _f("Discharged to Location", "DLD", "O", False, 25),
        38: _f("Diet Type", "CE", "O", False, 250),
        39: _f("Servicing Facility", "IS", "O", False, 2),
        40: _f("Bed Status", "IS", "B", False, 1),
        41: _f("Account Status", "IS", "O", False, 2),
        42: _f("Pending Location", "PL", "O", False, 80),
        43: _f("Prior Temporary Location", "PL", "O", False, 80),
        44: _f("Admit Date/Time", "TS", "O", False, 26),
        45: _f("Discharge Date/Time", "TS", "O", True, 26),
        46: _f("Current Patient Balance", "NM", "O", False, 12),
        47: _f("Total Charges", "NM", "O", False, 12),
        48: _f("Total Adjustments", "NM", "O", False, 12),
        49: _f("Total Payments", "NM", "O", False, 12),
        50: _f("Alternate Visit ID", "CX", "O", False, 250),
        51: _f("Visit Indicator", "IS", "O", False, 1),
        52: _f("Other Healthcare Provider", "XCN", "B", True, 250),
    }},
    "PV2": {"name": "Patient Visit - Additional", "fields": {
        1: _f("Prior Pending Location", "PL", "C", False, 80),
        2: _f("Accommodation Code", "CE", "O", False, 250),
        3: _f("Admit Reason", "CE", "O", False, 250),
        4: _f("Transfer Reason", "CE", "O", False, 250),
        5: _f("Patient Valuables", "ST", "O", True, 25),
        6: _f("Patient Valuables Location", "ST", "O", False, 25),
        7: _f("Visit User Code", "IS", "O", True, 2),
        8: _f("Expected Admit Date/Time", "TS", "O", False, 26),
        9: _f("Expected Discharge Date/Time", "TS", "O", False, 26),
        10: _f("Estimated Length of Inpatient Stay", "NM", "O", False, 3),
        11: _f("Actual Length of Inpatient Stay", "NM", "O", False, 3),
        12: _f("Visit Description", "ST", "O", False, 50),
        13: _f("Referral Source Code", "XCN", "O", True, 250),
        14: _f("Previous Service Date", "DT", "O", False, 8),
        15: _f("Employment Illness Related Indicator", "ID", "O", False, 1),
        16: _f("Purge Status Code", "IS", "O", False, 1),
        17: _f("Purge Status Date", "DT", "O", False, 8),
        18: _f("Special Program Code", "IS", "O", False, 2),
        19: _f("Retention Indicator", "ID", "O", False, 1),
        20: _f("Expected Number of Insurance Plans", "NM", "O", False, 1),
        21: _f("Visit Publicity Code", "IS", "O", False, 1),
        22: _f("Visit Protection Indicator", "ID", "O", False, 1),
        23: _f("Clinic Organization Name", "XON", "O", True, 250),
        24: _f("Patient Status Code", "IS", "O", False, 2),
        25: _f("Visit Priority Code", "IS", "O", False, 1),
        26: _f("Previous Treatment Date", "DT", "O", False, 8),
        27: _f("Expected Discharge Disposition", "IS", "O", False, 2),
        28: _f("Signature on File Date", "DT", "O", False, 8),
        29: _f("First Similar Illness Date", "DT", "O", False, 8),
        30: _f("Patient Charge Adjustment Code", "CE", "O", False, 250),
    }},
    "NK1": {"name": "Next of Kin", "fields": {
        1: _f("Set ID", "SI", "R", False, 4),
        2: _f("Name", "XPN", "O", True, 250),
        3: _f("Relationship", "CE", "O", False, 250),
        4: _f("Address", "XAD", "O", True, 250),
        5: _f("Phone Number", "XTN", "O", True, 250),
        6: _f("Business Phone Number", "XTN", "O", True, 250),
        7: _f("Contact Role", "CE", "O", False, 250),
        8: _f("Start Date", "DT", "O", False, 8),
        9: _f("End Date", "DT", "O", False, 8),
        10: _f("Next of Kin Job Title", "ST", "O", False, 60),
        11: _f("Next of Kin Job Code/Class", "JCC", "O", False, 20),
        12: _f("Next of Kin Employee Number", "CX", "O", False, 250),
        13: _f("Organization Name", "XON", "O", True, 250),
    }},
    "ORC": {"name": "Common Order", "fields": {
        1: _f("Order Control", "ID", "R", False, 2),
        2: _f("Placer Order Number", "EI", "C", False, 22),
        3: _f("Filler Order Number", "EI", "C", False, 22),
        4: _f("Placer Group Number", "EI", "O", False, 22),
        5: _f("Order Status", "ID", "O", False, 2),
        6: _f("Response Flag", "ID", "O", False, 1),
        7: _f("Quantity/Timing", "TQ", "O", True, 200),
        8: _f("Parent", "EI", "O", False, 200),
        9: _f("Date/Time of Transaction", "TS", "O", False, 26),
        10: _f("Entered By", "XCN", "O", True, 250),
        11: _f("Verified By", "XCN", "O", True, 250),
        12: _f("Ordering Provider", "XCN", "O", True, 250),
        13: _f("Enterer's Location", "PL", "O", False, 80),
        14: _f("Call Back Phone Number", "XTN", "O", True, 250),
        15: _f("Order Effective Date/Time", "TS", "O", False, 26),
        16: _f("Order Control Code Reason", "CE", "O", False, 250),
        17: _f("Entering Organization", "CE", "O", False, 250),
        18: _f("Entering Device", "CE", "O", False, 250),
        19: _f("Action By", "XCN", "O", True, 250),
    }},
    "OBR": {"name": "Observation Request", "fields": {
        1: _f("Set ID", "SI", "O", False, 4),
        2: _f("Placer Order Number", "EI", "C", False, 22),
        3: _f("Filler Order Number", "EI", "C", False, 22),
        4: _f("Universal Service Identifier", "CE", "R", False, 250),
        5: _f("Priority", "ID", "B", False, 2),
        6: _f("Requested Date/Time", "TS", "B", False, 26),
        7: _f("Observation Date/Time", "TS", "C", False, 26),
        8: _f("Observation End Date/Time", "TS", "O", False, 26),
        9: _f("Collection Volume", "CQ", "O", False, 20),
        10: _f("Collector Identifier", "XCN", "O", True, 250),
        11: _f("Specimen Action Code", "ID", "O", False, 1),
        12: _f("Danger Code", "CE", "O", False, 250),
        13: _f("Relevant Clinical Information", "ST", "O", False, 300),
        14: _f("Specimen Received Date/Time", "TS", "O", False, 26),
        15: _f("Specimen Source", "SPS", "O", False, 300),
        16: _f("Ordering Provider", "XCN", "O", True, 250),
        17: _f("Order Callback Phone Number", "XTN", "O", True, 250),
        18: _f("Placer Field 1", "ST", "O", False, 60),
        19: _f("Placer Field 2", "ST", "O", False, 60),
        20: _f("Filler Field 1", "ST", "O", False, 60),
        21: _f("Filler Field 2", "ST", "O", False, 60),
        22: _f("Results Rpt/Status Chng Date/Time", "TS", "C", False, 26),
        23: _f("Charge to Practice", "MOC", "O", False, 40),
        24: _f("Diagnostic Service Section ID", "ID", "O", False, 10),
        25: _f("Result Status", "ID", "C", False, 1),
        26: _f("Parent Result", "PRL", "O", False, 400),
        27: _f("Quantity/Timing", "TQ", "O", True, 200),
        28: _f("Result Copies To", "XCN", "O", True, 250),
        29: _f("Parent Number", "EI", "O", False, 200),
        30: _f("Transportation Mode", "ID", "O", False, 20),
        31: _f("Reason for Study", "CE", "O", True, 250),
        32: _f("Principal Result Interpreter", "NDL", "O", False, 200),
        33: _f("Assistant Result Interpreter", "NDL", "O", True, 200),
        34: _f("Technician", "NDL", "O", True, 200),
        35: _f("Transcriptionist", "NDL", "O", True, 200),
        36: _f("Scheduled Date/Time", "TS", "O", False, 26),
        37: _f("Number of Sample Containers", "NM", "O", False, 4),
        38: _f("Transport Logistics of Collected Sample", "CE", "O", True, 250),
        39: _f("Collector's Comment", "CE", "O", True, 250),
        40: _f("Transport Arrangement Responsibility", "CE", "O", False, 250),
        41: _f("Transport Arranged", "ID", "O", False, 30),
        42: _f("Escort Required", "ID", "O", False, 1),
        43: _f("Planned Patient Transport Comment", "CE", "O", True, 250),
    }},
    "OBX": {"name": "Observation/Result", "fields": {
        1: _f("Set ID", "SI", "O", False, 4),
        2: _f("Value Type", "ID", "C", False, 3),
        3: _f("Observation Identifier", "CE", "R", False, 250),
        4: _f("Observation Sub-ID", "ST", "C", False, 20),
        5: _f("Observation Value", "*", "C", True, 65536),
        6: _f("Units", "CE", "O", False, 250),
        7: _f("References Range", "ST", "O", False, 60),
        8: _f("Abnormal Flags", "IS", "O", True, 5),
        9: _f("Probability", "NM", "O", False, 5),
        10: _f("Nature of Abnormal Test", "ID", "O", False, 2),
        11: _f("Observation Result Status", "ID", "R", False, 1),
        12: _f("Effective Date of Reference Range", "TS", "O", False, 26),
        13: _f("User Defined Access Checks", "ST", "O", False, 20),
        14: _f("Date/Time of Observation", "TS", "O", False, 26),
        15: _f("Producer's ID", "CE", "O", False, 250),
        16: _f("Responsible Observer", "XCN", "O", True, 250),
        17: _f("Observation Method", "CE", "O", True, 250),
    }},
    "DG1": {"name": "Diagnosis", "fields": {
        1: _f("Set ID", "SI", "R", False, 4),
        2: _f("Diagnosis Coding Method", "ID", "B", False, 2),
        3: _f("Diagnosis Code", "CE", "O", False, 250),
        4: _f("Diagnosis Description", "ST", "B", False, 40),
        5: _f("Diagnosis Date/Time", "TS", "O", False, 26),
        6: _f("Diagnosis Type", "IS", "R", False, 2),
        7: _f("Major Diagnostic Category", "CE", "B", False, 250),
        8: _f("Diagnostic Related Group", "CE", "B", False, 250),
        9: _f("DRG Approval Indicator", "ID", "B", False, 1),
        10: _f("DRG Grouper Review Code", "IS", "B", False, 2),
        11: _f("Outlier Type", "CE", "B", False, 250),
        12: _f("Outlier Days", "NM", "B", False, 3),
        13: _f("Outlier Cost", "CP", "B", False, 12),
        14: _f("Grouper Version and Type", "ST", "B", False, 4),
        15: _f("Diagnosis Priority", "ID", "O", False, 2),
        16: _f("Diagnosing Clinician", "XCN", "O", True, 250),
    }},
    "IN1": {"name": "Insurance", "fields": {
        1: _f("Set ID", "SI", "R", False, 4),
        2: _f("Insurance Plan ID", "CE", "R", False, 250),
        3: _f("Insurance Company ID", "CX", "R", True, 250),
        4: _f("Insurance Company Name", "XON", "O", True, 250),
        5: _f("Insurance Company Address", "XAD", "O", True, 250),
        6: _f("Insurance Co Contact Person", "XPN", "O", True, 250),
        7: _f("Insurance Co Phone Number", "XTN", "O", True, 250),
        8: _f("Group Number", "ST", "O", False, 12),
        9: _f("Group Name", "XON", "O", True, 250),
        10: _f("Insured's Group Emp ID", "CX", "O", True, 250),
        11: _f("Insured's Group Emp Name", "XON", "O", True, 250),
        12: _f("Plan Effective Date", "DT", "O", False, 8),
        13: _f("Plan Expiration Date", "DT", "O", False, 8),
        14: _f("Authorization Information", "AUI", "O", False, 239),
        15: _f("Plan Type", "IS", "O", False, 3),
        16: _f("Name of Insured", "XPN", "O", True, 250),
        17: _f("Insured's Relationship to Patient", "CE", "O", False, 250),
        18: _f("Insured's Date of Birth", "TS", "O", False, 26),
        19: _f("Insured's Address", "XAD", "O", True, 250),
        20: _f("Assignment of Benefits", "IS", "O", False, 2),
        21: _f("Coordination of Benefits", "IS", "O", False, 2),
        22: _f("Coord of Ben. Priority", "ST", "O", False, 2),
    }},
    "AL1": {"name": "Patient Allergy", "fields": {
        1: _f("Set ID", "SI", "R", False, 4),
        2: _f("Allergen Type Code", "CE", "O", False, 250),
        3: _f("Allergen Code/Description", "CE", "R", False, 250),
        4: _f("Allergy Severity Code", "CE", "O", False, 250),
        5: _f("Allergy Reaction Code", "ST", "O", True, 15),
        6: _f("Identification Date", "DT", "B", False, 8),
    }},
    "GT1": {"name": "Guarantor", "fields": {
        1: _f("Set ID", "SI", "R", False, 4),
        2: _f("Guarantor Number", "CX", "O", True, 250),
        3: _f("Guarantor Name", "XPN", "R", True, 250),
        4: _f("Guarantor Spouse Name", "XPN", "O", True, 250),
        5: _f("Guarantor Address", "XAD", "O", True, 250),
        6: _f("Guarantor Ph Num - Home", "XTN", "O", True, 250),
        7: _f("Guarantor Ph Num - Business", "XTN", "O", True, 250),
        8: _f("Guarantor Date/Time of Birth", "TS", "O", False, 26),
        9: _f("Guarantor Administrative Sex", "IS", "O", False, 1),
        10: _f("Guarantor Type", "IS", "O", False, 2),
        11: _f("Guarantor Relationship", "CE", "O", False, 250),
        12: _f("Guarantor SSN", "ST", "O", False, 11),
    }},
    "NTE": {"name": "Notes and Comments", "fields": {
        1: _f("Set ID", "SI", "O", False, 4),
        2: _f("Source of Comment", "ID", "O", False, 8),
        3: _f("Comment", "FT", "O", True, 65536),
        4: _f("Comment Type", "CE", "O", False, 250),
    }},
    "MSA": {"name": "Message Acknowledgment", "fields": {
        1: _f("Acknowledgment Code", "ID", "R", False, 2),
        2: _f("Message Control ID", "ST", "R", False, 20),
        3: _f("Text Message", "ST", "O", False, 80),
        4: _f("Expected Sequence Number", "NM", "O", False, 15),
        5: _f("Delayed Acknowledgment Type", "ID", "B", False, 1),
        6: _f("Error Condition", "CE", "O", False, 250),
    }},
    "ERR": {"name": "Error", "fields": {
        1: _f("Error Code and Location", "CM", "R", True, 80),
    }},
    "QRD": {"name": "Original-Style Query Definition", "fields": {
        1: _f("Query Date/Time", "TS", "R", False, 26),
        2: _f("Query Format Code", "ID", "R", False, 1),
        3: _f("Query Priority", "ID", "R", False, 1),
        4: _f("Query ID", "ST", "R", False, 10),
        5: _f("Deferred Response Type", "ID", "O", False, 1),
        6: _f("Deferred Response Date/Time", "TS", "O", False, 26),
        7: _f("Quantity Limited Request", "CQ", "R", False, 10),
        8: _f("Who Subject Filter", "XCN", "R", True, 250),
        9: _f("What Subject Filter", "CE", "R", True, 250),
        10: _f("What Department Data Code", "CE", "R", True, 250),
        11: _f("What Data Code Value Qual", "CM", "O", True, 20),
        12: _f("Query Results Level", "ID", "O", False, 1),
    }},
    "QRF": {"name": "Original-Style Query Filter", "fields": {
        1: _f("Where Subject Filter", "ST", "R", True, 20),
        2: _f("When Data Start Date/Time", "TS", "O", False, 26),
        3: _f("When Data End Date/Time", "TS", "O", False, 26),
        4: _f("What User Qualifier", "ST", "O", True, 60),
        5: _f("Other QRY Subject Filter", "ST", "O", True, 60),
    }},
    "MRG": {"name": "Merge Patient Information", "fields": {
        1: _f("Prior Patient Identifier List", "CX", "R", True, 250),
        2: _f("Prior Alternate Patient ID", "CX", "B", True, 250),
        3: _f("Prior Patient Account Number", "CX", "O", False, 250),
        4: _f("Prior Patient ID", "CX", "B", False, 250),
        5: _f("Prior Visit Number", "CX", "O", False, 250),
        6: _f("Prior Alternate Visit ID", "CX", "O", False, 250),
        7: _f("Prior Patient Name", "XPN", "O", True, 250),
    }},
    "SCH": {"name": "Scheduling Activity", "fields": {
        1: _f("Placer Appointment ID", "EI", "C", False, 75),
        2: _f("Filler Appointment ID", "EI", "C", False, 75),
        3: _f("Occurrence Number", "NM", "C", False, 5),
        4: _f("Placer Group Number", "EI", "O", False, 22),
        5: _f("Schedule ID", "CE", "O", False, 250),
        6: _f("Event Reason", "CE", "R", False, 250),
        7: _f("Appointment Reason", "CE", "O", False, 250),
        8: _f("Appointment Type", "CE", "O", False, 250),
        9: _f("Appointment Duration", "NM", "O", False, 20),
        10: _f("Appointment Duration Units", "CE", "O", False, 250),
        11: _f("Appointment Timing Quantity", "TQ", "O", True, 200),
        12: _f("Placer Contact Person", "XCN", "O", True, 250),
        13: _f("Placer Contact Phone Number", "XTN", "O", False, 250),
        14: _f("Placer Contact Address", "XAD", "O", True, 250),
        15: _f("Placer Contact Location", "PL", "O", False, 80),
        16: _f("Filler Contact Person", "XCN", "R", True, 250),
        17: _f("Filler Contact Phone Number", "XTN", "O", False, 250),
        18: _f("Filler Contact Address", "XAD", "O", True, 250),
        19: _f("Filler Contact Location", "PL", "O", False, 80),
        20: _f("Entered By Person", "XCN", "R", True, 250),
        21: _f("Entered By Phone Number", "XTN", "O", True, 250),
        22: _f("Entered By Location", "PL", "O", False, 80),
        23: _f("Parent Placer Appointment ID", "EI", "O", False, 75),
        24: _f("Parent Filler Appointment ID", "EI", "O", False, 75),
        25: _f("Filler Status Code", "CE", "O", False, 250),
    }},
    "TXA": {"name": "Transcription Document Header", "fields": {
        1: _f("Set ID", "SI", "R", False, 4),
        2: _f("Document Type", "IS", "R", False, 30),
        3: _f("Document Content Presentation", "ID", "C", False, 2),
        4: _f("Activity Date/Time", "TS", "O", False, 26),
        5: _f("Primary Activity Provider Code/Name", "XCN", "C", True, 250),
        6: _f("Origination Date/Time", "TS", "O", False, 26),
        7: _f("Transcription Date/Time", "TS", "O", False, 26),
        8: _f("Edit Date/Time", "TS", "O", True, 26),
        9: _f("Originator Code/Name", "XCN", "O", True, 250),
        10: _f("Assigned Document Authenticator", "XCN", "O", True, 250),
        11: _f("Transcriptionist Code/Name", "XCN", "O", True, 250),
        12: _f("Unique Document Number", "EI", "R", False, 30),
        13: _f("Parent Document Number", "EI", "O", False, 30),
        14: _f("Placer Order Number", "EI", "O", True, 22),
        15: _f("Filler Order Number", "EI", "O", False, 22),
        16: _f("Unique Document File Name", "ST", "O", False, 30),
        17: _f("Document Completion Status", "ID", "R", False, 2),
        18: _f("Document Confidentiality Status", "ID", "O", False, 2),
        19: _f("Document Availability Status", "ID", "O", False, 2),
        20: _f("Document Storage Status", "ID", "O", False, 2),
        21: _f("Document Change Reason", "ST", "C", False, 30),
        22: _f("Authentication Person Time Stamp", "PPN", "C", True, 250),
        23: _f("Distributed Copies", "XCN", "O", True, 250),
    }},
    "DSP": {"name": "Display Data", "fields": {
        1: _f("Set ID", "SI", "O", False, 4),
        2: _f("Display Level", "SI", "O", False, 4),
        3: _f("Data Line", "TX", "R", False, 300),
        4: _f("Logical Break Point", "ST", "O", False, 2),
        5: _f("Result ID", "TX", "O", False, 20),
    }},
}


# ========== HL7 v2.5 SEGMENT DEFINITIONS ==========
# Start with v2.3 as base, then override/extend

HL7_V25 = copy.deepcopy(HL7_V23)

# MSH v2.5 extensions
HL7_V25["MSH"]["fields"][20] = _f("Alternate Character Set Handling", "ID", "O", False, 20)
HL7_V25["MSH"]["fields"][21] = _f("Message Profile Identifier", "EI", "O", True, 427)

# PID v2.5 extensions
HL7_V25["PID"]["fields"][31] = _f("Identity Unknown Indicator", "ID", "O", False, 1)
HL7_V25["PID"]["fields"][32] = _f("Identity Reliability Code", "IS", "O", True, 20)
HL7_V25["PID"]["fields"][33] = _f("Last Update Date/Time", "TS", "O", False, 26)
HL7_V25["PID"]["fields"][34] = _f("Last Update Facility", "HD", "O", False, 241)
HL7_V25["PID"]["fields"][35] = _f("Species Code", "CE", "C", False, 250)
HL7_V25["PID"]["fields"][36] = _f("Breed Code", "CE", "C", False, 250)
HL7_V25["PID"]["fields"][37] = _f("Strain", "ST", "O", False, 80)
HL7_V25["PID"]["fields"][38] = _f("Production Class Code", "CE", "O", False, 250)
HL7_V25["PID"]["fields"][39] = _f("Tribal Citizenship", "CWE", "O", True, 250)

# ERR v2.5 expanded (full redefinition)
HL7_V25["ERR"] = {"name": "Error", "fields": {
    1: _f("Error Code and Location", "ELD", "B", True, 493),
    2: _f("Error Location", "ERL", "O", True, 18),
    3: _f("HL7 Error Code", "CWE", "R", False, 705),
    4: _f("Severity", "ID", "R", False, 2),
    5: _f("Application Error Code", "CWE", "O", False, 705),
    6: _f("Application Error Parameter", "ST", "O", True, 80),
    7: _f("Diagnostic Information", "TX", "O", False, 2048),
    8: _f("User Message", "TX", "O", False, 250),
    9: _f("Inform Person Indicator", "IS", "O", True, 20),
    10: _f("Override Type", "CWE", "O", False, 705),
    11: _f("Override Reason Code", "CWE", "O", True, 705),
    12: _f("Help Desk Contact Point", "XTN", "O", True, 652),
}}

# ORC v2.5 extensions
HL7_V25["ORC"]["fields"][20] = _f("Advanced Beneficiary Notice Code", "CE", "O", False, 250)
HL7_V25["ORC"]["fields"][21] = _f("Ordering Facility Name", "XON", "O", True, 250)
HL7_V25["ORC"]["fields"][22] = _f("Ordering Facility Address", "XAD", "O", True, 250)
HL7_V25["ORC"]["fields"][23] = _f("Ordering Facility Phone Number", "XTN", "O", True, 250)
HL7_V25["ORC"]["fields"][24] = _f("Ordering Provider Address", "XAD", "O", True, 250)
HL7_V25["ORC"]["fields"][25] = _f("Order Status Modifier", "CWE", "O", False, 250)

# OBR v2.5 extensions
HL7_V25["OBR"]["fields"][44] = _f("Procedure Code", "CE", "O", False, 250)
HL7_V25["OBR"]["fields"][45] = _f("Procedure Code Modifier", "CE", "O", True, 250)
HL7_V25["OBR"]["fields"][46] = _f("Placer Supplemental Service Info", "CE", "O", True, 250)
HL7_V25["OBR"]["fields"][47] = _f("Filler Supplemental Service Info", "CE", "O", True, 250)
HL7_V25["OBR"]["fields"][48] = _f("Medically Necessary Duplicate Procedure Reason", "CWE", "C", False, 250)
HL7_V25["OBR"]["fields"][49] = _f("Result Handling", "IS", "O", False, 2)
HL7_V25["OBR"]["fields"][50] = _f("Parent Universal Service Identifier", "CWE", "O", False, 250)

# OBX v2.5 extensions
HL7_V25["OBX"]["fields"][18] = _f("Equipment Instance Identifier", "EI", "O", True, 22)
HL7_V25["OBX"]["fields"][19] = _f("Date/Time of the Analysis", "TS", "O", False, 26)

# New segments added in v2.5 (also inherited by v2.8)
HL7_V25["SFT"] = {"name": "Software Segment", "fields": {
    1: _f("Software Vendor Organization", "XON", "R", False, 567),
    2: _f("Software Certified Version or Release Number", "ST", "R", False, 15),
    3: _f("Software Product Name", "ST", "R", False, 20),
    4: _f("Software Binary ID", "ST", "R", False, 20),
    5: _f("Software Product Information", "TX", "O", False, 1024),
    6: _f("Software Install Date", "TS", "O", False, 26),
}}

HL7_V25["SPM"] = {"name": "Specimen", "fields": {
    1: _f("Set ID", "SI", "O", False, 4),
    2: _f("Specimen ID", "EIP", "O", False, 80),
    3: _f("Specimen Parent IDs", "EIP", "O", True, 80),
    4: _f("Specimen Type", "CWE", "R", False, 250),
    5: _f("Specimen Type Modifier", "CWE", "O", True, 250),
    6: _f("Specimen Additives", "CWE", "O", True, 250),
    7: _f("Specimen Collection Method", "CWE", "O", False, 250),
    8: _f("Specimen Source Site", "CWE", "O", False, 250),
    9: _f("Specimen Source Site Modifier", "CWE", "O", True, 250),
    10: _f("Specimen Collection Site", "CWE", "O", False, 250),
    11: _f("Specimen Role", "CWE", "O", True, 250),
    12: _f("Specimen Collection Amount", "CQ", "O", False, 20),
    13: _f("Grouped Specimen Count", "NM", "O", False, 6),
    14: _f("Specimen Description", "ST", "O", True, 250),
    15: _f("Specimen Handling Code", "CWE", "O", True, 250),
    16: _f("Specimen Risk Code", "CWE", "O", True, 250),
    17: _f("Specimen Collection Date/Time", "DR", "O", False, 26),
    18: _f("Specimen Received Date/Time", "TS", "O", False, 26),
    19: _f("Specimen Expiration Date/Time", "TS", "O", False, 26),
    20: _f("Specimen Availability", "ID", "O", False, 1),
    21: _f("Specimen Reject Reason", "CWE", "O", True, 250),
    22: _f("Specimen Quality", "CWE", "O", False, 250),
    23: _f("Specimen Appropriateness", "CWE", "O", False, 250),
    24: _f("Specimen Condition", "CWE", "O", True, 250),
    25: _f("Specimen Current Quantity", "CQ", "O", False, 20),
    26: _f("Number of Specimen Containers", "NM", "O", False, 4),
    27: _f("Container Type", "CWE", "O", False, 250),
}}

HL7_V25["TQ1"] = {"name": "Timing/Quantity", "fields": {
    1: _f("Set ID", "SI", "O", False, 4),
    2: _f("Quantity", "CQ", "O", False, 20),
    3: _f("Repeat Pattern", "RPT", "O", True, 540),
    4: _f("Explicit Time", "TM", "O", True, 20),
    5: _f("Relative Time and Units", "CQ", "O", True, 20),
    6: _f("Service Duration", "CQ", "O", False, 20),
    7: _f("Start Date/Time", "TS", "R", False, 26),
    8: _f("End Date/Time", "TS", "O", False, 26),
    9: _f("Priority", "CWE", "O", True, 250),
    10: _f("Condition Text", "TX", "O", False, 250),
    11: _f("Text Instruction", "TX", "O", False, 250),
    12: _f("Conjunction", "ID", "C", False, 10),
    13: _f("Occurrence Duration", "CQ", "O", False, 20),
    14: _f("Total Occurrences", "NM", "O", False, 10),
}}

HL7_V25["TQ2"] = {"name": "Timing/Quantity Relationship", "fields": {
    1: _f("Set ID", "SI", "O", False, 4),
    2: _f("Sequence/Results Flag", "ID", "O", False, 1),
    3: _f("Related Placer Number", "EI", "O", True, 22),
    4: _f("Related Filler Number", "EI", "O", True, 22),
    5: _f("Related Placer Group Number", "EI", "O", True, 22),
    6: _f("Sequence Condition Code", "ID", "O", False, 2),
    7: _f("Cyclic Entry/Exit Indicator", "ID", "O", False, 1),
    8: _f("Sequence Condition Time Interval", "CQ", "O", False, 20),
    9: _f("Cyclic Group Maximum Number of Repeats", "NM", "O", False, 10),
    10: _f("Special Service Request Relationship", "ID", "O", False, 1),
}}


# ========== HL7 v2.8 SEGMENT DEFINITIONS ==========
# Start with v2.5 as base, then override/extend

HL7_V28 = copy.deepcopy(HL7_V25)

# MSH v2.8 extensions
HL7_V28["MSH"]["fields"][22] = _f("Sending Responsible Organization", "XON", "O", False, 567)
HL7_V28["MSH"]["fields"][23] = _f("Receiving Responsible Organization", "XON", "O", False, 567)
HL7_V28["MSH"]["fields"][24] = _f("Sending Network Address", "HD", "O", False, 227)
HL7_V28["MSH"]["fields"][25] = _f("Receiving Network Address", "HD", "O", False, 227)

# OBX v2.8 extensions
HL7_V28["OBX"]["fields"][20] = _f("Observation Site", "CWE", "O", True, 250)
HL7_V28["OBX"]["fields"][21] = _f("Observation Instance Identifier", "EI", "O", False, 22)
HL7_V28["OBX"]["fields"][22] = _f("Mood Code", "CNE", "O", False, 250)
HL7_V28["OBX"]["fields"][23] = _f("Performing Organization Name", "XON", "O", False, 567)
HL7_V28["OBX"]["fields"][24] = _f("Performing Organization Address", "XAD", "O", False, 631)
HL7_V28["OBX"]["fields"][25] = _f("Performing Organization Medical Director", "XCN", "O", False, 3002)

# CE→CWE in v2.8 key lab fields
for _seg_name, _field_nums in [
    ("OBX", [3, 6, 15, 17]),
    ("OBR", [4, 44, 45]),
    ("DG1", [3]),
    ("AL1", [2, 3]),
]:
    for _fnum in _field_nums:
        if _fnum in HL7_V28[_seg_name]["fields"]:
            _fld = HL7_V28[_seg_name]["fields"][_fnum]
            if _fld["dt"] == "CE":
                HL7_V28[_seg_name]["fields"][_fnum] = _f(
                    _fld["name"], "CWE", _fld["opt"], _fld["rep"], _fld["len"])

HL7_DEFS = {"2.3": HL7_V23, "2.5": HL7_V25, "2.8": HL7_V28}

# ========== MSH-18 CHARACTER SET MAPPING ==========

MSH18_TO_ENCODING = {
    "": "ASCII",
    "ASCII": "ASCII",
    "8859/1": "ISO-8859-1",
    "8859/2": "ISO-8859-2",
    "8859/3": "ISO-8859-3",
    "8859/4": "ISO-8859-4",
    "8859/5": "ISO-8859-5",
    "8859/6": "ISO-8859-6",
    "8859/7": "ISO-8859-7",
    "8859/8": "ISO-8859-8",
    "8859/9": "ISO-8859-9",
    "UNICODE": "UTF-8",
    "UNICODE UTF-8": "UTF-8",
    "UTF-8": "UTF-8",
}


# ========== ACCESSOR FUNCTIONS ==========

def resolve_version(version_string):
    """Map HL7 version string to a supported definition set."""
    if not version_string:
        return "2.5"
    v = version_string.strip()
    if v.startswith("2.8"):
        return "2.8"
    if v.startswith("2.5"):
        return "2.5"
    if v.startswith("2.3") or v == "2.4":
        return "2.3"
    if v.startswith("2.6") or v.startswith("2.7"):
        return "2.5"
    return "2.5"


def get_seg_def(seg_name, version):
    """Get segment definition dict or None."""
    defs = HL7_DEFS.get(version)
    return defs.get(seg_name) if defs else None


def get_field_def(seg_name, field_num, version):
    """Get field definition dict or None."""
    seg = get_seg_def(seg_name, version)
    if not seg or "fields" not in seg:
        return None
    return seg["fields"].get(field_num)
