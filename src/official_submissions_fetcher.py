import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import os

# 1. Setup paths relative to your project structure
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Link to your specific Google Cloud credentials
CONFIG_PATH = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')
# Destination for official form data
OUTPUT_PATH = os.path.join(BASE_DIR, 'data', 'raw', 'official_submissions_raw.csv')


def fetch_official_submissions():
    """
    Connects to the Google Sheet containing official Tally submissions
    and synchronizes the data to a local CSV file.
    """
    # Define API scopes
    scope = ["https://www.googleapis.com/auth/spreadsheets.readonly", "https://www.googleapis.com/auth/drive.readonly"]

    try:
        # Authenticate with the Service Account 'Robot'
        creds = Credentials.from_service_account_file(CONFIG_PATH, scopes=scope)
        client = gspread.authorize(creds)
        client.set_timeout(30)

        # Open the specific spreadsheet synchronized with Tally
        # Ensure this name matches the title in your browser exactly
        sheet_id = os.environ.get('GOOGLE_SHEETS_ID')
        spreadsheet = client.open_by_key(sheet_id) if sheet_id else client.open(os.environ.get('GOOGLE_SHEETS_NAME', 'Regulatory_Monitoring_Log'))
        sheet = spreadsheet.sheet1

        # Retrieve all fresh incoming data from Google Sheets
        records = sheet.get_all_records()
        new_df = pd.DataFrame(records)

        # Initialize the tracking path extensions if they don't exist yet
        path_columns = ['Local_File_Path', 'Local_RIA_File_Path']
        for col in path_columns:
            if col not in new_df.columns:
                new_df[col] = None

        # Check if an older historical file already exists on disk
        if os.path.exists(OUTPUT_PATH):
            print(f"[*] Found existing historical submissions log. Merging path metadata...")
            try:
                existing_df = pd.read_csv(OUTPUT_PATH)

                # Define any internal system columns that should be ignored during matching
                system_columns_to_ignore = path_columns + ['dt', 'Internal_Timestamp']

                # Identify the core data columns coming natively from the form (excluding internal path and system variables)
                match_columns = [col for col in existing_df.columns if
                                 col not in system_columns_to_ignore and col in new_df.columns]

                # Force all matching columns to string type and handle NaNs correctly
                for col in match_columns:
                    new_df[col] = new_df[col].fillna('').astype(str).str.strip()
                    existing_df[col] = existing_df[col].fillna('').astype(str).str.strip()

                # Isolate only the key identifier and the protected columns, removing duplicates
                existing_paths = existing_df.drop_duplicates(subset=match_columns)

                # Perform an in-memory Left Merge to append tracking metadata onto identical records
                merged_df = pd.merge(
                    new_df,
                    existing_paths[match_columns + path_columns],
                    on=match_columns,
                    how='left',
                    suffixes=('_new', '_old')
                )

                # Resolve the tracking columns by favoring existing historical paths over empty fresh states
                for col in path_columns:
                    new_col_name = f"{col}_new"
                    old_col_name = f"{col}_old"

                    if old_col_name in merged_df.columns and new_col_name in merged_df.columns:
                        merged_df[col] = merged_df[old_col_name].combine_first(merged_df[new_col_name])
                        merged_df.drop(columns=[new_col_name, old_col_name], inplace=True)

                # Reassign the fully synchronized data back to our primary tracking dataframe
                df = merged_df[new_df.columns]

            except Exception as merge_error:
                print(f"[!] Metadata cross-merge failed ({merge_error}). Proceeding with fresh fetch baseline.")
                df = new_df
        else:
            print("[i] No historical log detected. Creating fresh tracking dataset.")
            df = new_df

        # Ensure the target raw storage directory is physically provisioned
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

        # Overwrite the spreadsheet array securely using UTF-8-SIG encoding for Hebrew text support
        df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')

        print(f"[*] Success: {len(df)} official submissions synchronized to {OUTPUT_PATH}")
        return df

    except Exception as e:
        print(f"[!] Synchronization Error: {e}")
        raise RuntimeError("Google Sheets synchronization failed; check credentials and sheet access") from e


if __name__ == "__main__":
    fetch_official_submissions()
