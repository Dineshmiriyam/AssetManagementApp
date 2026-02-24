"""Clients page — client directory with contact management."""

import pandas as pd
import streamlit as st

from components.empty_states import render_empty_state
from components.feedback import render_error_state
from core.data import safe_rerun, clear_cache, paginate_dataframe, render_page_navigation
from core.errors import log_error
from services.client_service import (
    create_client_record, update_client_record,
    add_contact, update_contact_record, remove_contact,
)
from database.db import get_client_by_id, get_client_contacts
from views.context import AppContext


def render(ctx: AppContext) -> None:
    """Render this page."""
    st.markdown('<p class="main-header">Clients</p>', unsafe_allow_html=True)

    if not ctx.api:
        st.warning("Please configure your database connection in Settings first.")
    elif st.session_state.get('data_load_error'):
        render_error_state(
            error_message=st.session_state.data_load_error or "Unable to load clients data. Please try again.",
            error_type="database",
            show_retry=True,
            retry_key="retry_data_load"
        )
    else:
        user_role = st.session_state.get("user_role", "operations")
        tab1, tab2, tab3 = st.tabs(["View Clients", "Add Client", "Manage Contacts"])

        # ── Tab 1: View Clients (+ inline Edit) ─────────────
        with tab1:
            editing_id = st.session_state.get("editing_client_id")

            # ── Inline Edit Mode ──
            if editing_id:
                editing_data = get_client_by_id(editing_id)
                if not editing_data:
                    st.error("Client not found.")
                    del st.session_state["editing_client_id"]
                else:
                    # Header with back button
                    if st.button("← Back to Client List", key="cancel_edit_client"):
                        del st.session_state["editing_client_id"]
                        safe_rerun()

                    st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #f59e0b;">
                        <div style="width: 4px; height: 20px; background: #f59e0b; border-radius: 2px;"></div>
                        <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Edit Client — {editing_data.get('client_name', '')}</span>
                    </div>
                    """, unsafe_allow_html=True)

                    with st.form("edit_client_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            edit_name = st.text_input("Client Name *", value=editing_data.get("client_name", ""))
                            edit_contact = st.text_input("Contact Person", value=editing_data.get("contact_person", "") or "")
                            edit_email = st.text_input("Email", value=editing_data.get("email", "") or "")
                            edit_phone = st.text_input("Phone", value=editing_data.get("phone", "") or "")
                        with col2:
                            type_options = ["Rental", "Sale", "Both"]
                            current_type = editing_data.get("client_type", "Rental")
                            type_index = type_options.index(current_type) if current_type in type_options else 0
                            edit_type = st.selectbox("Client Type *", type_options, index=type_index)
                            edit_active = st.checkbox("Active", value=(editing_data.get("status", "ACTIVE") == "ACTIVE"))
                            edit_address = st.text_area("Address", value=editing_data.get("address", "") or "")
                            edit_billing = st.number_input("Billing Rate (₹/month)", min_value=0, value=int(editing_data.get("billing_rate", 0) or 0), step=100)

                        if st.form_submit_button("Update Client", type="primary"):
                            if not edit_name:
                                st.error("Client Name is required!")
                            else:
                                record = {
                                    "Client Name": edit_name,
                                    "Client Type": edit_type,
                                    "Status": "ACTIVE" if edit_active else "INACTIVE",
                                    "Billing Rate": edit_billing,
                                }
                                if edit_contact: record["Contact Person"] = edit_contact
                                if edit_email: record["Email"] = edit_email
                                if edit_phone: record["Phone"] = edit_phone
                                if edit_address: record["Address"] = edit_address

                                success, error = update_client_record(editing_id, record, user_role)
                                if success:
                                    st.success(f"Client '{edit_name}' updated successfully!")
                                    del st.session_state["editing_client_id"]
                                    safe_rerun()
                                else:
                                    st.error(f"Failed to update client: {error}")

            # ── Normal List Mode ──
            else:
                if not ctx.clients_df.empty:
                    # Search and filter row
                    ccol1, ccol2, ccol3, ccol4 = st.columns([2, 1, 1, 0.5])

                    with ccol1:
                        client_search = st.text_input("🔍 Search Client Name", key="client_search", placeholder="Type to search...")

                    with ccol2:
                        client_type_list = sorted(list(ctx.clients_df["Client Type"].dropna().unique())) if "Client Type" in ctx.clients_df.columns else []
                        client_type_filter = st.selectbox("Type", ["All"] + client_type_list, key="client_type_filter")

                    with ccol3:
                        status_filter = st.selectbox("Status", ["Active", "All"], key="client_status_filter")

                    with ccol4:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        if st.button("Clear", key="clear_client_filters", use_container_width=True):
                            for key in ["client_search", "client_type_filter", "client_status_filter"]:
                                if key in st.session_state:
                                    del st.session_state[key]
                            safe_rerun()

                    # Apply filters
                    filtered_clients = ctx.clients_df.copy()

                    if status_filter == "Active" and "Status" in filtered_clients.columns:
                        filtered_clients = filtered_clients[filtered_clients["Status"] == "ACTIVE"]

                    if client_type_filter != "All" and "Client Type" in filtered_clients.columns:
                        filtered_clients = filtered_clients[filtered_clients["Client Type"] == client_type_filter]

                    if client_search and "Client Name" in filtered_clients.columns:
                        filtered_clients = filtered_clients[filtered_clients["Client Name"].str.contains(client_search, case=False, na=False)]

                    # Results count
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 8px; padding: 8px 0; margin-bottom: 8px;">
                        <span style="font-size: 14px; color: #374151; font-weight: 500;">Showing</span>
                        <span style="font-size: 16px; color: #3b82f6; font-weight: 700;">{len(filtered_clients)}</span>
                        <span style="font-size: 14px; color: #6b7280;">of {len(ctx.clients_df)} clients</span>
                    </div>
                    """, unsafe_allow_html=True)

                    # Apply pagination to client list
                    paginated_clients = paginate_dataframe(filtered_clients, "clients_table", show_controls=True)

                    # Show client cards
                    for idx, client in paginated_clients.iterrows():
                        client_name = client.get('Client Name', 'Unknown')
                        client_type = client.get('Client Type', 'N/A')
                        is_active = client.get('Is Active', 0)
                        status_badge = "🟢" if is_active else "🔴"

                        with st.expander(f"{status_badge} **{client_name}** — {client_type}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown("""
                                <div style="font-size: 13px; font-weight: 600; color: #6b7280; margin-bottom: 4px;">PRIMARY CONTACT</div>
                                """, unsafe_allow_html=True)
                                st.write(f"**Name:** {client.get('Contact Person') or 'Not set'}")
                                st.write(f"**Email:** {client.get('Email') or '—'}")
                                st.write(f"**Phone:** {client.get('Phone') or '—'}")
                            with col2:
                                st.write(f"**Type:** {client_type}")
                                st.write(f"**Status:** {'Active' if is_active else 'Inactive'}")
                                st.write(f"**Billing Rate:** ₹{client.get('Billing Rate', 0):,.0f}/month" if client.get('Billing Rate') else "**Billing Rate:** —")

                                # Count assets with this client
                                if not ctx.assets_df.empty and "Current Location" in ctx.assets_df.columns:
                                    asset_count = len(ctx.assets_df[ctx.assets_df["Current Location"] == client_name])
                                    st.write(f"**Assets Deployed:** {asset_count}")

                            # Edit button — right-aligned, primary (orange per app theme)
                            btn_spacer, btn_col = st.columns([5, 1])
                            with btn_col:
                                if st.button("✏️ Edit", key=f"edit_client_{client.get('_id', idx)}", type="primary", use_container_width=True):
                                    st.session_state.editing_client_id = client.get('_id')
                                    safe_rerun()

                    render_page_navigation("clients_table")
                else:
                    render_empty_state("no_clients", show_action=False)
                    if st.button("Add Your First Client", key="add_first_client_inline"):
                        st.session_state.show_add_client = True
                        safe_rerun()

        # ── Tab 2: Add Client ────────────────────────────────
        with tab2:
            # Section header
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #10b981;">
                <div style="width: 4px; height: 20px; background: #10b981; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Add New Client</span>
            </div>
            """, unsafe_allow_html=True)

            with st.form("add_client_form"):
                col1, col2 = st.columns(2)

                with col1:
                    client_name = st.text_input("Client Name *", placeholder="e.g., X3i Solution")
                    contact_person = st.text_input("Contact Person")
                    email = st.text_input("Email")
                    phone = st.text_input("Phone")

                with col2:
                    client_type = st.selectbox("Client Type *", ["Rental", "Sale", "Both"])
                    is_active = st.checkbox("Active", value=True)
                    address = st.text_area("Address")
                    billing_rate = st.number_input("Billing Rate (₹/month)", min_value=0, value=0, step=100)

                submitted = st.form_submit_button("Add Client", type="primary")

                if submitted:
                    if not client_name:
                        st.error("Client Name is required!")
                    else:
                        record = {
                            "Client Name": client_name,
                            "Client Type": client_type,
                            "Is Active": is_active,
                            "Billing Rate": billing_rate,
                        }
                        if contact_person: record["Contact Person"] = contact_person
                        if email: record["Email"] = email
                        if phone: record["Phone"] = phone
                        if address: record["Address"] = address

                        success, client_id, error = create_client_record(record, user_role)
                        if success:
                            st.success(f"Client '{client_name}' added successfully!")
                        else:
                            st.error(f"Failed to add client: {error}")

        # ── Tab 3: Manage Contacts ───────────────────────────
        with tab3:
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
                <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Client Contacts</span>
            </div>
            """, unsafe_allow_html=True)

            if ctx.clients_df.empty:
                st.info("No clients available. Add a client first.")
            else:
                # Client selector
                client_options = ctx.clients_df["Client Name"].dropna().unique().tolist()
                selected_client_name = st.selectbox("Select Client", client_options, key="contacts_client_select")

                # Get client ID
                client_row = ctx.clients_df[ctx.clients_df["Client Name"] == selected_client_name]
                if client_row.empty:
                    st.warning("Client not found.")
                else:
                    client_id = int(client_row.iloc[0]["_id"])

                    # Fetch contacts
                    contacts_df = get_client_contacts(client_id)

                    if not contacts_df.empty:
                        st.markdown(f"""
                        <div style="display: flex; align-items: center; gap: 8px; padding: 8px 0; margin-bottom: 8px;">
                            <span style="font-size: 14px; color: #374151; font-weight: 500;">Contacts for</span>
                            <span style="font-size: 16px; color: #3b82f6; font-weight: 700;">{selected_client_name}</span>
                            <span style="font-size: 14px; color: #6b7280;">({len(contacts_df)} total)</span>
                        </div>
                        """, unsafe_allow_html=True)

                        # Display contacts
                        for c_idx, contact in contacts_df.iterrows():
                            contact_id = contact.get("_id")
                            is_primary = contact.get("Is Primary", False)
                            primary_badge = " ⭐" if is_primary else ""
                            role = contact.get("Role", "Primary")

                            with st.expander(f"**{contact.get('Contact Name', 'Unknown')}** — {role}{primary_badge}"):
                                cc1, cc2 = st.columns(2)
                                with cc1:
                                    st.write(f"**Email:** {contact.get('Email') or '—'}")
                                    st.write(f"**Phone:** {contact.get('Phone') or '—'}")
                                with cc2:
                                    st.write(f"**Role:** {role}")
                                    st.write(f"**Primary:** {'Yes' if is_primary else 'No'}")
                                if contact.get("Notes"):
                                    st.write(f"**Notes:** {contact.get('Notes')}")

                                # Action buttons — Edit (orange/primary), Delete (green/default)
                                btn_c1, btn_c2, btn_spacer = st.columns([1, 1, 3])
                                with btn_c1:
                                    if st.button("✏️ Edit", key=f"edit_contact_{contact_id}", type="primary", use_container_width=True):
                                        st.session_state.editing_contact_id = contact_id
                                        safe_rerun()
                                with btn_c2:
                                    if st.button("🗑️ Delete", key=f"del_contact_{contact_id}", use_container_width=True):
                                        success, error = remove_contact(contact_id, user_role)
                                        if success:
                                            st.success("Contact deleted.")
                                            safe_rerun()
                                        else:
                                            st.error(f"Failed to delete: {error}")
                    else:
                        st.info(f"No contacts for {selected_client_name} yet. Add one below.")

                    # Edit contact form (shown when editing)
                    editing_contact_id = st.session_state.get("editing_contact_id")
                    if editing_contact_id and not contacts_df.empty:
                        edit_row = contacts_df[contacts_df["_id"] == editing_contact_id]
                        if not edit_row.empty:
                            edit_data = edit_row.iloc[0]
                            st.markdown("---")
                            st.markdown("**Edit Contact**")
                            with st.form("edit_contact_form"):
                                ec1, ec2 = st.columns(2)
                                with ec1:
                                    edit_name = st.text_input("Contact Name *", value=edit_data.get("Contact Name", ""))
                                    role_options = ["Primary", "Billing", "Technical", "Escalation"]
                                    current_role = edit_data.get("Role", "Primary")
                                    role_idx = role_options.index(current_role) if current_role in role_options else 0
                                    edit_role = st.selectbox("Role", role_options, index=role_idx)
                                    edit_primary = st.checkbox("Primary Contact", value=bool(edit_data.get("Is Primary", False)))
                                with ec2:
                                    edit_email = st.text_input("Email", value=edit_data.get("Email", "") or "")
                                    edit_phone = st.text_input("Phone", value=edit_data.get("Phone", "") or "")
                                    edit_notes = st.text_input("Notes", value=edit_data.get("Notes", "") or "")

                                ec_btn1, ec_btn2, ec_spacer = st.columns([1, 1, 3])
                                with ec_btn1:
                                    save_edit = st.form_submit_button("Save Changes", type="primary")
                                with ec_btn2:
                                    cancel_edit = st.form_submit_button("Cancel")

                                if save_edit:
                                    if not edit_name:
                                        st.error("Contact Name is required!")
                                    else:
                                        update_data = {
                                            "contact_name": edit_name,
                                            "contact_role": edit_role,
                                            "email": edit_email or None,
                                            "phone": edit_phone or None,
                                            "is_primary": edit_primary,
                                            "notes": edit_notes or None,
                                        }
                                        success, error = update_contact_record(editing_contact_id, update_data, user_role)
                                        if success:
                                            st.success("Contact updated!")
                                            del st.session_state["editing_contact_id"]
                                            safe_rerun()
                                        else:
                                            st.error(f"Failed to update: {error}")
                                if cancel_edit:
                                    del st.session_state["editing_contact_id"]
                                    safe_rerun()

                    # Add new contact form
                    st.markdown("---")
                    st.markdown("""
                    <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                        Add New Contact
                    </div>
                    """, unsafe_allow_html=True)

                    with st.form("add_contact_form"):
                        ac1, ac2 = st.columns(2)
                        with ac1:
                            new_contact_name = st.text_input("Contact Name *", key="new_contact_name", placeholder="e.g., John Doe")
                            new_contact_role = st.selectbox("Role", ["Primary", "Billing", "Technical", "Escalation"], key="new_contact_role")
                            new_contact_primary = st.checkbox("Set as Primary Contact", key="new_contact_primary")
                        with ac2:
                            new_contact_email = st.text_input("Email", key="new_contact_email")
                            new_contact_phone = st.text_input("Phone", key="new_contact_phone")
                            new_contact_notes = st.text_input("Notes", key="new_contact_notes")

                        add_submitted = st.form_submit_button("Add Contact", type="primary")

                        if add_submitted:
                            if not new_contact_name:
                                st.error("Contact Name is required!")
                            else:
                                contact_data = {
                                    "contact_name": new_contact_name,
                                    "contact_role": new_contact_role,
                                    "email": new_contact_email or None,
                                    "phone": new_contact_phone or None,
                                    "is_primary": new_contact_primary,
                                    "notes": new_contact_notes or None,
                                }
                                success, contact_id, error = add_contact(client_id, contact_data, user_role)
                                if success:
                                    st.success(f"Contact '{new_contact_name}' added!")
                                    safe_rerun()
                                else:
                                    st.error(f"Failed to add contact: {error}")
