import os
import json
import time
import argparse
import requests
from dotenv import load_dotenv
from common.logger import setup_logger
from common.utils import TimeCampConfig, clean_name, get_users_file
from common.supervisor_groups import process_source_data
from typing import Optional, Dict, List, Any, Set, Tuple
from common.api import TimeCampAPI

# Initialize logger with default level (will be updated in main)
logger = setup_logger('timecamp_sync_time_off')

def sync_vacations(vacation_file: str, api: TimeCampAPI, dry_run: bool = False, debug: bool = False) -> None:
    """Synchronize vacation/leave days from a JSON file to TimeCamp."""
    leave_types = {day_type['name']: day_type['id'] for day_type in api.get_day_types().values()}
    leave_types_day_off = {day_type['id']: day_type['isDayOff'] for day_type in api.get_day_types().values()}
    user_ids = {user['email']: user['user_id'] for user in api.get_users()}
    try:
        with open(vacation_file, 'r') as f:
            vacation_data = json.load(f)

        for entry in vacation_data.get("vacation", []):
            email = entry.get("email")
            user_id = user_ids.get(email)
            start_date = entry.get("start_on")
            end_date = entry.get("finish_on")
            leave_type_name = entry.get("tc_leave_type")
            leave_type = leave_types.get(leave_type_name)
            is_day_off = leave_types_day_off.get(leave_type, False)
            is_vacation = 'vacation' in leave_type_name.lower()
            should_be = 0 if is_day_off else 480
            vacation_time = 480 if is_vacation else 0

            if user_id and start_date and end_date and leave_type:
                if not dry_run:
                    api.add_vacation(user_id=user_id, start_date=start_date, end_date=end_date, 
                                     leave_type_id=leave_type, shouldBe=should_be, vacationTime=vacation_time)
                logger.info(f"Vacation added for {user_id} from {start_date} to {end_date} with leave type {leave_type_name}.")
            else:
                logger.warning(f"Incomplete vacation entry skipped: {entry} - {user_id}, {start_date}, {end_date}, {leave_type}")

        logger.info("Vacation synchronization completed.")
    except Exception as e:
        logger.error(f"Error during vacation synchronization: {e}")


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Synchronize users and groups between an external user source and TimeCamp",
        epilog="By default, only INFO level logs are displayed. Use --debug for detailed logging."
    )
    parser.add_argument("--dry-run", action="store_true", 
                      help="Simulate actions without making changes to TimeCamp")
    parser.add_argument("--debug", action="store_true", 
                      help="Enable debug logging to see detailed information about API calls and processing")
    return parser.parse_args()

if __name__ == "__main__":
    # Parse command-line arguments
    args = parse_arguments()
    
    # Set up logger with debug flag
    
    logger = setup_logger('timecamp_sync_time_off', args.debug)
    
    logger.info("Starting synchronization")
    sync_vacations("vacation.json", TimeCampAPI(TimeCampConfig.from_env()), dry_run=args.dry_run, debug=args.debug)
