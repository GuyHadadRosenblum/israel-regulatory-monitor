import os
import time
import re
import pandas as pd
from datetime import datetime
from docx import Document
from pypdf import PdfReader
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION & PATHS ---
# Base paths are resolved dynamically so they work on any computer
BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

RAW_DIR = os.path.join(BASE_DATA_DIR, 'raw')
PROCESSED_DIR = os.path.join(BASE_DATA_DIR, 'processed')
DOWNLOADS_BASE = os.path.join(BASE_DATA_DIR, 'downloads')
RIA_DOWNLOADS_BASE = os.path.join(BASE_DATA_DIR, 'downloaded_RIA')

PORTAL_CSV = os.path.join(RAW_DIR, 'legislation_website_data.csv')
OFFICIAL_SUBMISSIONS_CSV = os.path.join(RAW_DIR, 'official_submissions_raw.csv')
MERGED_XLSX = os.path.join(PROCESSED_DIR, 'unified_legislation_log.xlsx')

SIMILARITY_THRESHOLD = 55.0

# --- SOURCE COLUMN DEFINITIONS ---
P_OFFICE, P_DATE, P_FILE, P_URL, P_TITLE = 'office', 'publish_date', 'main_file_url', 'url', 'title'
T_DATE, T_OFFICE, T_TITLE, T_FILE = 'Submitted at', 'אנא ציינו את שם המשרד/התאגיד הציבורי', 'ציינו את השם הרשמי של התקנות/החוקים ששונו', 'אנא העלו את קובץ התקנות ששונו כאן'


# --- KEYWORD-BASED TRANSLATION MAP ---
SMART_TRANSLATION_MAP = {
    'תקנותחוקים נוספים': 'Additional_Related_Legislation',
    'השפעה משקית': 'Significant_Economic_Impact',
    'מדוע הרגולציה': 'Economic_Impact_Justification',
    'האם יש ברשותכם קובץ פטור': 'RIA_Submission_Exemption_Exists_Flag',
    'פטור לדוח הערכת רגולציה': 'RIA_Submission_Exemption_URL',
    'העלו את דוח הערכת': 'RIA_Submission_Full_Report_URL',
    'Submission ID': 'Submission_ID',
    'Respondent ID': 'Respondent_ID',
    'dt': 'Internal_Timestamp'
}

# --- UTILITIES ---

def translate_official_column(col_name):
    """Detects keywords in Hebrew headers and translates them to English."""
    for heb_keyword, eng_name in SMART_TRANSLATION_MAP.items():
        if heb_keyword in col_name:
            return eng_name
    clean_name = re.sub(r'[^a-zA-Z0-9]', '_', col_name).strip('_')
    return f"Official_Meta_{clean_name}"

def sanitize_folder_name(name):
    if not name or pd.isna(name):
        return "Unknown_Ministry"
    clean = re.sub(r'[\\/*?:"<>|]', '', str(name)).strip()
    clean = re.sub(r'\s+', '_', clean)
    return clean


def get_absolute_path(relative_path):
    """Converts a universal relative path from the CSV to an absolute path for the current machine."""
    if not isinstance(relative_path, str) or pd.isna(relative_path):
        return None
    normalized_path = os.path.normpath(relative_path)
    return os.path.join(BASE_DATA_DIR, normalized_path)


def get_stealth_driver(download_dir):
    from src.browser_factory import chrome
    return chrome(download_dir)


def download_and_track_file(url, target_folder_absolute, base_subfolder, ministry_clean, rel_base_name="downloads"):
    """
    Downloads the file using its original name provided by the server.
    Returns the universal relative path to be saved in the CSV.
    """
    if not isinstance(url, str) or pd.isna(url) or not url.strip():
        return None

    driver = get_stealth_driver(target_folder_absolute)
    print(f"      [Network] Starting download from: {url[:60]}...")

    # Snapshot of directory before download
    existing_files = set(os.listdir(target_folder_absolute))

    try:
        driver.get(url)
        for _ in range(35):  # Wait up to 35 seconds
            time.sleep(1)
            current_files = set(os.listdir(target_folder_absolute))
            new_files = current_files - existing_files

            if new_files:
                # Check if file is still downloading (.crdownload or .tmp)
                if any(f.endswith('.crdownload') or f.endswith('.tmp') for f in new_files):
                    continue

                # Download finished successfully
                downloaded_file = list(new_files)[0]
                print(f"      [Network] Download complete. Original file saved: {downloaded_file}")

                # Construct relative path using the provided base name
                rel_path = f"{rel_base_name}/{base_subfolder}/{ministry_clean}/{downloaded_file}"
                return rel_path
    except Exception as e:
        print(f"      [!] Download failed: {e}")
    finally:
        driver.quit()

    return None


