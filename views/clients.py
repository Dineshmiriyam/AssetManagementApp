"""Clients page — client directory."""

import pandas as pd
import streamlit as st

from components.empty_states import render_empty_state
from components.feedback import render_error_state
from core.data import safe_rerun, clear_cache, get_table, paginate_dataframe, render_page_navigation
from core.errors import log_error
from views.context import AppContext

def render(ctx: AppContext) -> None:
    """Render this page."""
    st.markdown('<p class="main-header">Clients</p>', unsafe_allow_html=True)

    if not ctx.api:
        st.warning("Please configure your Airtable API key in Settings first.")
    elif st.session_state.get('data_load_error'):
        render_error_state(
            error_message=st.session_state.data_load_error or "Unable to load clients data. Please try again.",
            error_type="database",
            show_retry=True,
            retry_key="retry_data_load"
        )
    else:
        tab1, tab2 = st.tabs(["View Clients", "Add Client"])

        with tab1:
            if not ctx.clients_df.empty:
                # Search and filter row
                ccol1, ccol2, ccol3 = st.columns([2, 1, 0.5])

                with ccol1:
                    client_search = st.text_input("🔍 Search Client Name", key="client_search", placeholder="Type to search...")

                with ccol2:
                    client_type_list = sorted(list(ctx.clients_df["Client Type"].dropna().unique())) if "Client Type" in ctx.clients_df.columns else []
                    client_type_filter = st.selectbox("Type", ["All"] + client_type_list, key="client_type_filter")

                with ccol3:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("Clear", key="clear_client_filters", width="stretch"):
                        for key in ["client_search", "client_type_filter"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        safe_rerun()

                # Apply filters
                filtered_clients = ctx.clients_df.copy()

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
                    with st.expander(f"**{client.get('Client Name', 'Unknown')}** - {client.get('Client Type', 'N/A')}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Contact:** {client.get('Contact Person', 'N/A')}")
                            st.write(f"**Email:** {client.get('Email', 'N/A')}")
                            st.write(f"**Phone:** {client.get('Phone', 'N/A')}")
                        with col2:
                            st.write(f"**Type:** {client.get('Client Type', 'N/A')}")
                            st.write(f"**Active:** {'Yes' if client.get('Is Active', False) else 'No'}")

                            # Count assets with this client
                            if not ctx.assets_df.empty and "Current Location" in ctx.assets_df.columns:
                                asset_count = len(ctx.assets_df[ctx.assets_df["Current Location"] == client.get("Client Name", "")])
                                st.write(f"**Assets:** {asset_count}")
                render_page_navigation("clients_table")
            else:
                render_empty_state("no_clients", show_action=False)
                # Add client button inline
                if st.button("Add Your First Client", key="add_first_client_inline"):
                    st.session_state.show_add_client = True
                    safe_rerun()

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

                submitted = st.form_submit_button("Add Client", type="primary")

                if submitted:
                    if not client_name:
                        st.error("Client Name is required!")
                    else:
                        record = {
                            "Client Name": client_name,
                            "Client Type": client_type,
                            "Is Active": is_active
                        }

                        if contact_person: record["Contact Person"] = contact_person
                        if email: record["Email"] = email
                        if phone: record["Phone"] = phone
                        if address: record["Address"] = address

                        try:
                            table = get_table("clients")
                            table.create(record)
                            clear_cache(["clients"])  # Targeted invalidation
                            st.success(f"Client {client_name} added successfully!")
                        except Exception as e:
                            error_id = log_error(e, "create_client_airtable", st.session_state.get('user_role'))
                            st.error(f"Unable to add client. Please try again. (Ref: {error_id})")

    # REPORTS PAGE

