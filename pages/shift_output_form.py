import streamlit as st
import datetime
import pandas as pd
import csv
import os
from db import get_sqlalchemy_engine
from sqlalchemy.sql import text  # Import SQL text wrapper
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from db import get_db_connection
import psycopg2
import bcrypt
from auth import check_authentication, check_access
# Hide Streamlit's menu and "Manage app" button
st.markdown("""
    <style>
        [data-testid="stToolbar"] {visibility: hidden !important;}
        [data-testid="manage-app-button"] {display: none !important;}
        header {visibility: hidden !important;}
        footer {visibility: hidden !important;}
    </style>
""", unsafe_allow_html=True)
# Authenticate user before anything else
check_authentication()

# Enforce access control: Only "user", "power user", and "admin" can access this form
check_access(["user", "power user", "admin"])

# Get the correct database engine for the assigned branch
engine = get_sqlalchemy_engine()

def reset_form():
    """Fully resets all form inputs, including downtime and batch entries, without logging out the user."""
    
    # ✅ Safely reset form fields
    st.session_state.pop("machine", None)
    st.session_state.pop("shift_type", None)
    st.session_state.pop("shift_duration", None)
    st.session_state.pop("selected_product", None)
    st.session_state.pop("product_batches", None)
    
    # ✅ Ensure submitted data is cleared
    st.session_state.pop("submitted_archive_df", None)
    st.session_state.pop("submitted_av_df", None)
    st.session_state.pop("modify_mode", None)
    st.session_state.pop("proceed_clicked", None)
    st.session_state.pop("show_confirmation", None)
    st.session_state.pop("replace_data", None)
    st.session_state.pop("restart_form", None)
    st.session_state.pop("submitted", None)

    # ✅ Reset downtime entries
    downtime_types = [
        "Maintenance DT", "Production DT", "Material DT", "Utility DT", 
        "QC DT", "Cleaning DT", "QA DT", "Changeover DT"
    ]
    
    for dt_type in downtime_types:
        st.session_state.pop(dt_type, None)  # ✅ Remove downtime hours
        st.session_state.pop(f"{dt_type}_comment", None)  # ✅ Remove downtime comments

    st.toast("🔄 Form reset successfully!")
    st.rerun()  # ✅ Force UI refresh to clear inputs
    
def save_to_database(archive_df, av_df):
    """Saves archive and av dataframes to PostgreSQL using SQLAlchemy."""
    engine = get_sqlalchemy_engine()

    if engine is None:
        st.error("❌ Database connection failed. Please check credentials.")
        return

    try:
        # ✅ Convert all numeric columns before inserting into DB
        numeric_cols_archive = ["time", "efficiency", "quantity", "rate", "standard rate"]
        numeric_cols_av = ["hours", "T.production time", "Availability", "Av Efficiency", "OEE"]

        for col in numeric_cols_archive:
            if col in archive_df.columns:
                archive_df[col] = pd.to_numeric(archive_df[col], errors="coerce")

        for col in numeric_cols_av:
            if col in av_df.columns:
                av_df[col] = pd.to_numeric(av_df[col], errors="coerce")

        # ✅ Debugging: Print Data Types Before Saving
        st.write("DEBUG: Archive Data Types Before Saving", archive_df.dtypes)
        st.write("DEBUG: AV Data Types Before Saving", av_df.dtypes)

        # ✅ Save data using SQLAlchemy (handles data types automatically)
        archive_df.to_sql("archive", engine, if_exists="append", index=False)
        av_df.to_sql("av", engine, if_exists="append", index=False)

        st.success("✅ Data saved to database successfully!")

    except Exception as e:
        st.error(f"❌ Critical error while saving: {e}")