def extract_text(file_path):
    if not file_path or not os.path.exists(file_path):
        return ""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(4)
        if header == b'%PDF':
            return " ".join([p.extract_text() for p in PdfReader(file_path).pages if p.extract_text()])
        elif header == b'PK\x03\x04':
            return " ".join([p.text for p in Document(file_path).paragraphs])
    except Exception:
        pass
    return ""


def get_similarity(text1, text2):
    s1 = set(re.findall(r'\w+', (text1 or "").lower()))
    s2 = set(re.findall(r'\w+', (text2 or "").lower()))
    return (len(s1 & s2) / len(s1 | s2)) * 100 if s1 and s2 else 0.0


def create_unified_row(portal_row, official_row, score, status):
    """Constructs a standardized English row, mapping data from both sources."""
    unified_title = portal_row.get(P_TITLE) if portal_row is not None else official_row.get(T_TITLE)
    unified_office = portal_row.get(P_OFFICE) if portal_row is not None else official_row.get(T_OFFICE)

    # Resolve fallback URL identifier logic
    portal_url = portal_row.get(P_FILE) if portal_row is not None else "N/A"
    submission_url = official_row.get(T_FILE) if official_row is not None else "N/A"

    # Fallback structure: prioritize Submission URL, then Portal URL, default to N/A string
    unique_url = submission_url if (pd.notna(submission_url) and str(submission_url).strip() != "N/A") else portal_url

    # Extract dynamic fallback date for official submission entries
    resolved_submission_date = "N/A"
    if official_row is not None:
        override_val = official_row.get('אנא ציינו את התאריך היום')
        if pd.notna(override_val) and str(override_val).strip() != "":
            resolved_submission_date = str(override_val).strip()
        else:
            resolved_submission_date = official_row.get(T_DATE, "N/A")

    row = {
        'unique_url_regulation': unique_url,
        'Regulation_Title': unified_title,
        'Responsible_Ministry': unified_office,
        'Processing_Status': status,
        'Similarity_Score': round(score, 2),
        'Portal_Publish_Date': portal_row.get(P_DATE) if portal_row is not None else "N/A",
        'Submission_Date': resolved_submission_date,
        'Portal_Web_Page': portal_row.get(P_URL) if portal_row is not None else "N/A",
        'Portal_Regulation_URL': portal_row.get(P_FILE) if portal_row is not None else "N/A",
        'Submission_Regulation_URL': official_row.get(T_FILE) if official_row is not None else "N/A",
        'Portal_Local_Regulation_Path': portal_row.get('Local_File_Path', 'N/A') if portal_row is not None else "N/A",
        'Portal_Local_RIA_Path': portal_row.get('Local_RIA_File_Path', 'N/A') if portal_row is not None else "N/A",
        'Submission_Local_Regulation_Path': official_row.get('Local_File_Path',
                                                             'N/A') if official_row is not None else "N/A",
        'Submission_Local_RIA_Path': official_row.get('Local_RIA_File_Path',
                                                      'N/A') if official_row is not None else "N/A",
    }

    if portal_row is not None:
        row['Legislation_Type'] = portal_row.get('legislation_type', 'Other')
        row['RIA_Portal_Exists_Flag'] = portal_row.get('has_standard_ria', 'No')
        row['RIA_Portal_Standard_URL'] = portal_row.get('standard_ria_url', 'N/A')
        row['RIA_Portal_Exemption_URL'] = portal_row.get('ria_exemption_url', 'N/A')
        row['Portal_Description'] = portal_row.get('description', 'N/A')
        row['Portal_Subjects'] = portal_row.get('subjects', 'N/A')

    if official_row is not None:
        exclude_list = [T_OFFICE, T_TITLE, T_FILE, T_DATE, 'dt', 'Local_File_Path']
        for k, v in official_row.items():
            if k not in exclude_list:
                translated_key = translate_official_column(k)

                # Logic to translate Hebrew "Yes/No" to English
                if translated_key == 'RIA_Submission_Exemption_Exists_Flag':
                    translation_map = {'כן': 'Yes', 'לא': 'No'}
                    v = translation_map.get(str(v).strip(), v)

                row[translated_key] = v

    return row


# --- EXECUTION ENGINE ---

