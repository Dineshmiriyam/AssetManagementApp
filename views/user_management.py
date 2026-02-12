"""User Management page — user CRUD operations (admin only)."""

import streamlit as st

from config.permissions import check_page_access, render_access_denied
from services.audit_service import log_activity_event
from core.data import safe_rerun
from views.context import AppContext

try:
    from database.auth import (
        get_all_users, create_user, update_user,
        change_password, deactivate_user, activate_user,
    )
except ImportError:
    get_all_users = None

def render(ctx: AppContext) -> None:
    """Render this page."""
    # Route-level access control (defense in depth)
    if not check_page_access("User Management", st.session_state.user_role):
        render_access_denied(required_roles=["admin"])
        st.stop()

    st.markdown('<p class="main-header">User Management</p>', unsafe_allow_html=True)

    # User Management Tabs
    user_tabs = st.tabs(["All Users", "Create User"])

    # TAB 1: All Users
    with user_tabs[0]:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
            <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Registered Users</span>
        </div>
        """, unsafe_allow_html=True)

        if ctx.auth_available:
            users = get_all_users()

            if users:
                # User stats
                total_users = len(users)
                active_users = len([u for u in users if u.get('is_active', False)])
                admin_count = len([u for u in users if u.get('role') == 'admin'])

                stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
                with stat_col1:
                    st.metric("Total Users", total_users)
                with stat_col2:
                    st.metric("Active Users", active_users)
                with stat_col3:
                    st.metric("Inactive Users", total_users - active_users)
                with stat_col4:
                    st.metric("Admins", admin_count)

                st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

                # Users table
                for user in users:
                    user_id = user['id']
                    username = user['username']
                    email = user.get('email', 'N/A')
                    full_name = user.get('full_name', 'N/A')
                    role = user.get('role', 'operations')
                    is_active = user.get('is_active', False)
                    last_login = user.get('last_login', None)

                    # User card
                    status_color = "#10b981" if is_active else "#ef4444"
                    status_text = "Active" if is_active else "Inactive"

                    with st.expander(f"**{full_name or username}** ({username}) - {role.title()}", expanded=False):
                        col1, col2 = st.columns(2)

                        with col1:
                            st.write(f"**Username:** {username}")
                            st.write(f"**Email:** {email}")
                            st.write(f"**Full Name:** {full_name or 'Not set'}")

                        with col2:
                            st.write(f"**Role:** {role.title()}")
                            st.markdown(f"**Status:** <span style='color: {status_color};'>{status_text}</span>", unsafe_allow_html=True)
                            if last_login:
                                st.write(f"**Last Login:** {last_login}")
                            else:
                                st.write("**Last Login:** Never")

                        st.markdown("---")

                        # Action buttons (don't allow editing own account to prevent lockout)
                        if username != st.session_state.username:
                            action_col1, action_col2, action_col3, action_col4 = st.columns(4)

                            with action_col1:
                                # Change Role
                                new_role = st.selectbox(
                                    "Change Role",
                                    options=["admin", "operations", "finance"],
                                    index=["admin", "operations", "finance"].index(role) if role in ["admin", "operations", "finance"] else 1,
                                    key=f"role_{user_id}"
                                )
                                if new_role != role:
                                    if st.button("Update Role", key=f"update_role_{user_id}"):
                                        success, msg = update_user(user_id, {'role': new_role})
                                        if success:
                                            st.success(f"Role updated to {new_role}")
                                            safe_rerun()
                                        else:
                                            st.error(msg)

                            with action_col2:
                                # Reset Password
                                st.write("**Reset Password**")
                                new_pass = st.text_input("New Password", type="password", key=f"pass_{user_id}")
                                if new_pass:
                                    if st.button("Reset", key=f"reset_pass_{user_id}"):
                                        success, msg = change_password(user_id, new_pass)
                                        if success:
                                            st.success("Password reset successfully")
                                        else:
                                            st.error(msg)

                            with action_col3:
                                # Activate/Deactivate
                                if is_active:
                                    if st.button("Deactivate User", key=f"deactivate_{user_id}"):
                                        success, msg = deactivate_user(user_id)
                                        if success:
                                            st.success("User deactivated")
                                            safe_rerun()
                                        else:
                                            st.error(msg)
                                else:
                                    if st.button("Activate User", key=f"activate_{user_id}"):
                                        success, msg = activate_user(user_id)
                                        if success:
                                            st.success("User activated")
                                            safe_rerun()
                                        else:
                                            st.error(msg)
                        else:
                            st.info("This is your account. Use Settings to change your own password.")
            else:
                st.info("No users found in the database.")
        else:
            st.warning("Authentication module not available.")

    # TAB 2: Create User
    with user_tabs[1]:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #10b981;">
            <div style="width: 4px; height: 20px; background: #10b981; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Create New User</span>
        </div>
        """, unsafe_allow_html=True)

        if ctx.auth_available:
            with st.form("create_user_form"):
                col1, col2 = st.columns(2)

                with col1:
                    new_username = st.text_input("Username *", placeholder="e.g., john.doe")
                    new_email = st.text_input("Email *", placeholder="e.g., john@example.com")
                    new_password = st.text_input("Password *", type="password", placeholder="Minimum 6 characters")

                with col2:
                    new_full_name = st.text_input("Full Name", placeholder="e.g., John Doe")
                    new_role = st.selectbox("Role *", options=["operations", "finance", "admin"], index=0)
                    confirm_password = st.text_input("Confirm Password *", type="password")

                submitted = st.form_submit_button("Create User", type="primary")

                if submitted:
                    # Validation
                    errors = []
                    if not new_username:
                        errors.append("Username is required")
                    elif len(new_username) < 3:
                        errors.append("Username must be at least 3 characters")

                    if not new_email:
                        errors.append("Email is required")
                    elif "@" not in new_email:
                        errors.append("Invalid email format")

                    if not new_password:
                        errors.append("Password is required")
                    elif len(new_password) < 6:
                        errors.append("Password must be at least 6 characters")

                    if new_password != confirm_password:
                        errors.append("Passwords do not match")

                    if errors:
                        for error in errors:
                            st.error(error)
                    else:
                        success, user_id, msg = create_user(
                            username=new_username,
                            email=new_email,
                            password=new_password,
                            full_name=new_full_name,
                            role=new_role
                        )

                        if success:
                            st.success(f"User '{new_username}' created successfully!")
                            # Log activity
                            log_activity_event(
                                action_type="USER_CREATED",
                                category="authentication",
                                user_role=st.session_state.user_role,
                                description=f"New user created: {new_username} (role: {new_role})",
                                success=True
                            )
                            # Refresh page to show new user in list
                            safe_rerun()
                        else:
                            st.error(f"Failed to create user: {msg}")
        else:
            st.warning("Authentication module not available.")

    # IMPORT/EXPORT PAGE