def get_standard_rate(product, machine):
    query = text("""
        SELECT standard_rate FROM rates 
        WHERE product = :product AND machine = :machine
        LIMIT 1
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"product": product, "machine": machine}).fetchone()

    if result and result[0] is not None:
        try:
            return float(result[0])  # Ensure it's a valid float
        except ValueError:
            st.error(f"⚠️ Invalid standard_rate found for {product} - {machine}: {result[0]}")
            return 1  # Default to 1 to avoid division by zero
    else:
        st.warning(f"⚠️ No standard rate found for {product} - {machine}. Using 1 as default.")
        return 1  # Default to 1 to prevent division errors
# Function to fetch data from PostgreSQL
def fetch_data(query):
    """Fetch data from PostgreSQL and return as a list."""
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        return df["name"].tolist()
    except Exception as e:
        st.error(f"❌ Database error: {e}")
        return []

# Fetch machine list from database
machine_list = fetch_data("SELECT name FROM machines")

# Fetch product list from database
product_list = fetch_data("SELECT name FROM products")

# Check if product_list is empty
if not product_list:
    st.error("⚠️ Product list is empty. Please check the database.")
def clean_dataframe(df):
    """
    Cleans the dataframe by:
    1. Converting column names to strings to prevent errors.
    2. Stripping whitespaces from column names.
    3. Converting empty strings in numeric columns to NaN.
    4. Ensuring consistent data types.
    """
    df.columns = df.columns.astype(str).str.strip()  # Ensure all column names are strings
    
    numeric_cols = ["time", "quantity", "rate", "standard rate", "efficiency"]  # Adjust as needed

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")  # Convert to float, replace invalid values with NaN
    
    return df


st.title("Shift Output Report")

# Initialize session state for submitted data and modify mode
if "submitted_archive_df" not in st.session_state:
    st.session_state.submitted_archive_df = pd.DataFrame()
if "submitted_av_df" not in st.session_state:
    st.session_state.submitted_av_df = pd.DataFrame()
if "modify_mode" not in st.session_state:
    st.session_state.modify_mode = False
if st.button("Restart App"):
    reset_form()
    st.rerun()  # ✅ Force rerun to apply changes
# Check if product_list is empty
if not product_list:
    st.error("Product list is empty. Please check products.csv.")
else:
    # Read shift types from shifts.csv
    try:
        shifts_df = pd.read_csv("shifts.csv")
        shift_durations = shifts_df["code"].tolist()
        shift_working_hours = shifts_df["working hours"].tolist()
    except FileNotFoundError:
        st.error("shifts.csv file not found. Please create the file.")
        shift_durations = []
        shift_working_hours = []
    except Exception as e:
        st.error(f"An error occurred reading shifts.csv: {e}")
        shift_durations = []
        shift_working_hours = []
# Step 1: User selects Date, Machine, and Shift Type
st.subheader("Step 1: Select Shift Details")
shift_types = ["Day", "Night", "Plan"]
date = st.date_input("Date", value=st.session_state.get("date", datetime.date.today()), key="date")
selected_machine = st.selectbox("Select Machine", [""] + machine_list, index=0, key="machine")
shift_type = st.selectbox("Shift Type", [""] + shift_types, index=0, key="shift_type")
if st.button("Proceed"):
    st.session_state.proceed_clicked = True
    st.rerun()
if st.session_state.get("proceed_clicked", False):
    # Query to check if a record exists in 'av' table
    query = text("""
        SELECT COUNT(*) FROM av 
        WHERE date = :date AND shift = :shift AND machine = :machine
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"date": date, "shift": shift_type, "machine": selected_machine}).fetchone()

    if result and result[0] > 0:  # If a record already exists
        st.warning("⚠️ A report for this Date, Shift Type, and Machine already exists. Choose an action.")

    col1, col2 = st.columns(2)
    if col1.button("🗑️ Delete Existing Data and Proceed"):
        try:
            with engine.begin() as conn:  # Use engine.begin() to keep connection open
            # Check if records exist before deleting
                check_query_av = text("""
                    SELECT * FROM av WHERE date = :date AND shift = :shift AND machine = :machine
                """)
                result_av = conn.execute(check_query_av, {"date": date, "shift": shift_type, "machine": selected_machine}).fetchall()

                check_query_archive = text("""
                    SELECT * FROM archive WHERE "Date" = :date AND "Machine" = :machine AND "Day/Night/plan" = :shift
                """)
                result_archive = conn.execute(check_query_archive, {"date": date, "shift": shift_type, "machine": selected_machine}).fetchall()

                # Show records before deletion
                if not result_av and not result_archive:
                    st.warning("⚠️ No matching records found. Nothing to delete.")
                else:
                    st.write("🔍 Records found in 'av':", result_av)
                    st.write("🔍 Records found in 'archive':", result_archive)

                    # Proceed with deletion if records exist
                    delete_query_av = text("""
                        DELETE FROM av WHERE date = :date AND shift = :shift AND machine = :machine
                    """)
                    conn.execute(delete_query_av, {"date": date, "shift": shift_type, "machine": selected_machine})

                    delete_query_archive = text("""
                        DELETE FROM archive WHERE "Date" = :date AND "Machine" = :machine AND "Day/Night/plan" = :shift
                    """)
                    conn.execute(delete_query_archive, {"date": date, "shift": shift_type, "machine": selected_machine})

                    st.success("✅ Existing records deleted. You can proceed with new data entry.")
                    st.session_state.proceed_clicked = False  # Reset proceed state

        except Exception as e:
            st.error(f"❌ Error deleting records: {e}")

    if col2.button("🔄 Change Selection"):
            st.warning("🔄 Please modify the Date, Shift Type, or Machine to proceed.")
            st.session_state.proceed_clicked = False  # Reset proceed state
            st.stop()  # Prevents further execution

    else:
        st.success("✅ No existing record found. You can proceed with the form.")
    