def run_cross_reference():
    print(f"\n{'=' * 90}")
    print(f"[*] STARTING FULL REGULATORY SYNC & CROSS-REFERENCE")
    print(f"[*] Mode: Download All Submissions -> Fetch Portal Suspects -> Compare")
    print(f"{'=' * 90}")

    if not os.path.exists(PORTAL_CSV) or not os.path.exists(OFFICIAL_SUBMISSIONS_CSV):
        raise FileNotFoundError("Source CSV files are missing")

    portal_df = pd.read_csv(PORTAL_CSV)
    official_df = pd.read_csv(OFFICIAL_SUBMISSIONS_CSV)

    # Ensure tracking columns exist for both Regulation files and RIA files
    for col in ['Local_File_Path', 'Local_RIA_File_Path']:
        if col not in official_df.columns:
            official_df[col] = None
        if col not in portal_df.columns:
            portal_df[col] = None

    portal_df['dt'] = pd.to_datetime(portal_df[P_DATE], dayfirst=True, errors='coerce')
    official_df['dt'] = pd.to_datetime(official_df[T_DATE], errors='coerce')

    # -------------------------------------------------------------------------
    # PHASE 1: Download ALL Official Submissions First
    # -------------------------------------------------------------------------
    print("\n[*] PHASE 1: Verifying and Downloading Official Submissions...")
    for idx, t_row in official_df.iterrows():
        t_title = t_row.get(T_TITLE, 'Untitled')
        t_office = t_row.get(T_OFFICE, 'Unknown')
        t_url = t_row.get(T_FILE)
        t_office_clean = sanitize_folder_name(t_office)

        saved_path = official_df.at[idx, 'Local_File_Path']
        abs_path = get_absolute_path(saved_path)

        if abs_path and os.path.exists(abs_path):
            print(f"    [CACHE FOUND] Official Submission row {idx}: '{t_title}' ({t_office})")
            print(f"                  -> Regulation File Path: {saved_path}")
        else:
            if pd.notnull(t_url) and str(t_url).startswith("http"):
                t_folder = os.path.join(DOWNLOADS_BASE, "Official_Submissions", t_office_clean)
                os.makedirs(t_folder, exist_ok=True)
                print(f"    [MISSING] Official Submission row {idx}: '{t_title}' -> Downloading from internet...")
                new_rel_path = download_and_track_file(t_url, t_folder, "Official_Submissions", t_office_clean)
                if new_rel_path:
                    official_df.at[idx, 'Local_File_Path'] = new_rel_path
            else:
                print(f"    [NO FILE PROVIDED] Official Submission row {idx}: '{t_title}' has no valid URL link.")

    # Save regulation tracking once
    official_df.to_csv(OFFICIAL_SUBMISSIONS_CSV, index=False, encoding='utf-8-sig')

    # -------------------------------------------------------------------------
    # PHASE 1.5: Identify and Download Missing RIA Files
    # -------------------------------------------------------------------------
    print("\n[*] PHASE 1.5: Scanning for missing RIA files...")
    RIA_OFFICIAL_COL = "אם נמצא, אנא העלו את דוח הערכת הרגולציה כאן"
    RIA_PORTAL_COL = "standard_ria_url"
    ria_queue = []

    print("  -> Checking Official Submissions Table for RIA status:")
    for idx, row in official_df.iterrows():
        url = row.get(RIA_OFFICIAL_COL)
        title = row.get(T_TITLE, 'Untitled')
        if pd.notnull(url) and str(url).startswith("http"):
            ria_path = row.get('Local_RIA_File_Path')
            if pd.notna(ria_path):
                print(f"     [RIA CACHED] Row {idx} '{title}': Found local RIA -> {ria_path}")
            else:
                print(f"     [RIA MISSING] Row {idx} '{title}': Has URL but no local file. Adding to download queue.")
                ria_queue.append(('official', idx, url, title, row.get(T_OFFICE)))
        else:
            print(f"     [NO RIA DECLARED] Row {idx} '{title}': Form does not contain a RIA URL.")

    print("\n  -> Checking Legislation Portal Table for RIA status:")
    for idx, row in portal_df.iterrows():
        url = row.get(RIA_PORTAL_COL)
        title = row.get(P_TITLE, 'Untitled')
        if pd.notnull(url) and str(url).startswith("http"):
            ria_path = row.get('Local_RIA_File_Path')
            if pd.notna(ria_path):
                print(f"     [RIA CACHED] Row {idx} '{title}': Found local RIA -> {ria_path}")
            else:
                print(f"     [RIA MISSING] Row {idx} '{title}': Has URL but no local file. Adding to download queue.")
                ria_queue.append(('portal', idx, url, title, row.get(P_OFFICE)))
        else:
            print(f"     [NO RIA DECLARED] Row {idx} '{title}': Portal row does not contain a standard RIA URL.")

    if ria_queue:
        print(f"\n    [i] Executing queue: Downloading {len(ria_queue)} missing RIA files...")
        for source, idx, url, title, office in ria_queue:
            office_clean = sanitize_folder_name(office)
            base_sub = "Official_Submissions" if source == 'official' else "Legislation_Portal"
            target_folder = os.path.join(RIA_DOWNLOADS_BASE, base_sub, office_clean)
            os.makedirs(target_folder, exist_ok=True)
            new_rel_path = download_and_track_file(url, target_folder, base_sub, office_clean, "downloaded_RIA")
            if new_rel_path:
                if source == 'official':
                    official_df.at[idx, 'Local_RIA_File_Path'] = new_rel_path
                else:
                    portal_df.at[idx, 'Local_RIA_File_Path'] = new_rel_path

        official_df.to_csv(OFFICIAL_SUBMISSIONS_CSV, index=False, encoding='utf-8-sig')
        portal_df.to_csv(PORTAL_CSV, index=False, encoding='utf-8-sig')
    else:
        print("\n    [V] All declared RIA files are fully accounted for inside the spreadsheet tracking columns.")

    # -------------------------------------------------------------------------
    # PHASE 1.6: Bulk Download ALL Portal Regulation Files
    # -------------------------------------------------------------------------
    # This ensures that even "Orphan" portal entries have their main regulation files
    # downloaded locally, allowing the AI Summarizer to analyze them later.
    print("\n[*] PHASE 1.6: Ensuring all Portal Regulation files are downloaded...")
    portal_downloaded_count = 0

    for p_idx, p_row in portal_df.iterrows():
        p_title = p_row.get(P_TITLE, 'Untitled')
        p_office = p_row.get(P_OFFICE, 'Unknown')
        p_url = p_row.get(P_FILE)
        p_office_clean = sanitize_folder_name(p_office)

        saved_path = portal_df.at[p_idx, 'Local_File_Path']
        abs_path = get_absolute_path(saved_path)

        if pd.notnull(p_url) and str(p_url).startswith("http"):
            if abs_path and os.path.exists(abs_path):
                print(f"    [CACHE FOUND] Portal Regulation row {p_idx}: '{p_title}' ({p_office})")
                print(f"                  -> Regulation File Path: {saved_path}")
            else:
                p_folder = os.path.join(DOWNLOADS_BASE, "Legislation_Portal", p_office_clean)
                os.makedirs(p_folder, exist_ok=True)
                print(f"    [MISSING] Portal Regulation row {p_idx}: '{p_title}' -> Downloading from internet...")
                new_rel_path = download_and_track_file(p_url, p_folder, "Legislation_Portal", p_office_clean)
                if new_rel_path:
                    portal_df.at[p_idx, 'Local_File_Path'] = new_rel_path
                    portal_downloaded_count += 1
        else:
            print(
                f"    [NO FILE PROVIDED] Portal Regulation row {p_idx}: '{p_title}' has no main legislation file link attachment.")

    if portal_downloaded_count > 0:
        portal_df.to_csv(PORTAL_CSV, index=False, encoding='utf-8-sig')
        print(f"\n    [V] Finished downloading {portal_downloaded_count} new portal regulation files.")
    else:
        print(
            "\n    [V] All declared Portal Regulation documents are fully accounted for inside the spreadsheet tracking columns.")

    # -------------------------------------------------------------------------
    # PHASE 2 & 3: Identify Suspects and Download Portal Files
    # -------------------------------------------------------------------------
    print("\n[*] PHASE 2: Identifying Suspects and Fetching Portal Documents...")
    suspect_indices_in_portal = set()

    # Map each submission index to a list of portal suspect indices
    submission_to_suspects_map = {}

    for t_idx, t_row in official_df.iterrows():
        t_office_raw = str(t_row.get(T_OFFICE, "Unknown"))

        suspects_for_this_submission = []
        for p_idx, p_row in portal_df.iterrows():
            if (t_office_raw in str(p_row.get(P_OFFICE)) or str(p_row.get(P_OFFICE)) in t_office_raw):
                if pd.notnull(t_row['dt']) and pd.notnull(p_row['dt']):
                    if abs((t_row['dt'] - p_row['dt']).days) <= 120:
                        suspect_indices_in_portal.add(p_idx)
                        suspects_for_this_submission.append(p_idx)

        submission_to_suspects_map[t_idx] = suspects_for_this_submission

    # Download ONLY the suspects from the Legislation Portal
    for p_idx in suspect_indices_in_portal:
        p_row = portal_df.iloc[p_idx]
        p_url = p_row.get(P_FILE)
        p_office_clean = sanitize_folder_name(p_row.get(P_OFFICE, "Unknown"))

        saved_path = portal_df.at[p_idx, 'Local_File_Path']
        abs_path = get_absolute_path(saved_path)

        if abs_path and os.path.exists(abs_path):
            pass  # Suspect file is already cached
        else:
            p_folder = os.path.join(DOWNLOADS_BASE, "Legislation_Portal", p_office_clean)
            os.makedirs(p_folder, exist_ok=True)

            print(f"    -> Fetching Portal Suspect: '{p_row.get(P_TITLE, 'Untitled')[:40]}...'")
            new_rel_path = download_and_track_file(p_url, p_folder, "Legislation_Portal", p_office_clean)
            if new_rel_path:
                portal_df.at[p_idx, 'Local_File_Path'] = new_rel_path

    # Save tracked portal files to RAW CSV
    portal_df.to_csv(PORTAL_CSV, index=False, encoding='utf-8-sig')

    # -------------------------------------------------------------------------
    # PHASE 4: Cross-Reference & Compare
    # -------------------------------------------------------------------------
    print("\n[*] PHASE 3: Comparing Text and Generating Report...")
    final_results = []
    matched_portal_urls = set()

    for t_idx, t_row in official_df.iterrows():
        t_title = str(t_row.get(T_TITLE, "Untitled Submission"))
        suspects = submission_to_suspects_map[t_idx]

        print(f"\n[ANALYZING] Submission: '{t_title}'")

        if not suspects:
            print("    [i] No suspects found in Legislation Portal (Filtered by Ministry/Date).")
            new_row = create_unified_row(None, t_row, 0, 'Official Submission Only')
            new_row['Associated_Regulations_Count'] = 0
            final_results.append(new_row)
            continue

        print(f"    [?] Comparing against {len(suspects)} suspect(s)...")

        t_abs_path = get_absolute_path(t_row.get('Local_File_Path'))
        t_text = extract_text(t_abs_path)

        best_match_row = None
        highest_score = 0.0
        valid_matches_count = 0

        if t_text:
            for p_idx in suspects:
                p_row = portal_df.iloc[p_idx]
                p_title = p_row.get(P_TITLE)

                p_abs_path = get_absolute_path(p_row.get('Local_File_Path'))
                p_text = extract_text(p_abs_path)

                score = get_similarity(t_text, p_text)
                print(f"      -> VS Portal: '{p_title[:50]}...' | SCORE: {score:.2f}%")

                # Track how many total files pass the threshold for context
                if score >= SIMILARITY_THRESHOLD:
                    valid_matches_count += 1

                # Dynamically isolate the single absolute maximum score
                if score > highest_score:
                    highest_score = score
                    best_match_row = p_row

        # Check if the single highest scoring document clears the required entry criteria
        if highest_score >= SIMILARITY_THRESHOLD and best_match_row is not None:
            print(
                f"    [V] VERIFIED: Best match confirmed with score {highest_score:.2f}%. (Total qualifying: {valid_matches_count})")
            new_row = create_unified_row(best_match_row, t_row, highest_score, 'Verified Match')
            new_row['Associated_Regulations_Count'] = valid_matches_count
            final_results.append(new_row)
            matched_portal_urls.add(best_match_row[P_URL])
        else:
            print(f"    [X] UNVERIFIED: Highest score was {highest_score:.2f}%. Marking as Unverified.")
            new_row = create_unified_row(None, t_row, highest_score, 'Submission (Unverified)')
            new_row['Associated_Regulations_Count'] = 0
            final_results.append(new_row)

    # Collect Orphan Portal entries
    print(f"\n[*] Finalizing: Adding remaining Portal entries with no submission match...")
    for _, p_row in portal_df.iterrows():
        if p_row[P_URL] not in matched_portal_urls:
            new_row = create_unified_row(p_row, None, 0, 'Portal Entry Only')
            new_row['Associated_Regulations_Count'] = 0
            final_results.append(new_row)

    # -------------------------------------------------------------------------
    # PHASE 5: Save Log (Styled) - WITH SAFE SMART MERGE FOR ADDITIONAL COLUMNS
    # -------------------------------------------------------------------------
    final_df = pd.DataFrame(final_results)
    if not final_results:
        schema = create_unified_row({P_TITLE: '', P_OFFICE: ''}, None, 0, '')
        final_df = pd.DataFrame(columns=list(schema))
        final_df['Associated_Regulations_Count'] = pd.Series(dtype='int64')
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    # Define the custom/AI columns you want to protect from being wiped out
    columns_to_preserve = ['נושא', 'סיכום AI']

    if os.path.exists(MERGED_XLSX):
        print(f"\n[i] Found existing log at {MERGED_XLSX}. Checking for columns to preserve...")
        try:
            # Read the current physical Excel file from disk
            existing_df = pd.read_excel(MERGED_XLSX)

            # Clean and filter existing historical data
            required_existing_cols = ['unique_url_regulation', 'Submission_Regulation_URL', 'Portal_Regulation_URL'] + [
                c for c in columns_to_preserve if c in existing_df.columns]
            existing_clean = existing_df[[c for c in required_existing_cols if c in existing_df.columns]].copy()

            # Initialize target columns in the new final DataFrame
            for col in columns_to_preserve:
                final_df[col] = None

            # Build high-performance lookup dictionaries from historical records using both URL types
            sub_lookup = {}
            portal_lookup = {}

            for _, hist_row in existing_clean.iterrows():
                sub_url = str(hist_row.get('Submission_Regulation_URL', '')).strip()
                port_url = str(hist_row.get('Portal_Regulation_URL', '')).strip()

                # Bundle all historical metadata we want to pass back
                meta_payload = {
                    'נושא': hist_row.get('נושא') if pd.notna(hist_row.get('נושא')) else None,
                    'סיכום AI': hist_row.get('סיכום AI') if pd.notna(hist_row.get('סיכום AI')) else None,
                    'unique_url_regulation': hist_row.get('unique_url_regulation')
                }

                if sub_url and sub_url != 'N/A' and sub_url != 'nan':
                    sub_lookup[sub_url] = meta_payload
                if port_url and port_url != 'N/A' and port_url != 'nan':
                    portal_lookup[port_url] = meta_payload

            # Process each new row in final_df to graft historical data if a match is found
            print("    -> Cross-referencing current URLs against historical Submission & Portal URLs...")
            for idx, row in final_df.iterrows():
                curr_sub_url = str(row.get('Submission_Regulation_URL', '')).strip()
                curr_port_url = str(row.get('Portal_Regulation_URL', '')).strip()

                matched_payload = None

                # Match Hierarchy: Check Submission URL match first, fall back to Portal URL match
                if curr_sub_url in sub_lookup:
                    matched_payload = sub_lookup[curr_sub_url]
                elif curr_port_url in portal_lookup:
                    matched_payload = portal_lookup[curr_port_url]

                # If an historical match is verified, restore historical AI text and original unique key
                if matched_payload:
                    final_df.at[idx, 'נושא'] = matched_payload['נושא']
                    final_df.at[idx, 'סיכום AI'] = matched_payload['סיכום AI']
                    if pd.notna(matched_payload['unique_url_regulation']):
                        final_df.at[idx, 'unique_url_regulation'] = matched_payload['unique_url_regulation']

        except Exception as e:
            print(f"    [!] Warning: Failed to process existing file for smart URL matching ({e}). Writing fresh data.")
    else:
        # If no file exists, make sure the columns are initialized so downstream scripts don't fail
        for col in columns_to_preserve:
            if col not in final_df.columns:
                final_df[col] = None

    # Write the safely merged DataFrame back to the Excel file
    with pd.ExcelWriter(MERGED_XLSX, engine='xlsxwriter') as writer:
        final_df.to_excel(writer, index=False, sheet_name='Regulatory_Log')
        workbook = writer.book
        worksheet = writer.sheets['Regulatory_Log']

        header_format = workbook.add_format({'bold': True, 'bg_color': '#D9EAD3', 'border': 1})
        for col_num, value in enumerate(final_df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            worksheet.set_column(col_num, col_num, 24)

        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, len(final_df), len(final_df.columns) - 1)

    print(f"\n{'=' * 90}")
    print(f"[*] SUCCESS: Full Sync Finished. Report saved at: {MERGED_XLSX}")
    print(f"{'=' * 90}")


if __name__ == "__main__":
    run_cross_reference()
