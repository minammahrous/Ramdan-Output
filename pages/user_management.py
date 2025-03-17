import streamlit as st
import psycopg2
import bcrypt
from db import get_db_connection
from auth import check_authentication, check_access

def get_users():
    """Fetch all users from the database."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, role, branch FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return users

def add_user(username, password, role, branch):
    """Add a new user with hashed password."""
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (username, password, role, branch) VALUES (%s, %s, %s, %s)", 
                (username, hashed_password, role, branch))
    conn.commit()
    cur.close()
    conn.close()

def update_user(user_id, role, branch):
    """Update user's role or branch."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET role = %s, branch = %s WHERE id = %s", (role, branch, user_id))
    conn.commit()
    cur.close()
    conn.close()

def reset_password(user_id, new_password):
    """Reset a user's password."""
    hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, user_id))
    conn.commit()
    cur.close()
    conn.close()

def delete_user(user_id):
    """Delete a user."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()

# Check authentication and access
check_authentication()
check_access(["admin"])

st.title("User Management")

# Display users
users = get_users()
user_options = {str(user[0]): f"{user[1]} ({user[2]})" for user in users}
selected_user = st.selectbox("Select User to Edit", options=["New User"] + list(user_options.keys()), format_func=lambda x: user_options.get(x, "New User"))

if selected_user == "New User":
    st.subheader("Add New User")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["admin", "user", "power user", "report"])
    branch = st.text_input("Branch")
    
    if st.button("Add User"):
        add_user(username, password, role, branch)
        st.success("User added successfully!")
        st.rerun()
else:
    st.subheader("Edit User")
    user_id = int(selected_user)
    user_data = next((u for u in users if u[0] == user_id), None)
    if user_data:
        new_role = st.selectbox("Role", ["admin", "user", "power user", "report"], index=["admin", "user", "power user", "report"].index(user_data[2]))
        new_branch = st.text_input("Branch", value=user_data[3])
        
        if st.button("Update User"):
            update_user(user_id, new_role, new_branch)
            st.success("User updated successfully!")
            st.rerun()
        
        new_password = st.text_input("New Password", type="password")
        if st.button("Reset Password"):
            reset_password(user_id, new_password)
            st.success("Password reset successfully!")
        
        if st.button("Delete User", key=f"delete_{user_id}"):
            delete_user(user_id)
            st.warning("User deleted!")
            st.rerun()
