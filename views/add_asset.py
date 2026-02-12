"""Add Asset page — single asset creation form."""

from datetime import datetime

import streamlit as st

from config.constants import (
    ASSET_TYPES, BRANDS, STORAGE_TYPES, OS_OPTIONS,
    VALID_INITIAL_STATUSES, STATUS_DISPLAY_NAMES,
)
from config.permissions import check_page_access, render_access_denied, validate_action
from services.audit_service import log_activity_event
from core.data import safe_rerun, clear_cache, get_table
from core.errors import log_error
from views.context import AppContext

def render(ctx: AppContext) -> None:
    """Render this page."""
    # Route-level access control (defense in depth)
    if not check_page_access("Add Asset", st.session_state.user_role):
        render_access_denied(required_roles=["admin", "operations"])
        st.stop()  # Prevent further page rendering

    st.markdown('<p class="main-header">Add New Asset</p>', unsafe_allow_html=True)

    if not ctx.api:
        st.warning("Please configure your Airtable API key in Settings first.")
    else:
        with st.form("add_asset_form"):
            # Section: Asset Information
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
                <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Asset Information</span>
            </div>
            """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)

            with col1:
                serial_number = st.text_input("Serial Number *", placeholder="e.g., PF1XLNM6")
                asset_type = st.selectbox("Asset Type *", ASSET_TYPES)
                brand = st.selectbox("Brand *", BRANDS)
                model = st.text_input("Model", placeholder="e.g., T495, MacBook Air")
                specs = st.text_input("Specs", placeholder="e.g., 16GB, 256GB SSD, i5")

            with col2:
                touch_screen = st.checkbox("Touch Screen")
                processor = st.text_input("Processor", placeholder="e.g., AMD Ryzen 5 Pro")
                ram = st.number_input("RAM (GB)", min_value=0, max_value=128, value=16)
                storage_type = st.selectbox("Storage Type", STORAGE_TYPES)
                storage_gb = st.number_input("Storage (GB)", min_value=0, max_value=4096, value=256)

            # Section: Software & License
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin: 24px 0 16px 0; padding-bottom: 8px; border-bottom: 2px solid #10b981;">
                <div style="width: 4px; height: 20px; background: #10b981; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Software & License</span>
            </div>
            """, unsafe_allow_html=True)
            col1, col2 = st.columns(2)

            with col1:
                os_installed = st.selectbox("OS Installed", [""] + OS_OPTIONS)
                office_key = st.text_input("Office License Key", placeholder="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")

            with col2:
                password = st.text_input("Device Password")
                current_status = st.selectbox("Current Status *", VALID_INITIAL_STATUSES, index=0,
                                              help="New assets can only be added as 'In Stock' or 'With Client'")

            # Section: Location & Purchase
            st.markdown("""
            <div style="display: flex; align-items: center; gap: 8px; margin: 24px 0 16px 0; padding-bottom: 8px; border-bottom: 2px solid #f59e0b;">
                <div style="width: 4px; height: 20px; background: #f59e0b; border-radius: 2px;"></div>
                <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Location & Purchase</span>
            </div>
            """, unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)

            with col1:
                current_location = st.text_input("Current Location", value="Office")

            with col2:
                purchase_date = st.date_input("Purchase Date", value=None)

            with col3:
                purchase_price = st.number_input("Purchase Price (₹)", min_value=0, value=0)

            # Additional Notes
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            notes = st.text_area("Notes", placeholder="Any additional information...")

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Add Asset", type="primary")

            if submitted:
                # Server-side RBAC validation (defense in depth)
                validation_result = validate_action("create_asset", st.session_state.user_role)
                if not validation_result.success:
                    st.error(validation_result.message)
                    log_activity_event(
                        action_type="ACCESS_DENIED",
                        category="security",
                        user_role=st.session_state.user_role,
                        description="Unauthorized asset creation attempt",
                        success=False
                    )
                elif not serial_number:
                    st.error("Serial Number is required.")
                else:
                    record = {
                        "Serial Number": serial_number,
                        "Asset Type": asset_type,
                        "Brand": brand,
                        "Current Status": current_status
                    }

                    if model: record["Model"] = model
                    if specs: record["Specs"] = specs
                    if touch_screen: record["Touch Screen"] = touch_screen
                    if processor: record["Processor"] = processor
                    if ram: record["RAM (GB)"] = ram
                    if storage_type: record["Storage Type"] = storage_type
                    if storage_gb: record["Storage (GB)"] = storage_gb
                    if os_installed: record["OS Installed"] = os_installed
                    if office_key: record["Office License Key"] = office_key
                    if password: record["Password"] = password
                    if current_location: record["Current Location"] = current_location
                    if purchase_date: record["Purchase Date"] = purchase_date.isoformat()
                    if purchase_price: record["Purchase Price"] = purchase_price
                    if notes: record["Notes"] = notes

                    try:
                        table = get_table("assets")
                        table.create(record)
                        clear_cache(["assets"])  # Targeted invalidation
                        # Log successful creation
                        log_activity_event(
                            action_type="ASSET_CREATED",
                            category="asset",
                            user_role=st.session_state.user_role,
                            description=f"Asset created: {serial_number}",
                            serial_number=serial_number,
                            success=True
                        )
                        st.success(f"Asset {serial_number} added successfully.")
                        st.balloons()
                    except Exception as e:
                        error_id = log_error(e, "create_asset_airtable", st.session_state.get('user_role'))
                        st.error(f"Unable to add asset. Please try again. (Ref: {error_id})")

    # ASSIGNMENTS PAGE

