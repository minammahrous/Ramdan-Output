import streamlit as st
import bcrypt
import psycopg2
from db import get_main_db_connection  # Ensure it connects to the 'main' branch

# Hide Streamlit's menu and "Manage app" button
st.markdown("""
    <style>
        [data-testid="stToolbar"] {visibility: hidden !important;}
        [data-testid="manage-app-button"] {display: none !important;}
        header {visibility: hidden !important;}
        footer {visibility: hidden !important;}
    </style>
""", unsafe_allow_html=True)

def update_password(username, old_password, new_password):
    conn = get_main_db_connection()  # Connect to the main branch
    if not conn:
        st.error("Database connection failed.")
        return False

    try:
        cur = conn.cursor()

        # Fetch the user's current hashed password
        cur.execute("SELECT password FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

        if not user:
            st.error("User not found.")
            return False

        stored_password = user[0].strip()  # Ensure no spaces

        # Verify old password
        if not bcrypt.checkpw(old_password.encode(), stored_password.encode()):
            st.error("Old password is incorrect.")
            return False

        # Hash the new password
        hashed_new_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

        # Update the password in the database
        cur.execute("UPDATE users SET password = %s WHERE username = %s", (hashed_new_password, username))
        conn.commit()

        st.success("Password updated successfully!")
        return True

    except Exception as e:
        st.error("An error occurred while updating the password.")
        st.write(f"DEBUG: {e}")  # Log error for debugging
        return False

    finally:
        cur.close()
        conn.close()

# UI for password change
st.title("Change Password")

if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("You must be logged in to change your password.")
    st.stop()

st.write(f"Logged in as: **{st.session_state['username']}**")

old_password = st.text_input("Enter Old Password", type="password")
new_password = st.text_input("Enter New Password", type="password")
confirm_password = st.text_input("Confirm New Password", type="password")

if st.button("Update Password"):
    if new_password != confirm_password:
        st.error("New passwords do not match.")
    elif len(new_password) < 6:
        st.error("New password must be at least 6 characters long.")
    else:
        update_password(st.session_state["username"], old_password, new_password)

