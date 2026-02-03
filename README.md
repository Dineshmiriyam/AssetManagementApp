# Asset Lifecycle Management System

A web application for managing laptop and asset rentals, connected to Airtable.

## Features

- **Dashboard**: Overview of all assets with charts and statistics
- **Assets**: View, filter, search, and export asset data
- **Add Asset**: Form to add new assets to inventory
- **Issues**: Log and track problems with assets
- **Clients**: Manage client information
- **Settings**: Configure Airtable connection

## Quick Start

### Step 1: Configure Airtable API Key

1. Go to [airtable.com/create/tokens](https://airtable.com/create/tokens)
2. Click "Create new token"
3. Name it: "Asset Management App"
4. Select scopes:
   - `data.records:read`
   - `data.records:write`
5. Select access: Your "Asset Lifecycle Management" base
6. Click "Create token" and copy it

### Step 2: Add API Key to App

1. Open the `.env` file in this folder
2. Replace `your_api_key_here` with your actual API key:
   ```
   AIRTABLE_API_KEY=patXXXXXXXXXXXXXX.XXXXXXXXXXXXXXXXXXXXXXXX
   AIRTABLE_BASE_ID=appfGt6T3RSXVrzPU
   ```
3. Save the file

### Step 3: Run the App

**Option A: Double-click**
- Double-click `run_app.bat`

**Option B: Command line**
```bash
cd C:\Users\LENOVO\Documents\AssetManagementApp
python -m pip install -r requirements.txt
streamlit run app.py
```

### Step 4: Open in Browser

The app will automatically open at: http://localhost:8501

## File Structure

```
AssetManagementApp/
├── app.py              # Main application code
├── requirements.txt    # Python dependencies
├── .env               # Configuration (API keys)
├── run_app.bat        # Easy launcher for Windows
└── README.md          # This file
```

## Troubleshooting

### "API Key not configured"
- Make sure you've added your Airtable API key to the `.env` file
- Restart the app after changing the `.env` file

### "Connection failed"
- Check that your API key has the correct permissions
- Make sure the Base ID matches your Airtable base

### App won't start
- Make sure Python is installed: `python --version`
- Install dependencies: `pip install -r requirements.txt`

## Support

For issues with the app, check the Settings page for connection diagnostics.
