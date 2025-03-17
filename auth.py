import streamlit as st
import psycopg2
import bcrypt
from db import get_db_connection
from db import get_main_db_connection

# Role-based access control
ROLE_ACCESS = {
    "admin": ["shift_output_form", "reports_dashboard", "master_data", "user_management", "extract_data", "change_password"],
    "user": ["shift_output_form", "reports_dashboard", "extract_data", "change_password"],
    "power user": ["shift_output_form", "reports_dashboard", "master_data", "extract_data", "change_password"],
    "report": ["reports_dashboard", "extract_data", "change_password"],
}

def check_authentication():
    if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
        st.warning("You must log in to access this page.")
        st.stop()  # Stops execution if the user is not authenticated

def check_access(required_roles):
    if "role" not in st.session_state or st.session_state["role"] not in required_roles:
        st.error("Access Denied: You do not have permission to view this page.")
        st.stop()        

def authenticate_user():
    """Handles user authentication and assigns branch based on database records."""
    
    # Prevent duplicate authentication checks
    if st.session_state.get("authenticated", False):
        st.sidebar.success(f"Logged in as {st.session_state['username']} ({st.session_state['role']})")
        return {
            "username": st.session_state["username"],
            "role": st.session_state["role"],
            "branch": st.session_state["branch"],
        }

    # Sidebar login form
    st.sidebar.header("Login")
    username = st.sidebar.text_input("Username", key="login_username")  
    password = st.sidebar.text_input("Password", type="password", key="login_password")

    if st.sidebar.button("Login", key="login_button"):
        conn = get_main_db_connection()
        cur = conn.cursor()

        try:
            # Fetch user details
            cur.execute("SELECT username, password, role, branch FROM users WHERE username = %s", (username,))
            user = cur.fetchone()

            if user:
                stored_password = user[1].strip()  # Ensure no extra spaces
                if bcrypt.checkpw(password.encode(), stored_password.encode()):
                    # Store login info in session state
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = user[0]
                    st.session_state["role"] = user[2]
                    st.session_state["branch"] = user[3]  # Assign branch from the users table
                    st.sidebar.success(f"Logged in as {user[0]} ({user[2]})")
                    st.rerun()
                else:
                    st.sidebar.error("Invalid username or password")

            else:
                st.sidebar.error("User not found")

        except Exception as e:
            st.sidebar.error("Database error. Please try again.")
            st.write(f"DEBUG: Auth error → {e}")

        finally:
            cur.close()
            conn.close()

    return None  # Authentication failed