shift_duration = st.selectbox("Shift Duration", [""] + shift_durations, index=0, key="shift_duration")
    
# Define downtime categories
downtime_types = [
    "Maintenance DT", "Production DT", "Material DT", "Utility DT", 
    "QC DT", "Cleaning DT", "QA DT", "Changeover DT"
]

st.subheader("Downtime (hours)")
downtime_data = {}

for dt_type in downtime_types:
    col1, col2 = st.columns(2)
    with col1:
        downtime_data[dt_type] = st.number_input(
            dt_type, min_value=0.0, step=0.1, format="%.1f",
            key=dt_type, value=st.session_state.get(dt_type, 0.0)  # ✅ Use default 0.0 if not set
        )
    with col2:
        if downtime_data[dt_type] > 0:
            downtime_data[f"{dt_type}_comment"] = st.text_area(
                f"Comment for {dt_type}",
                value=st.session_state.get(f"{dt_type}_comment", ""),  # ✅ Use default empty string
                placeholder="Enter comment here (required for downtime)",
                key=f"{dt_type}_comment"
            )


if "product_batches" not in st.session_state:
    st.session_state.product_batches = {}

selected_product = st.selectbox("Select Product", [""] + product_list, index=0, key="selected_product")

# Allow adding batches for multiple products
if selected_product:
    if selected_product not in st.session_state.product_batches:
        st.session_state.product_batches[selected_product] = []
with st.form("batch_entry_form"):
    batch = st.text_input("Batch Number")
    quantity = st.number_input("Production Quantity", min_value=0.0, step=0.1, format="%.1f")
    time_consumed = st.number_input("Time Consumed (hours)", min_value=0.0, step=0.1, format="%.1f")
    add_batch = st.form_submit_button("Add Batch")

    if add_batch:
        if selected_product:
            if len(st.session_state.product_batches[selected_product]) < 5:
                st.session_state.product_batches[selected_product].append({
                    "batch": batch,
                    "quantity": quantity,
                    "time_consumed": time_consumed
                })
            else:
                st.error(f"You can add a maximum of 5 batches for {selected_product}.")
        else:
            st.error("Please select a product before adding a batch.")
    # Display added batches for the selected product with delete buttons
for product, batch_list in st.session_state.product_batches.items():
    if batch_list:  # Only show if there are batches
        st.subheader(f"Added Batches for {product}:")
        
             # Display table headers
        cols = st.columns(4)
        cols[0].write("Batch")
        cols[1].write("Quantity")
        cols[2].write("Time Consumed")
        cols[3].write("Delete")

        # Ensure batch_data exists
        batches_to_delete = []
        for i, batch in enumerate(batch_list):
            cols[0].write(batch["batch"])
            cols[1].write(batch["quantity"])
            cols[2].write(batch["time_consumed"])
            
            # Delete button
            if cols[3].button("Delete", key=f"delete_{product}_{i}"):
                batches_to_delete.append(i)

        # Remove selected batches
        for i in sorted(batches_to_delete, reverse=True):
            del st.session_state.product_batches[product][i]
            st.rerun()



from sqlalchemy.sql import text  # Import SQL text wrapper

# Ensure session state variables exist
if "show_confirmation" not in st.session_state:
    st.session_state.show_confirmation = False
if "replace_data" not in st.session_state:
    st.session_state.replace_data = False
if "restart_form" not in st.session_state:
    st.session_state.restart_form = False
if "submitted" not in st.session_state:
    st.session_state.submitted = False  # Tracks if report is submitted

# Function to update session state safely
def set_replace_data():
    st.session_state.replace_data = True

def set_restart_form():
    st.session_state.restart_form = True


# Validation: Check if comments are provided for downtime entries
missing_comments = [dt_type for dt_type in downtime_types if downtime_data[dt_type] > 0 and not downtime_data[dt_type + "_comment"]]
if missing_comments:
    st.error(f"Please provide comments for the following downtime types: {', '.join(missing_comments)}")
