"""Import/Export page — CSV import, export, QR code generation."""

import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from config.constants import (
    ASSET_TYPES, BRANDS, STORAGE_TYPES, OS_OPTIONS,
    VALID_INITIAL_STATUSES, STATUS_DISPLAY_NAMES,
)
from config.permissions import check_page_access, render_access_denied
from services.audit_service import log_activity_event
from components.empty_states import render_empty_state
from components.feedback import render_error_state
from core.data import safe_rerun, clear_cache, get_table, paginate_dataframe, render_page_navigation
from core.errors import log_error
from views.context import AppContext

try:
    from database.db import get_all_assets as mysql_get_assets
except ImportError:
    mysql_get_assets = None

def render(ctx: AppContext) -> None:
    """Render this page."""
    # Route-level access control (defense in depth)
    if not check_page_access("Import/Export", st.session_state.user_role):
        render_access_denied(required_roles=["admin", "operations"])
        st.stop()

    # Import excel utilities
    from database.excel_utils import (
        export_assets_to_excel,
        generate_import_template,
        validate_import_data,
        import_assets_from_dataframe,
        detect_columns,
        auto_suggest_mapping,
        apply_column_mapping,
        EXCEL_COLUMNS
    )
    from database.db import get_import_profiles, save_import_profile, delete_import_profile

    # Import QR code utilities
    from database.qr_utils import (
        generate_asset_qr,
        generate_asset_label_image,
        generate_bulk_qr_pdf
    )

    st.markdown('<p class="main-header">Import / Export Assets</p>', unsafe_allow_html=True)

    # Create three main sections
    export_section, import_section, qr_section = st.tabs(["📤 Export Data", "📥 Import Data", "📱 QR Codes"])

    # ========== EXPORT SECTION ==========
    with export_section:
        # Section header (matching other pages)
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
            <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Export Assets to File</span>
        </div>
        """, unsafe_allow_html=True)

        st.info("Download all assets data as Excel (.xlsx) or CSV file for reporting, backup, or offline analysis.")

        # Fetch current assets data
        if ctx.data_source == "mysql" and ctx.mysql_available:
            export_assets = mysql_get_assets()
        else:
            export_assets = []

        # Convert to DataFrame
        export_df = pd.DataFrame(export_assets) if export_assets is not None else pd.DataFrame()

        if len(export_df) > 0:
            # Show summary
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Assets", len(export_df))
            with col2:
                st.metric("Columns", len(export_df.columns))
            with col3:
                st.metric("File Formats", "2", help="Excel and CSV")

            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

            # Download Format sub-header
            st.markdown("""
            <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                Download Format
            </div>
            """, unsafe_allow_html=True)

            export_col1, export_col2, export_col3 = st.columns([1, 1, 2])

            with export_col1:
                # Excel Export
                try:
                    excel_buffer = export_assets_to_excel(export_df)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                    st.download_button(
                        label="📥 Download Excel",
                        data=excel_buffer.getvalue(),
                        file_name=f"assets_export_{timestamp}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Failed to generate Excel: {str(e)}")

            with export_col2:
                # CSV Export
                csv_data = export_df.to_csv(index=False).encode('utf-8')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_data,
                    file_name=f"assets_export_{timestamp}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            # Preview section
            st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
            with st.expander("👁 Preview Export Data", expanded=False):
                # Select columns to show
                display_cols = ['Serial Number', 'Asset Type', 'Brand', 'Model', 'Current Status', 'Current Location']
                available_cols = [c for c in display_cols if c in export_df.columns]
                export_preview_source = export_df[available_cols] if available_cols else export_df.iloc[:, :6]

                # Paginated preview with page navigation
                paginated_export = paginate_dataframe(export_preview_source, "export_preview_table", show_controls=True)
                st.dataframe(paginated_export, use_container_width=True, height=400)
                render_page_navigation("export_preview_table")
        else:
            st.warning("No assets found in the database to export.")

    # ========== IMPORT SECTION ==========
    with import_section:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
            <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Import Assets from Excel</span>
        </div>
        """, unsafe_allow_html=True)

        st.info("Upload **any Excel file** — map your columns to app fields, save the mapping as a profile, and reuse it next time.")

        # Download template button
        st.markdown("""
        <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
            Download Template (Optional)
        </div>
        """, unsafe_allow_html=True)
        st.caption("Use our template for the easiest import, or upload your own Excel file below.")
        tmpl_col1, _ = st.columns([1, 3])
        with tmpl_col1:
            try:
                template_buffer = generate_import_template()
                st.download_button(
                    label="📋 Download Template",
                    data=template_buffer.getvalue(),
                    file_name="asset_import_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Failed to generate template: {str(e)}")

        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

        # ── Initialize session state ──────────────────────────────────────
        for key, default in [
            ("import_raw_df", None),
            ("import_mapping", {}),
            ("import_mapping_done", False),
            ("import_validated", False),
            ("import_df", None),
            ("import_errors", []),
            ("import_warnings", []),
        ]:
            if key not in st.session_state:
                st.session_state[key] = default

        # ── STEP 1: Upload ────────────────────────────────────────────────
        st.markdown("""
        <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
            Step 1: Upload Your Excel File
        </div>
        """, unsafe_allow_html=True)
        st.caption("Upload your own Excel file in any format — vendor invoice, procurement sheet, old IT register, etc.")

        uploaded_file = st.file_uploader(
            "Choose Excel file (.xlsx)",
            type=["xlsx"],
            help="Any Excel file up to 10MB.",
            key="import_file_uploader"
        )

        if uploaded_file is not None:
            if uploaded_file.size > 10 * 1024 * 1024:
                st.error("File too large. Maximum size is 10MB.")
            else:
                try:
                    raw_df = pd.read_excel(uploaded_file, sheet_name=0)
                    # Store raw df; reset downstream state if file changed
                    if st.session_state.import_raw_df is None or list(raw_df.columns) != list(
                        st.session_state.import_raw_df.columns if st.session_state.import_raw_df is not None else []
                    ):
                        st.session_state.import_raw_df = raw_df
                        st.session_state.import_mapping = {}
                        st.session_state.import_mapping_done = False
                        st.session_state.import_validated = False
                        st.session_state.import_df = None
                        st.session_state.import_errors = []
                        st.session_state.import_warnings = []

                    detected = detect_columns(raw_df)
                    st.success(f"Detected **{len(detected)} columns** and **{len(raw_df)} rows** in your file.")

                    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

                    # ── STEP 2: Map Columns ───────────────────────────────
                    st.markdown("""
                    <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                        Step 2: Map Your Columns
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption("Match each column in your file to the corresponding app field. Columns set to '-- Skip --' will be ignored.")

                    # Build app field options
                    app_fields = ["-- Skip --"] + [col["name"] for col in EXCEL_COLUMNS]
                    required_fields = {"Serial Number"}

                    # Load saved profile
                    profiles = get_import_profiles()
                    profile_options = ["-- New Mapping --"] + [p["profile_name"] for p in profiles]
                    profile_map = {p["profile_name"]: p for p in profiles}

                    prof_col1, prof_col2 = st.columns([3, 1])
                    with prof_col1:
                        selected_profile = st.selectbox(
                            "Load Saved Profile",
                            options=profile_options,
                            key="import_profile_select"
                        )
                    with prof_col2:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        if selected_profile != "-- New Mapping --":
                            if st.button("🗑 Delete Profile", key="delete_profile_btn", use_container_width=True):
                                pid = profile_map[selected_profile]["id"]
                                if delete_import_profile(pid):
                                    st.success(f"Profile '{selected_profile}' deleted.")
                                    st.rerun()
                                else:
                                    st.error("Failed to delete profile.")

                    # Determine initial mapping
                    if selected_profile != "-- New Mapping --" and selected_profile in profile_map:
                        saved_mapping = profile_map[selected_profile]["mapping"]
                    else:
                        saved_mapping = auto_suggest_mapping(detected)

                    # Render mapping rows
                    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                    header_c1, header_c2 = st.columns([2, 2])
                    with header_c1:
                        st.markdown("**Your Column**")
                    with header_c2:
                        st.markdown("**App Field**")

                    current_mapping = {}
                    for their_col in detected:
                        col1, col2 = st.columns([2, 2])
                        with col1:
                            is_required = saved_mapping.get(their_col) in required_fields
                            label = f"{'⭐ ' if is_required else ''}{their_col}"
                            st.markdown(
                                f"<div style='padding: 8px 0; font-size: 13px; color: #374151;'>{label}</div>",
                                unsafe_allow_html=True
                            )
                        with col2:
                            default_field = saved_mapping.get(their_col, "-- Skip --")
                            default_idx = app_fields.index(default_field) if default_field in app_fields else 0
                            chosen = st.selectbox(
                                label=their_col,
                                options=app_fields,
                                index=default_idx,
                                key=f"map_{their_col}",
                                label_visibility="collapsed"
                            )
                            current_mapping[their_col] = chosen

                    # Save profile expander
                    with st.expander("💾 Save as Profile"):
                        save_col1, save_col2 = st.columns([3, 1])
                        with save_col1:
                            new_profile_name = st.text_input(
                                "Profile name",
                                placeholder="e.g. Vendor Dell Format",
                                key="new_profile_name"
                            )
                        with save_col2:
                            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                            if st.button("Save", key="save_profile_btn", use_container_width=True):
                                if new_profile_name.strip():
                                    ok, err = save_import_profile(
                                        new_profile_name.strip(),
                                        current_mapping,
                                        st.session_state.get("username", "")
                                    )
                                    if ok:
                                        st.success(f"Profile '{new_profile_name}' saved!")
                                    else:
                                        st.error(f"Save failed: {err}")
                                else:
                                    st.warning("Enter a profile name first.")

                    # Confirm mapping button
                    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                    if st.button("✅ Confirm Mapping", key="confirm_mapping_btn", type="primary", use_container_width=True):
                        if current_mapping.get("-- Skip --") == "Serial Number" or \
                           "Serial Number" not in current_mapping.values():
                            st.warning("⭐ Serial Number must be mapped to at least one column to proceed.")
                        else:
                            st.session_state.import_mapping = current_mapping
                            st.session_state.import_mapping_done = True
                            st.session_state.import_validated = False
                            st.session_state.import_df = None
                            st.rerun()

                    # ── STEP 3: Preview Mapped Data ───────────────────────
                    if st.session_state.import_mapping_done:
                        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
                        st.markdown("""
                        <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                            Step 3: Preview Mapped Data
                        </div>
                        """, unsafe_allow_html=True)

                        mapped_df = apply_column_mapping(
                            st.session_state.import_raw_df,
                            st.session_state.import_mapping
                        )
                        mapped_count = sum(1 for v in st.session_state.import_mapping.values() if v != "-- Skip --")
                        skipped_count = sum(1 for v in st.session_state.import_mapping.values() if v == "-- Skip --")
                        st.caption(f"{mapped_count} columns mapped, {skipped_count} skipped — {len(mapped_df)} rows ready.")

                        preview_cols = ["Serial Number", "Asset Type", "Brand", "Model", "Current Status"]
                        available_preview = [c for c in preview_cols if c in mapped_df.columns]
                        st.dataframe(
                            mapped_df[available_preview].head(5) if available_preview else mapped_df.head(5),
                            use_container_width=True
                        )

                        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

                        # ── STEP 4: Validate ──────────────────────────────
                        st.markdown("""
                        <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                            Step 4: Validate Data
                        </div>
                        """, unsafe_allow_html=True)
                        st.caption("Check your data for errors before importing.")

                        if st.button("🔍 Validate Data", key="validate_btn", use_container_width=True, type="primary"):
                            with st.spinner("Validating..."):
                                is_valid, errors, warnings, valid_df = validate_import_data(mapped_df)
                                st.session_state.import_errors = errors
                                st.session_state.import_warnings = warnings
                                st.session_state.import_df = valid_df
                                st.session_state.import_validated = True
                                st.rerun()

                        if st.session_state.import_validated:
                            errors = st.session_state.import_errors
                            warnings = st.session_state.import_warnings
                            valid_df = st.session_state.import_df
                            valid_count = len(valid_df) if valid_df is not None else 0

                            v_col1, v_col2, v_col3 = st.columns(3)
                            with v_col1:
                                st.metric("✅ Valid Records", valid_count)
                            with v_col2:
                                st.metric("❌ Errors", len(errors))
                            with v_col3:
                                st.metric("⚠️ Warnings", len(warnings))

                            if errors:
                                with st.expander("❌ Errors (must fix)", expanded=True):
                                    for err in errors[:20]:
                                        row_info = f"Row {err['row']}" if err.get("row") else ""
                                        field_info = f"[{err['field']}]" if err.get("field") else ""
                                        st.markdown(f"• {row_info} {field_info}: {err.get('message', 'Unknown error')}")
                                    if len(errors) > 20:
                                        st.caption(f"...and {len(errors) - 20} more errors")

                            if warnings:
                                with st.expander("⚠️ Warnings", expanded=False):
                                    for warn in warnings[:20]:
                                        row_info = f"Row {warn['row']}" if warn.get("row") else ""
                                        field_info = f"[{warn['field']}]" if warn.get("field") else ""
                                        st.markdown(f"• {row_info} {field_info}: {warn.get('message', 'Warning')}")
                                    if len(warnings) > 20:
                                        st.caption(f"...and {len(warnings) - 20} more warnings")

                            # ── STEP 5: Import ────────────────────────────
                            st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
                            st.markdown("""
                            <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                                Step 5: Import Assets
                            </div>
                            """, unsafe_allow_html=True)

                            if valid_count > 0:
                                if st.button(f"📥 Import {valid_count} Assets", key="import_btn", use_container_width=True, type="primary"):
                                    with st.spinner(f"Importing {valid_count} assets..."):
                                        result = import_assets_from_dataframe(valid_df)

                                    if result["success"] > 0:
                                        st.success(f"✅ Successfully imported {result['success']} assets!")
                                        log_activity_event(
                                            action_type="BULK_IMPORT",
                                            category="data_management",
                                            user_role=st.session_state.user_role,
                                            description=f"Imported {result['success']} assets from Excel (column mapping)",
                                            success=True
                                        )
                                        st.session_state.data_stale = True

                                    if result["failed"] > 0:
                                        st.warning(f"⚠️ {result['failed']} assets failed to import.")
                                        if result.get("errors"):
                                            with st.expander("View import errors"):
                                                for err in result["errors"][:10]:
                                                    st.write(f"• {err.get('serial', 'Unknown')}: {err.get('error', 'Unknown error')}")

                                    # Reset state
                                    for key in ["import_raw_df", "import_mapping", "import_mapping_done",
                                                "import_validated", "import_df", "import_errors", "import_warnings"]:
                                        st.session_state[key] = None if key in ("import_raw_df", "import_df") else \
                                                                 {} if key == "import_mapping" else \
                                                                 [] if key in ("import_errors", "import_warnings") else False
                            else:
                                st.warning("No valid records to import. Fix errors above, adjust mapping, and re-validate.")

                            if st.button("🔄 Reset & Start Over", key="reset_btn", use_container_width=True):
                                for key in ["import_raw_df", "import_mapping", "import_mapping_done",
                                            "import_validated", "import_df", "import_errors", "import_warnings"]:
                                    st.session_state[key] = None if key in ("import_raw_df", "import_df") else \
                                                             {} if key == "import_mapping" else \
                                                             [] if key in ("import_errors", "import_warnings") else False
                                st.rerun()

                except Exception as e:
                    st.error(f"Failed to read file: {str(e)}")
                    st.info("Please make sure you're uploading a valid Excel (.xlsx) file.")

    # ========== QR CODES SECTION ==========
    with qr_section:
        # Section header (matching other pages)
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #3b82f6;">
            <div style="width: 4px; height: 20px; background: #3b82f6; border-radius: 2px;"></div>
            <span style="font-size: 16px; font-weight: 600; color: #1f2937;">Generate QR Codes</span>
        </div>
        """, unsafe_allow_html=True)

        st.info("Generate QR codes for assets. QR codes contain the serial number for easy scanning and identification.")

        # Fetch assets for QR generation
        if ctx.data_source == "mysql" and ctx.mysql_available:
            qr_assets = mysql_get_assets()
        else:
            qr_assets = []

        qr_df = pd.DataFrame(qr_assets) if qr_assets is not None else pd.DataFrame()

        if len(qr_df) > 0:
            # ===== SINGLE ASSET QR =====
            st.markdown("""
            <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                Single Asset QR Code
            </div>
            """, unsafe_allow_html=True)

            # Create asset options for dropdown
            asset_options = []
            for _, row in qr_df.iterrows():
                serial = row.get('Serial Number', '')
                asset_type = row.get('Asset Type', '')
                brand = row.get('Brand', '')
                model = row.get('Model', '')
                label = f"{serial} - {asset_type} - {brand} {model}"
                asset_options.append(label)

            selected_asset_label = st.selectbox(
                "Select Asset",
                options=asset_options,
                key="qr_asset_select"
            )

            if selected_asset_label:
                # Get the selected asset data
                selected_idx = asset_options.index(selected_asset_label)
                selected_asset = qr_df.iloc[selected_idx].to_dict()

                serial = selected_asset.get('Serial Number', '')
                asset_type = selected_asset.get('Asset Type', '')
                brand = selected_asset.get('Brand', '')
                model = selected_asset.get('Model', '')
                status = selected_asset.get('Current Status', '')

                # Display QR code and info side by side
                qr_col1, qr_col2 = st.columns([1, 2])

                with qr_col1:
                    # Generate and display QR code
                    qr_buffer = generate_asset_qr(serial, size=200)
                    st.image(qr_buffer, caption="Scan to get Serial Number", width=200)

                with qr_col2:
                    st.markdown(f"""
                    <div style="padding: 16px; background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb;">
                        <div style="margin-bottom: 12px;">
                            <span style="color: #6b7280; font-size: 12px;">SERIAL NUMBER</span><br>
                            <span style="font-size: 18px; font-weight: 700; color: #111827;">{serial}</span>
                        </div>
                        <div style="margin-bottom: 8px;">
                            <span style="color: #6b7280; font-size: 12px;">TYPE</span><br>
                            <span style="font-size: 14px; color: #374151;">{asset_type}</span>
                        </div>
                        <div style="margin-bottom: 8px;">
                            <span style="color: #6b7280; font-size: 12px;">BRAND / MODEL</span><br>
                            <span style="font-size: 14px; color: #374151;">{brand} {model}</span>
                        </div>
                        <div>
                            <span style="color: #6b7280; font-size: 12px;">STATUS</span><br>
                            <span style="font-size: 14px; color: #374151;">{status}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # Download buttons
                st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
                dl_col1, dl_col2, dl_col3 = st.columns([1, 1, 2])

                with dl_col1:
                    qr_png = generate_asset_qr(serial, size=300)
                    st.download_button(
                        label="📥 Download QR (PNG)",
                        data=qr_png.getvalue(),
                        file_name=f"qr_{serial}.png",
                        mime="image/png",
                        use_container_width=True
                    )

                with dl_col2:
                    qr_label = generate_asset_label_image(selected_asset)
                    st.download_button(
                        label="📥 Download with Label",
                        data=qr_label.getvalue(),
                        file_name=f"qr_label_{serial}.png",
                        mime="image/png",
                        use_container_width=True
                    )

            # ===== BULK QR GENERATION =====
            st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
            st.markdown("""
            <div style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;">
                Bulk QR Labels (PDF)
            </div>
            """, unsafe_allow_html=True)
            st.caption("Generate a printable PDF with QR code labels for multiple assets.")

            # Filters
            filter_col1, filter_col2 = st.columns(2)

            with filter_col1:
                status_options = ["All"] + sorted(qr_df['Current Status'].dropna().unique().tolist())
                selected_status = st.selectbox("Filter by Status", options=status_options, key="qr_status_filter")

            with filter_col2:
                brand_options = ["All"] + sorted(qr_df['Brand'].dropna().unique().tolist())
                selected_brand = st.selectbox("Filter by Brand", options=brand_options, key="qr_brand_filter")

            # Apply filters
            filtered_qr_df = qr_df.copy()
            if selected_status != "All":
                filtered_qr_df = filtered_qr_df[filtered_qr_df['Current Status'] == selected_status]
            if selected_brand != "All":
                filtered_qr_df = filtered_qr_df[filtered_qr_df['Brand'] == selected_brand]

            # Show count
            st.markdown(f"**{len(filtered_qr_df)}** assets match the filters")

            # Select all checkbox
            select_all = st.checkbox(f"Select All ({len(filtered_qr_df)} assets)", key="qr_select_all")

            # Multi-select for assets
            if select_all:
                default_selection = filtered_qr_df['Serial Number'].tolist()
            else:
                default_selection = []

            # Create options with more info
            bulk_options = []
            for _, row in filtered_qr_df.iterrows():
                serial = row.get('Serial Number', '')
                asset_type = row.get('Asset Type', '')
                brand = row.get('Brand', '')
                bulk_options.append(f"{serial} - {asset_type} - {brand}")

            selected_bulk = st.multiselect(
                "Select Assets for PDF",
                options=bulk_options,
                default=[f"{s} - {filtered_qr_df[filtered_qr_df['Serial Number']==s].iloc[0]['Asset Type']} - {filtered_qr_df[filtered_qr_df['Serial Number']==s].iloc[0]['Brand']}" for s in default_selection] if select_all else [],
                key="qr_bulk_select"
            )

            # Labels per row option
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            labels_per_row = st.selectbox("Labels per Row", options=[2, 3, 4], index=1, key="qr_labels_per_row")

            # Generate PDF button
            if selected_bulk:
                # Get selected asset data
                selected_serials = [opt.split(" - ")[0] for opt in selected_bulk]
                selected_assets_data = filtered_qr_df[filtered_qr_df['Serial Number'].isin(selected_serials)].to_dict('records')

                if st.button(f"📄 Generate PDF ({len(selected_bulk)} labels)", type="primary", use_container_width=True):
                    with st.spinner("Generating PDF..."):
                        pdf_buffer = generate_bulk_qr_pdf(selected_assets_data, labels_per_row=labels_per_row)
                        st.session_state.qr_pdf_buffer = pdf_buffer
                        st.session_state.qr_pdf_count = len(selected_bulk)
                        st.success(f"PDF generated with {len(selected_bulk)} QR labels!")

                # Show download button if PDF was generated
                if 'qr_pdf_buffer' in st.session_state and st.session_state.qr_pdf_buffer:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                    st.download_button(
                        label=f"📥 Download PDF ({st.session_state.qr_pdf_count} labels)",
                        data=st.session_state.qr_pdf_buffer.getvalue(),
                        file_name=f"qr_labels_{timestamp}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            else:
                st.info("Select assets above to generate PDF labels.")

        else:
            st.warning("No assets found in the database.")

    # SETTINGS PAGE

