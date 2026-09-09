import os
from pathlib import Path
import sys
from datetime import datetime

# Add the current directory to path to ensure imports work
current_dir = str(Path(__file__).resolve().parents[1])
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(current_dir) / '.env')
    from src.legislation_scraper import scrape_legislation_portal
    from src.official_submissions_fetcher import fetch_official_submissions
    from src.cross_reference_engine import run_cross_reference
    from src.friendly_table_generator import create_friendly_summary

except ImportError as e:
    print(f"\n[!] Critical Import Error: {e}")
    sys.exit(1)


def run_unified_sync(since=None):
    start_time = datetime.now()
    print(f"\n{'=' * 70}")
    print(f"[*] REGULATORY MONITORING SYSTEM - AUTOMATED SYNC")
    print(f"[*] Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 70}\n")

    print("[STEP 1/5] Checking Legislation Portal for new updates...")
    from datetime import date, timedelta
    cutoff = date.fromisoformat(since) if since else date.today() - timedelta(days=30)
    scrape_legislation_portal(target_date_str=cutoff.strftime('%d/%m/%Y'))

    print("\n[STEP 2/5] Synchronizing Official Submissions...")
    fetch_official_submissions()

    print("\n[STEP 3/5] Running Cross-Reference Engine...")
    run_cross_reference()

    print("\n[STEP 4/5] Executing AI Summarizer & Regulatory Classification...")
    if os.environ.get('ENABLE_AI', 'false').lower() == 'true':
        from src.ai_summarizer import process_ai_summaries
        process_ai_summaries()
    else:
        print('[AI] Disabled; original titles and source data remain available.')

    print("\n[STEP 5/5] Generating User-Friendly Hebrew Table...")
    create_friendly_summary()

    end_time = datetime.now()
    print(f"\n{'=' * 70}")
    print(f"[SUCCESS] Automated Sync Completed in {end_time - start_time}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--since', help='ISO start date; defaults to last 30 days')
    run_unified_sync(parser.parse_args().since)