else:     
    st.write(f"Machine: {selected_machine}")
    st.write(f"Date: {date}")
    st.write(f"Shift Type: {shift_type}")
    st.write(f"Shift Duration: {shift_duration}")
          

 
    # Construct archive_df (Downtime records)
archive_data = []
for dt_type in downtime_types:
    if downtime_data[dt_type] > 0:
        archive_row = {
            "Date": date,
            "Machine": selected_machine,
            "Day/Night/plan": shift_type,
            "Activity": dt_type,
            "time": downtime_data[dt_type],
            "Product": "",
            "batch number": "",
            "quantity": "",
            "comments": downtime_data[dt_type + "_comment"],
            "rate": "",
            "standard rate": "",
            "efficiency": "",
        }
        archive_data.append(archive_row)  # Append to the list

# Construct archive_df (Production batch records)
# ✅ Initialize average_efficiency with a default value
average_efficiency = 0  # Default to 0 if no efficiency data is available
# ✅ Always initialize production_data before using it
production_data = []
efficiencies = []  # Declare only once

if "product_batches" in st.session_state and st.session_state["product_batches"]:
    for product, batch_list in st.session_state["product_batches"].items():
        for batch in batch_list:
            rate = batch["quantity"] / batch["time_consumed"] if batch["time_consumed"] != 0 else 0
            standard_rate = get_standard_rate(product, selected_machine) or 1  # Avoid division by zero
            efficiency = rate / standard_rate
            efficiencies.append(efficiency)
            # ✅ Ensure efficiency calculation runs even if no products are added
            if efficiencies:
                average_efficiency = sum(efficiencies) / len(efficiencies)
                production_data.append({
                    "Date": date,
                    "Machine": selected_machine,
                    "Day/Night/plan": shift_type,
                    "Activity": "Production",
                    "time": batch["time_consumed"],
                    "Product": product,
                    "batch number": batch["batch"],
                    "quantity": batch["quantity"],
                    "comments": "",
                    "rate": rate,
                    "standard rate": standard_rate,
                    "efficiency": efficiency,
                })


# ✅ Merge both downtime and production records
archive_data.extend(production_data)

# ✅ Create DataFrame from the combined list
archive_df = pd.DataFrame(archive_data)

            # Construct av_df
total_production_time = sum(
    batch["time_consumed"] for product, batch_list in st.session_state.product_batches.items() for batch in batch_list
)

filtered_shift = shifts_df.loc[shifts_df['code'] == shift_duration, 'working hours']

if not filtered_shift.empty:
    standard_shift_time = filtered_shift.iloc[0]
else:
    st.error(f"⚠️ Shift duration '{shift_duration}' not found in shifts.csv.")
    standard_shift_time = None  # Set default value or handle gracefully


if shift_duration == "partial":
    total_downtime = sum(downtime_data.values()) - sum(1 for key in downtime_data if "_comment" in key)
    availability = total_production_time / (total_production_time + total_downtime) if (total_production_time + total_downtime) != 0 else 0
else:
    availability = total_production_time / standard_shift_time if standard_shift_time != 0 else 0

OEE = 0.99 * availability * average_efficiency
av_row = {
                    "date": date,
                    "machine": selected_machine,
                    "shift type": shift_duration,
                    "hours": standard_shift_time,
                    "shift": shift_type,
                    "T.production time": total_production_time,
                    "Availability": availability,
                    "Av Efficiency": average_efficiency,
                    "OEE": OEE,
}
av_df = pd.DataFrame([av_row])

# Store submitted data in session state
st.session_state.submitted_archive_df = archive_df
st.session_state.submitted_av_df = av_df

# Display submitted data
st.subheader("Submitted Archive Data")
st.dataframe(st.session_state.submitted_archive_df)
st.subheader("Submitted AV Data")
st.dataframe(st.session_state.submitted_av_df)
           # Compute total recorded time (downtime + production time)
total_production_time = sum(
    batch["time_consumed"] for product, batch_list in st.session_state.product_batches.items() for batch in batch_list
)
total_downtime = sum(downtime_data[dt] for dt in downtime_types)
total_recorded_time = total_production_time + total_downtime

# Fetch standard shift time
try:
    if shift_duration == "partial":
        standard_shift_time = None  # No standard time for partial shift
    else:
        standard_shift_time = shifts_df.loc[shifts_df['code'] == shift_duration, 'working hours'].iloc[0]
except IndexError:
    st.error("Shift duration not found in shifts.csv")
    standard_shift_time = 0  # Default to 0 to avoid None issues

