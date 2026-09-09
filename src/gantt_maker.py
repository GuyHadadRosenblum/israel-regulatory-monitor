import os
import glob
import datetime
import pandas as pd
import plotly.express as px

def generate_gantts(min_submission_date=None):
    """
    Generates regulatory trackers and Gantt charts from the latest Monday table.

    Parameters:
    -----------
    min_submission_date : str or None
        Optional date string cutoff in 'YYYY-MM-DD' format. If provided, rows
        with an official submission date or portal publication date on or after
        this cutoff will be processed.
    """
    # 1. Configuration & Paths
    # Dynamically resolve script location to ensure cross-machine compatibility
    BASE_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR = os.path.join(os.path.dirname(BASE_SRC_DIR), "data", "gantt and tracking table")

    # Ensure the targeted output directory exists safely before executing save actions
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Dynamically resolve the input directory based on the relative path
    INPUT_DIR = os.path.join(OUTPUT_DIR, "monday_table")

    # Find all Excel files in the target directory
    search_pattern = os.path.join(INPUT_DIR, "*.xlsx")
    list_of_files = glob.glob(search_pattern)

    if not list_of_files:
        raise FileNotFoundError(f"No Excel files found in the directory: {INPUT_DIR}")

    # Automatically grab the latest file based on creation/modification time
    INPUT_FILE = max(list_of_files, key=os.path.getctime)
    print(f"[*] Found latest input file automatically: {INPUT_FILE}")

    # Read the Excel file directly, skipping the first 2 metadata rows (header on row 3 / index 2)
    df = pd.read_excel(INPUT_FILE, header=2)

    # Clean column names by stripping trailing whitespaces
    df.columns = df.columns.str.strip()

    # Helper function to parse dates safely
    def to_datetime_safe(series):
        return pd.to_datetime(series, errors='coerce', dayfirst=True)

    # Parse required date columns
    df['תאריך פנייה רשמית'] = to_datetime_safe(df['תאריך פנייה רשמית'])
    df['תאריך פנייה רשמי מעוכב מעודכן'] = to_datetime_safe(df['תאריך פנייה רשמי מעוכב מעודכן'])
    df['תאריך פרסום באתר'] = to_datetime_safe(df['תאריך פרסום באתר'])

    # --- OPTIONAL CUTOFF DATE FILTERING ---
    if min_submission_date is not None:
        cutoff_dt = pd.to_datetime(min_submission_date, errors='coerce')
        if pd.notna(cutoff_dt):
            initial_count = len(df)
            cond_official_submission_after = df['תאריך פנייה רשמית'] >= cutoff_dt
            cond_portal_publication_after = df['תאריך פרסום באתר'] >= cutoff_dt
            df = df[cond_official_submission_after | cond_portal_publication_after].copy()
            print(f"[*] Applied date filter (either date >= {min_submission_date}): Kept {len(df)} out of {initial_count} rows.")
        else:
            print(f"[!] Warning: Invalid date format provided for min_submission_date ('{min_submission_date}'). Skipping date filter.")

    # Handle missing values and convert text columns to clean strings (Always executed safely)
    df['האם קיים RIA/פטור'] = df['האם קיים RIA/פטור'].fillna('').astype(str).str.strip()
    df['תאריך עדכון האם הוחלט לייעץ'] = df['תאריך עדכון האם הוחלט לייעץ'].fillna('').astype(str).str.strip()
    df['סיווג אסדרה (AI)'] = df['סיווג אסדרה (AI)'].fillna('').astype(str).str.strip()
    df['מקור הנתונים'] = df['מקור הנתונים'].fillna('').astype(str).str.strip()

    # Rename the 'Name' or 'name' column to 'נושא' if it exists to match the mapping requirements
    if 'Name' in df.columns:
        df.rename(columns={'Name': 'נושא'}, inplace=True)
    elif 'name' in df.columns:
        df.rename(columns={'name': 'נושא'}, inplace=True)

    # Strict schema definition for final output logs
    REQUIRED_COLUMNS = [
        "נושא", "האם הוחלט לייעץ", "מקור הנתונים", "תאריך פרסום באתר",
        "קישור לדף החקיקה", "המשרד האחראי", "שם התקנה/חוק",
        "מזהה קישור ייחודי", "תאריך פנייה רשמית",
        "תאריך פנייה רשמי מעוכב מעודכן", "סיווג אסדרה (AI)"
    ]

    # Guarantee existence of all architecture target columns
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None

    print(f"[*] Total source rows parsed from Excel file: {len(df)}")

    # =========================================================================
    # FILTER 1: Open Official Submissions (Submission Exists, Has RIA, No Consultation Update)
    # =========================================================================
    cond_sub_exists = df['תאריך פנייה רשמית'].notna()
    cond_ria_exists = df['האם קיים RIA/פטור'] == "קיים RIA"
    cond_no_update = (df['תאריך עדכון האם הוחלט לייעץ'] == "") | (df['תאריך עדכון האם הוחלט לייעץ'].isna())

    df_filtered_1 = df[cond_sub_exists & cond_ria_exists & cond_no_update].copy()
    table_1_output = df_filtered_1[REQUIRED_COLUMNS]

    # Save Filter 1 Excel log using relative target path tracking
    table_1_output.to_excel(os.path.join(OUTPUT_DIR, "open_official_submissions.xlsx"), index=False)
    print(f"[V] Filter 1 Table exported successfully! Total rows: {len(table_1_output)}")

    # --- Generate Gantt Chart for Filter 1 ---
    gantt_data_1 = []
    today = pd.Timestamp(datetime.date.today())
    two_weeks_ahead = today + pd.Timedelta(days=14)

    for idx, row in df_filtered_1.iterrows():
        start_date = row['תאריך פנייה רשמי מעוכב מעודכן'] if pd.notna(row['תאריך פנייה רשמי מעוכב מעודכן']) else row['תאריך פנייה רשמית']

        if pd.notna(start_date):
            if str(row.get('האם הוחלט לייעץ')).strip() == "הוחלט לייעץ":
                task_days = 60 + 14
                max_visible_date = today + pd.Timedelta(days=74)
            else:
                task_days = 14
                max_visible_date = two_weeks_ahead

            end_date = start_date + pd.Timedelta(days=task_days)

            if end_date < today or end_date <= max_visible_date:
                gantt_data_1.append({
                    "Subject": row['נושא'],
                    "Start": start_date,
                    "Finish": end_date,
                    "Status": "Overdue" if end_date < today else (
                        "Due within 60+14 Days" if task_days == 74 else "Due within 2 Weeks")
                })

    if gantt_data_1:
        df_gantt_1 = pd.DataFrame(gantt_data_1)
        fig1 = px.timeline(df_gantt_1, x_start="Start", x_end="Finish", y="Subject", color="Status",
                           title="Gantt Chart - Official Submissions Response Windows (2 Weeks Ahead & Overdue)",
                           labels={"Subject": "Subject"})
        fig1.update_yaxes(autorange="reversed")
        fig1.add_vline(x=today.timestamp() * 1000, line_width=2, line_dash="dash", line_color="red",
                       annotation_text="Today", annotation_position="top right")
        fig1.write_html(os.path.join(OUTPUT_DIR, "gantt_official_submissions.html"))
        fig1.write_image(os.path.join(OUTPUT_DIR, "gantt_official_submissions.png"), width=1200, height=800)
        print("[V] Gantt Chart 1 (Official Submissions) saved as HTML file.")
    else:
        print("[i] No tasks matching timeline filters for Gantt Chart 1.")

    # =========================================================================
    # FILTER 2: Enforcement Log - Regulations with Missing RIA Documentation
    # =========================================================================
    cond_ai_reg = df['סיווג אסדרה (AI)'] == "אסדרה סיווג ראשוני"
    cond_no_ria = df['האם קיים RIA/פטור'] == "לא קיים RIA או פטור"

    # Exclude rows where the consultation decision is "Not Regulation"
    cond_not_regulation = df['האם הוחלט לייעץ'] != "לא אסדרה"

    df_filtered_2 = df[
        cond_ai_reg &
        cond_no_ria &
        cond_not_regulation
        ].copy()
    table_2_output = df_filtered_2[REQUIRED_COLUMNS]

    table_2_output.to_excel(os.path.join(OUTPUT_DIR, "enforcement_no_ria.xlsx"), index=False)
    print(f"[V] Filter 2 Table (Missing RIA Enforcement) exported successfully! Total rows: {len(table_2_output)}")

    # --- NEW: Generate Gantt Chart for Filter 2 (Missing RIA Enforcement) ---
    gantt_data_2 = []
    enforcement_deadline_2 = today + pd.Timedelta(days=14)

    for idx, row in df_filtered_2.iterrows():
        # Fallback tracking anchor: prefer portal publishing date, use official submission date as backup
        start_date = row['תאריך פרסום באתר'] if pd.notna(row['תאריך פרסום באתר']) else row['תאריך פנייה רשמית']

        if pd.notna(start_date):
            # Target compliance cutoff is enforced 14 days out from initial baseline detection
            deadline_date = start_date + pd.Timedelta(days=14)

            if deadline_date <= enforcement_deadline_2:
                gantt_data_2.append({
                    "Subject": row['נושא'],
                    "Start": start_date,
                    "Finish": deadline_date,
                    "Status": "Enforcement Window Overdue" if deadline_date < today else "Enforcement Active",
                    "Regulation_Name": row['שם התקנה/חוק'],
                    "Ministry": row['המשרד האחראי']
                })

    if gantt_data_2:
        df_gantt_2 = pd.DataFrame(gantt_data_2)
        fig2 = px.timeline(df_gantt_2,
                           x_start="Start",
                           x_end="Finish",
                           y="Subject",
                           color="Status",
                           title="Gantt Chart - Regulations Missing Legal RIA / Exemption Documentation",
                           labels={"Subject": "Subject", "Status": "Status"},
                           custom_data=["Regulation_Name", "Ministry", "Start", "Finish"])

        fig2.update_yaxes(autorange="reversed")
        color_map = {"Enforcement Window Overdue": "red", "Enforcement Active": "green"}
        fig2.for_each_trace(lambda t: t.update(marker_color=color_map.get(t.name, "gray")))

        fig2.update_traces(
            hovertemplate="<br>".join([
                "<b>Subject:</b> %{y}",
                "<b>Regulation/Law Name:</b> %{customdata[0]}",
                "<b>Responsible Ministry:</b> %{customdata[1]}",
                "<b>Start Date:</b> %{customdata[2]|%Y-%m-%d}",
                "<b>Enforcement Cutoff:</b> %{customdata[3]|%Y-%m-%d}"
            ]) + "<extra></extra>"
        )

        fig2.add_vline(x=today.timestamp() * 1000, line_width=2, line_dash="dash", line_color="red",
                       annotation_text="Today", annotation_position="top right")

        fig2.write_html(os.path.join(OUTPUT_DIR, "gantt_missing_ria.html"))
        fig2.write_image(os.path.join(OUTPUT_DIR, "gantt_missing_ria.png"), width=1200, height=800)
        print("[V] Gantt Chart 2 (Missing RIA Enforcement) saved as HTML file.")
    else:
        print("[i] No tasks matching timeline filters for Gantt Chart 2.")

    # =========================================================================
    # FILTER 3: Enforcement Log - Uploaded Portal Documents Missing Official Submissions
    # =========================================================================
    cond_portal_only = df['מקור הנתונים'] == "אתר החקיקה בלבד"
    cond_has_ria_or_exemption = df['האם קיים RIA/פטור'].isin(["קיים RIA", "קיים פטור"])

    three_days_ago = today - pd.Timedelta(days=3)
    cond_past_3_days = df['תאריך פרסום באתר'] <= three_days_ago

    df_filtered_3 = df[cond_portal_only & cond_has_ria_or_exemption & cond_past_3_days].copy()
    table_3_output = df_filtered_3[REQUIRED_COLUMNS]

    table_3_output.to_excel(os.path.join(OUTPUT_DIR, "enforcement_portal_no_submission.xlsx"), index=False)
    print(f"[V] Filter 3 Table (Portal Orphans > 3 Days) exported successfully! Total rows: {len(table_3_output)}")

    # --- Generate Gantt Chart for Filter 3 ---
    gantt_data_3 = []
    enforcement_deadline = today + pd.Timedelta(days=14)

    for idx, row in df_filtered_3.iterrows():
        start_date = row['תאריך פרסום באתר']

        if pd.notna(start_date):
            deadline_date = start_date + pd.Timedelta(days=14)

            if deadline_date <= enforcement_deadline:
                gantt_data_3.append({
                    "Subject": row['נושא'],
                    "Start": start_date,
                    "Finish": deadline_date,
                    "Status": "Enforcement Window Overdue" if deadline_date < today else "Enforcement Active",
                    "Regulation_Name": row['שם התקנה/חוק'],
                    "Ministry": row['המשרד האחראי']
                })

    if gantt_data_3:
        df_gantt_3 = pd.DataFrame(gantt_data_3)
        fig3 = px.timeline(df_gantt_3,
                           x_start="Start",
                           x_end="Finish",
                           y="Subject",
                           color="Status",
                           title="Gantt Chart - Portal RIA Documents/Exemptions Missing Official Submission Link",
                           labels={"Subject": "Subject", "Status": "Status"},
                           custom_data=["Regulation_Name", "Ministry", "Start", "Finish"])

        fig3.update_yaxes(autorange="reversed")
        color_map = {"Enforcement Window Overdue": "red", "Enforcement Active": "green"}
        fig3.for_each_trace(lambda t: t.update(marker_color=color_map.get(t.name, "gray")))

        fig3.update_traces(
            hovertemplate="<br>".join([
                "<b>Subject:</b> %{y}",
                "<b>Regulation/Law Name:</b> %{customdata[0]}",
                "<b>Responsible Ministry:</b> %{customdata[1]}",
                "<b>Start Date:</b> %{customdata[2]|%Y-%m-%d}",
                "<b>Deadline Date:</b> %{customdata[3]|%Y-%m-%d}"
            ]) + "<extra></extra>"
        )

        fig3.add_vline(x=today.timestamp() * 1000, line_width=2, line_dash="dash", line_color="red",
                       annotation_text="Today", annotation_position="top right")

        fig3.write_html(os.path.join(OUTPUT_DIR, "gantt_enforcement_portal.html"))
        fig3.write_image(os.path.join(OUTPUT_DIR, "gantt_enforcement_portal.png"), width=1200, height=800)
        print("[V] Gantt Chart 3 (Portal Enforcement Tracking) saved as HTML file.")
    else:
        print("[i] No tasks matching timeline filters for Gantt Chart 3.")

    print("\n[!] All data pipeline filters and visualization charts completed successfully.")


if __name__ == "__main__":
    generate_gantts(min_submission_date="2026-04-01")