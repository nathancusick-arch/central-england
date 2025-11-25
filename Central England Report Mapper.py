import streamlit as st
import pandas as pd
import io

# ============================================================
# COLUMN MAP
# ============================================================

COLUMN_MAP = {
    "Order": "order_internal_id",
    "Client": "client_name",
    "Visit": "internal_id",
    "Site": "site_internal_id",
    "Order Deadline": "end_date",
    "Responsibility": "responsibility",
    "Premises Name": "site_name",
    "Address1": "site_address_1",
    "Address2": "site_address_2",
    "Address3": "site_address_3",
    "City": None,
    "Post Code": "site_post_code",
    "Submitted Date": "submitted_date",
    "Approved Date": "approval_date",
    "Item to order": "item_to_order",
    "Actual Visit Date": "date_of_visit",
    "Actual Visit Time": "time_of_visit",
    "AM / PM": None,
    "Pass-Fail": "primary_result",
    "Pass-Fail2": "secondary_result",
    "Abort Reason": "Please detail why you were unable to conduct this audit:",
    "Extra Site 1": "site_code",
    "Extra Site 2": None,
    "Extra Site 3": None,
    "Extra Site 4": None,
    "Extra Site 5": None,
    "VISITORSEX": None,
    "What type of alcohol did you purchase?": ["What type of E-cigarette product did you purchase/attempt to purchase?", "What type of alcohol did you try to purchase?"],
    "Please give details of the alcohol purchased (brand and size):": ["Please give details of the e-cig product that you purchased:", "Please give details of the cigarettes that you purchased:", "Please give details of the alcohol that you purchased:"],
    "Did you make the purchase on its own or as part of a larger shop?": "Did you make the purchase on its own or as part of a larger shop?",
    "Did the operator ask your age?": None,
    "Did the operator ask for your ID during the transaction?": "Did the staff member who served you ask for ID?",
    "Did the operator make eye contact with you during the transaction?": "Did the staff member who served you make eye contact with you during the transaction?",
    "If eye contact was made, when was it FIRST made?": "When was eye contact first made?",
    "In your opinion, did the operator make an assessment of your age?": "Did the staff member who served you look at you long enough to assess your age?  ",
    "Was the operator wearing a name badge?": "Was the staff member who served you wearing a name badge?",
    "If they were, please state their name:": "What was the name of the staff member who served you?",
    "Please accurately describe the operator that served you (include hair colour and style, build, height and any distinguishing features):": "Please accurately describe the staff member who served you:",
    "Was there any \"Challenge 25\" signage visible in the till area?": "Was there any generic 'Challenge 25' material visible from the till?",
    "Was the operator wearing a \"Challenge 25\" Badge?": "Was the staff member wearing a 'Challenge 25' badge?",
    "OTHER VISIT DETAILS": None,
    "How many staff members were serving?": ["How many staff members were working on the tills?", "How staff members were working on the tills?"],
    "Please comment on the overall service you received (include queue length and unattended tills):": "Please comment on the overall service you received:",
    "From the receipt, please enter the store name:": "From the top of the receipt, please enter the store name:",
    "Please enter the receipt number (#000000):": "Please enter the receipt number (#000000) from the receipt:",
    "Please enter the C number (C:000000):": "Please enter the C number (C:000000) from the receipt:",
    "Please enter the T number (T:00):": "Please enter the T number (T:00) from the receipt:",
    "Please describe the location and positions of the store (i.e. names of the stores on either side):": None,
    "Please use this space to explain anything unusual about your visit or to clarify any detail of your report:": "Please use this space to explain anything unusual about your visit or to clarify any detail of your report:",
    "Please confirm below whether or not you were asked for ID:": ["Please confirm below whether or not you were asked for ID:", "Please confirm whether or not you were asked for ID, and if so, at what point during the transaction ID was requested:"]
}

# ============================================================
# STREAMLIT UI
# ============================================================

st.title("Central England Report Mapper")

st.write("""
          1. Export the previous 2 weeks worth of data
          2. Drop the file in the below box, it should then give you the output file in your downloads
          3. Standard bits - Check data vs previous week, remove data already reported, paste over new data
          4. Copy and paste over values etc!!!
          5. Done.
          """)

uploaded = st.file_uploader("Upload audits_basic_data_export.csv", type=["csv"])

# ============================================================
# PROCESSING WHEN FILE UPLOADED
# ============================================================

if uploaded:

    df = pd.read_csv(uploaded, dtype=str)

    df["item_to_order"] = df["item_to_order"].fillna("").astype(str)
    df["primary_result"] = df["primary_result"].fillna("").astype(str)

    # FILTER OUT RAPID DELIVERY & ABORTS
    df = df[df["item_to_order"].str.strip().str.lower() != "rapid delivery"]
    df = df[df["primary_result"].str.strip().str.lower() != "abort"]

    # ============================================================
    # GENERIC MAPPING FUNCTION
    # ============================================================

    def map_value(row, mapping):
        if mapping is None:
            return ""
        if isinstance(mapping, list):
            vals = []
            for col in mapping:
                if col in row and pd.notna(row[col]):
                    cleaned = str(row[col]).strip()
                    if cleaned:
                        vals.append(cleaned)
            return " | ".join(vals)
        if mapping in row and pd.notna(row[mapping]):
            return str(row[mapping]).strip()
        return ""

    # ============================================================
    # BUILD FINAL OUTPUT
    # ============================================================

    final_df = pd.DataFrame()

    for report_col, export_mapping in COLUMN_MAP.items():
        final_df[report_col] = df.apply(lambda row: map_value(row, export_mapping), axis=1)

    # ============================================================
    # DOWNLOAD OUTPUT
    # ============================================================

    output_bytes = io.BytesIO()
    final_df.to_csv(output_bytes, index=False, encoding="utf-8-sig")
    output_bytes.seek(0)

    st.success(f"File processed successfully! Rows: {len(final_df)}")

    st.download_button(
        "Download Central England CSV",
        data=output_bytes.getvalue(),
        file_name="Central England Data.csv",
        mime="text/csv"
    )
