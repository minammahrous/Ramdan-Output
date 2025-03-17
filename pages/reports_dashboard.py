import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy.sql import text
from db import get_sqlalchemy_engine
from auth import check_authentication, check_access
import io
import plotly.io as pio
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from textwrap import wrap
from bs4 import BeautifulSoup
# ✅ Hide Streamlit's menu and sidebar
st.markdown("""
    <style>
        [data-testid="stToolbar"] {visibility: hidden !important;}
        [data-testid="manage-app-button"] {display: none !important;}
        header {visibility: hidden !important;}
        footer {visibility: hidden !important;}
    </style>
""", unsafe_allow_html=True)

# ✅ Authenticate and enforce role-based access
check_authentication()
check_access(["user", "power user", "admin", "report"])

# ✅ Get database engine
engine = get_sqlalchemy_engine()

# ✅ Function to Fetch Data from PostgreSQL
def get_data(query, params=None):
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        return df
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        return pd.DataFrame()

# ✅ SQL Query to Fetch Production Data with Total Batch Output
query_production = """
    SELECT 
        "Machine", 
        "batch number",  
        a."Product" AS "Product",  
        SUM("quantity") AS "Produced Quantity",
        SUM(SUM("quantity")) OVER (PARTITION BY "Machine", "batch number") AS "Total Batch Output"
    FROM archive a
    WHERE "Activity" = 'Production' AND "Date" = :date AND "Day/Night/plan" = :shift
    GROUP BY "Machine", "batch number", a."Product"
    ORDER BY "Machine", "batch number";
"""

# ✅ Function to Create PDF Report
def create_pdf(df_av, df_archive, df_production, fig):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    # ✅ Set PDF Title
    c.setTitle("Machine Performance Report")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "📊 Machine Performance Report")

    # ✅ Convert Plotly graph to high-quality PNG
    img_buf = io.BytesIO()
    pio.write_image(fig, img_buf, format="png", scale=3)
    img_buf.seek(0)
    img = ImageReader(img_buf)
    c.drawImage(img, 50, 500, width=500, height=200)

    # ✅ Add tables
    add_table(c, "📋 Machine Activity Summary", df_archive, 450)
    add_table(c, "🏭 Production Summary", df_production, 300)
    add_table(c, "📈 AV Data", df_av, 150)

    # ✅ Save PDF
    c.save()
    buffer.seek(0)

    return buffer.getvalue()
def generate_full_html():
    fig_html = fig.to_html(full_html=False) if not df_av.empty else ""

    raw_html = f"""
    <html>
    <head>
        <title>Machine Performance Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ border: 1px solid black; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .graph-container {{ text-align: center; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>📊 Machine Performance Report</h1>
        <div class="graph-container">{fig_html}</div>
        <h2>📋 Machine Activity Summary</h2>
        {df_archive.to_html(index=False)}
        <h2>🏭 Production Summary</h2>
        {df_production.to_html(index=False)}
        <h2>📈 AV Data</h2>
        {df_av.to_html(index=False)}
    </body>
    </html>
    """

    # Minify and clean HTML using BeautifulSoup
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.prettify(formatter="minimal")
# ✅ Streamlit UI
st.title("📊 Machine Performance Dashboard")

# ✅ User Inputs
date_selected = st.date_input("📅 Select Date")
shift_selected = st.selectbox("🕒 Select Shift Type", ["Day", "Night", "Plan"])

# ✅ Fetch Data
query_av = """
    SELECT "machine", "Availability", "Av Efficiency", "OEE"
    FROM av
    WHERE "date" = :date AND "shift" = :shift
"""
query_archive = """
    SELECT "Machine", "Activity", SUM("time") as "Total_Time", AVG("efficiency") as "Avg_Efficiency"
    FROM archive
    WHERE "Date" = :date AND "Day/Night/plan" = :shift
    GROUP BY "Machine", "Activity"
"""

df_av = get_data(query_av, {"date": date_selected, "shift": shift_selected})
df_archive = get_data(query_archive, {"date": date_selected, "shift": shift_selected})
df_production = get_data(query_production, {"date": date_selected, "shift": shift_selected})

# ✅ Generate Graph
if not df_av.empty:
    st.subheader("📈 Machine Efficiency, Availability & OEE")
    fig = px.bar(df_av, x="machine", y=["Availability", "Av Efficiency", "OEE"], 
                 barmode="group", title="Performance Metrics per Machine",
                 color_discrete_map={"Availability": "#1f77b4", "Av Efficiency": "#ff7f0e", "OEE": "#2ca02c"})
    st.plotly_chart(fig)
else:
    st.warning("⚠️ No AV data available for the selected filters.")

# ✅ Display Tables
st.subheader("📋 Machine Activity Summary")
st.dataframe(df_archive)

st.subheader("🏭 Production Summary per Machine and Batch")
st.dataframe(df_production)

# ✅ PDF Download Button
if st.button("📥 Download Full Report as PDF"):
    pdf_report = create_pdf(df_av, df_archive, df_production, fig)
    file_name = f"{shift_selected}_{date_selected}.pdf"

    st.download_button(label="📥 Click here to download", 
                       data=pdf_report, 
                       file_name=file_name, 
                       mime="application/pdf")


html_bytes = generate_full_html().encode("utf-8")
html_file = f"{shift_selected}_{date_selected}.html"

# ✅ HTML Download Button
st.download_button(label="📥 Download Full Page as HTML", 
                   data=html_bytes, 
                   file_name=html_file, 
                   mime="text/html")