# Compute total recorded time (downtime + production time)
total_production_time = sum(batch["time_consumed"] for batch in st.session_state.product_batches[selected_product])
total_downtime = sum(downtime_data[dt] for dt in downtime_types)
total_recorded_time = archive_df["time"].sum()

# Special check for "partial" shift
if shift_duration == "partial":
    if total_recorded_time > 7:
        st.error("⚠️ Total recorded time cannot exceed 7 hours for a partial shift!")
    st.warning("⏳ Shift visualization is not available for 'partial' shifts.")
else:
    # Only show visualization if shift is NOT "partial"
    st.subheader("Shift Time Utilization")
    fig, ax = plt.subplots(figsize=(5, 2))

    # Bar Chart - Only add standard shift time if it's not None
    ax.barh(["Total Time"], [total_recorded_time], color="blue", label="Recorded Time")

    if standard_shift_time is not None:
        ax.barh(["Total Time"], [standard_shift_time], color="gray", alpha=0.5, label="Shift Standard Time")

    # Ensure limits are set correctly
    valid_times = [total_recorded_time]
    if standard_shift_time is not None:
        valid_times.append(standard_shift_time)

    # Set x-axis limits only if valid values exist
    if valid_times:
        ax.set_xlim(0, max(valid_times) * 1.2)

    ax.set_xlabel("Hours")
    ax.legend()

    # Display Chart
    st.pyplot(fig)

    # Display numeric comparison
    st.write(f"**Total Recorded Time:** {total_recorded_time:.2f} hrs")
    if standard_shift_time is not None:
        st.write(f"**Standard Shift Time:** {standard_shift_time:.2f} hrs")

    # Warnings
    if standard_shift_time is not None:
        if total_recorded_time > standard_shift_time:
            st.warning("⚠️ Total recorded time exceeds the standard shift time!")
        elif total_recorded_time < 0.9 * standard_shift_time:
            st.warning("⚠️ Recorded time is less than 90% of the standard shift time.")

         # xchecks & Approve and Save 
    
if st.button("Approve and Save"):
    try:
        # Check for duplicate entries in both "av" and "archive" tables
        query_av = text("""
            SELECT COUNT(*) FROM av 
            WHERE date = :date AND "shift" = :shift AND machine = :machine
        """)
        query_archive = text("""
            SELECT COUNT(*) FROM archive 
            WHERE "Date" = :date AND "Machine" = :machine AND "Day/Night/plan" = :shift
        """)

        with engine.connect() as conn:
            result_av = conn.execute(query_av, {"date": date, "shift": shift_type, "machine": selected_machine}).fetchone()
            result_archive = conn.execute(query_archive, {"date": date, "shift": shift_type, "machine": selected_machine}).fetchone()

        # If a duplicate exists in either table, STOP execution completely
        if (result_av and result_av[0] > 0) or (result_archive and result_archive[0] > 0):
            st.error("❌ A report for this Date, Shift Type, and Machine already exists. Modify your selection or delete existing data before saving.")
            st.stop()  # ⛔ Completely stop execution

        else:
            st.success("No existing record found. Proceeding with approval.")

            # Clean DataFrames before using them
            archive_df = clean_dataframe(st.session_state.submitted_archive_df.copy())
            av_df = clean_dataframe(st.session_state.submitted_av_df.copy())

            # Get shift standard time
            standard_shift_time = shifts_df.loc[shifts_df['code'] == shift_duration, 'working hours'].iloc[0]

            # Validation checks
            total_recorded_time = archive_df["time"].sum()
            efficiency_invalid = (archive_df["efficiency"] > 1).any()
            time_exceeds_shift = total_recorded_time > standard_shift_time
            time_below_90 = total_recorded_time < (0.9 * standard_shift_time)

            if efficiency_invalid:
                st.error("Efficiency must not exceed 1. Please review and modify the data.")
            elif time_exceeds_shift:
                st.error(f"Total recorded time ({total_recorded_time} hrs) exceeds shift standard time ({standard_shift_time} hrs). Modify the data.")
            elif time_below_90:
                st.error(f"Total recorded time ({total_recorded_time} hrs) is less than 90% of shift standard time ({0.9 * standard_shift_time} hrs). Modify the data.")
            else:
                # Save cleaned data to PostgreSQL
                archive_df.to_sql("archive", engine, if_exists="append", index=False)
                av_df.to_sql("av", engine, if_exists="append", index=False)
                st.success("Data saved to database successfully!")
                # ✅ Reset form after successful save
                reset_form()
                st.rerun()  # ✅ Force rerun to apply changes
    except Exception as e:
        st.error(f"Error saving data: {e}")
