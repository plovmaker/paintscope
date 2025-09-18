"""
Authentication module for Streamlit app
Handles login, signup, and session management
"""

import streamlit as st
from typing import Optional, Dict
import db_service
import re


def init_session_state():
    """Initialize session state variables for authentication"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    return True, "Password is valid"


def login_page():
    """Display login page"""
    st.title("🎯 PaintScope - Login")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        login_form()
    
    with tab2:
        signup_form()


def login_form():
    """Display login form"""
    st.subheader("Welcome Back!")
    
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button("Login", use_container_width=True, type="primary")
        
        if submit:
            if not username or not password:
                st.error("Please enter both username and password")
            else:
                user = db_service.authenticate_user(username, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.session_state.user_id = user['id']  # Access as dictionary
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")


def signup_form():
    """Display signup form"""
    st.subheader("Create New Account")
    
    with st.form("signup_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            full_name = st.text_input("Full Name", placeholder="John Doe")
            username = st.text_input("Username", placeholder="johndoe")
            email = st.text_input("Email", placeholder="john@example.com")
        
        with col2:
            company = st.text_input("Company (Optional)", placeholder="ABC Construction")
            password = st.text_input("Password", type="password", placeholder="Min 8 characters")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Re-enter password")
        
        st.markdown("**Password Requirements:**")
        st.caption("• At least 8 characters • One uppercase letter • One lowercase letter • One number")
        
        submit = st.form_submit_button("Create Account", use_container_width=True, type="primary")
        
        if submit:
            # Validation
            errors = []
            
            if not all([full_name, username, email, password, confirm_password]):
                errors.append("Please fill in all required fields")
            
            if email and not validate_email(email):
                errors.append("Please enter a valid email address")
            
            if password:
                valid, msg = validate_password(password)
                if not valid:
                    errors.append(msg)
            
            if password != confirm_password:
                errors.append("Passwords do not match")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                # Check if user already exists
                existing_user = db_service.get_user_by_email(email)
                if existing_user:
                    st.error("An account with this email already exists")
                else:
                    # Create new user
                    user = db_service.create_user(
                        username=username,
                        email=email,
                        password=password,
                        full_name=full_name,
                        company=company
                    )
                    
                    if user:
                        st.success("Account created successfully! Please login.")
                        st.balloons()
                    else:
                        st.error("Username already taken. Please choose a different username.")


def logout():
    """Logout user and clear session"""
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.user_id = None
    # Clear other session state variables related to the app
    keys_to_clear = ['current_pdf', 'current_conversation', 'messages', 'pdf_images']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def require_auth():
    """Decorator to require authentication for certain functions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not st.session_state.get('authenticated', False):
                st.error("Please login to access this feature")
                st.stop()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def display_user_menu():
    """Display user menu in sidebar"""
    if st.session_state.authenticated and st.session_state.user:
        with st.sidebar:
            st.divider()
            st.markdown(f"**👤 {st.session_state.user['username']}**")
            if st.session_state.user.get('company'):
                st.caption(st.session_state.user['company'])
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Profile", use_container_width=True):
                    st.session_state.page = "profile"
            with col2:
                if st.button("Logout", use_container_width=True):
                    logout()


def profile_page():
    """Display user profile page"""
    st.title("👤 User Profile")
    
    user_data = db_service.get_user_session_data(st.session_state.user_id)
    
    if not user_data:
        st.error("Unable to load user data")
        return
    
    user = user_data['user']
    
    # Profile Information
    st.subheader("Profile Information")
    
    with st.form("profile_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            full_name = st.text_input("Full Name", value=user.get('full_name', ''))
            email = st.text_input("Email", value=user.get('email', ''), disabled=True)
        
        with col2:
            company = st.text_input("Company", value=user.get('company', ''))
            username = st.text_input("Username", value=user.get('username', ''), disabled=True)
        
        submit = st.form_submit_button("Update Profile", use_container_width=True)
        
        if submit:
            success = db_service.update_user_profile(
                st.session_state.user_id,
                full_name=full_name,
                company=company
            )
            if success:
                st.success("Profile updated successfully!")
                st.rerun()
            else:
                st.error("Failed to update profile")
    
    # Statistics
    st.divider()
    st.subheader("📊 Statistics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        pdfs_count = len(db_service.get_user_pdfs(st.session_state.user_id))
        st.metric("PDFs Uploaded", pdfs_count)
    
    with col2:
        convs_count = len(db_service.get_user_conversations(st.session_state.user_id))
        st.metric("Conversations", convs_count)
    
    with col3:
        st.metric("Member Since", user_data['user'].get('created_at', 'N/A'))
    
    # Recent Activity
    st.divider()
    st.subheader("🕒 Recent Activity")
    
    tab1, tab2 = st.tabs(["Recent PDFs", "Recent Conversations"])
    
    with tab1:
        if user_data['recent_pdfs']:
            for pdf in user_data['recent_pdfs']:
                st.write(f"📄 **{pdf['filename']}**")
                if pdf.get('project_name'):
                    st.caption(f"Project: {pdf['project_name']}")
                st.caption(f"Uploaded: {pdf['uploaded_at']}")
                st.divider()
        else:
            st.info("No PDFs uploaded yet")
    
    with tab2:
        if user_data['recent_conversations']:
            for conv in user_data['recent_conversations']:
                st.write(f"💬 **{conv['title']}**")
                if conv.get('pdf_filename'):
                    st.caption(f"PDF: {conv['pdf_filename']}")
                st.caption(f"Last updated: {conv['last_updated']}")
                st.divider()
        else:
            st.info("No conversations yet")
