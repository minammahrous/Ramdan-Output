import streamlit as st
from auth import authenticate_user, ROLE_ACCESS
from db import get_branches

# Hide Streamlit's menu and "Manage app" button
st.markdown("""
    <style>
        [data-testid="stToolbar"] {visibility: hidden !important;}
        [data-testid="manage-app-button"] {display: none !important;}
        header {visibility: hidden !important;}
        footer {visibility: hidden !important;}
    </style>
""", unsafe_allow_html=True)

# ✅ Authenticate user FIRST
user = authenticate_user()

if not user:  # Prevent undefined variable errors
    st.warning("Please log in first.")
    st.stop()

# ✅ Retrieve role and branch safely AFTER authentication
st.session_state["authenticated"] = True
st.session_state["username"] = user["username"]
st.session_state["role"] = user.get("role", "user")  # Default to "user"
st.session_state["branch"] = user.get("branch", "main")  # Default branch is "main"

# ✅ Ensure branch exists after authentication
branch = st.session_state["branch"]
display_branch = "October SDF" if branch == "main" else branch

# ✅ Show user details
st.markdown(f"**👤 Role:** `{st.session_state['role']}`  |  **🏢 Branch:** `{display_branch}`")

# ✅ Admins can select a branch
if st.session_state["role"] == "admin":
    branches = get_branches()
    selected_branch = st.selectbox(
        "Select a branch:", branches, 
        index=branches.index(branch) if branch in branches else 0
    )

    if selected_branch != branch:
        st.session_state["branch"] = selected_branch
        st.rerun()

# ✅ Display UI
st.title("Welcome to the App")
st.write("Use the sidebar to navigate.")

# ✅ Define accessible pages based on role
allowed_pages = ROLE_ACCESS.get(st.session_state["role"], [])

# ✅ Navigation links
if "shift_output_form" in allowed_pages:
    st.page_link("pages/shift_output_form.py", label="Shift Output Form")

if "reports_dashboard" in allowed_pages:
    st.page_link("pages/reports_dashboard.py", label="Reports Dashboard")

if "master_data" in allowed_pages:
    st.page_link("pages/master_data.py", label="Master Data Control")
    
if "user management" in allowed_pages:
    st.page_link("pages/user_management.py", label="User Management")
    
if "extract_data" in allowed_pages:
    st.page_link("pages/extract_data.py", label="Extract Data")

# ✅ Success message
st.success(f"Now working on: {display_branch}")
