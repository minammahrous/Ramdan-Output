import streamlit as st
import pandas as pd
from db import get_sqlalchemy_engine
from io import BytesIO
from auth import check_authentication

# Hide Streamlit's menu and "Manage app" button
st.markdown("""
    <style>
        [data-testid="stToolbar"] {visibility: hidden !important;}
        [data-testid="manage-app-button"] {display: none !important;}
        header {visibility: hidden !important;}
        footer {visibility: hidden !important;}
    </style>
""", unsafe_allow_html=True)

def fetch_data(engine, table, start_date, end_date):
    """Fetch data from a given table between two dates."""
    column_mapping = {
        "av": "date",
        "archive": "Date"
    }
    date_column = column_mapping[table]
    query = f"""
        SELECT * FROM {table}
        WHERE "{date_column}" BETWEEN '{start_date}' AND '{end_date}'
    """
    return pd.read_sql(query, con=engine)

def generate_excel(av_df, archive_df, branch, start_date, end_date):
    """Generate an Excel file with two sheets."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        av_df.to_excel(writer, sheet_name='av', index=False)
        archive_df.to_excel(writer, sheet_name='archive', index=False)
    filename = f"{branch}_{start_date}_to_{end_date}.xlsx"
    return output.getvalue(), filename

# Authenticate user
check_authentication()

st.title("Extract Data")

# Select date range
start_date = st.date_input("Start Date")
end_date = st.date_input("End Date")

if st.button("Extract Data"):
    if start_date > end_date:
        st.error("Start date cannot be after end date.")
    else:
        branch = st.session_state.get("branch", "main")
        engine = get_sqlalchemy_engine()
        
        av_data = fetch_data(engine, "av", start_date, end_date)
        archive_data = fetch_data(engine, "archive", start_date, end_date)
        
        excel_data, filename = generate_excel(av_data, archive_data, branch, start_date, end_date)
        
        st.download_button(
            label="Download Excel File",
            data=excel_data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

