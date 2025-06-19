"""
Remove Empty TimeCamp Groups
This script identifies and removes groups that have no users and no subgroups.
"""

import os
import argparse
from typing import Dict, List, Set, Any
from dotenv import load_dotenv
from common.logger import setup_logger
from common.utils import TimeCampConfig
from common.api import TimeCampAPI

# Load environment variables
load_dotenv()

# Initialize logger
logger = setup_logger('remove_empty_groups')


class EmptyGroupRemover:
    """Handles identification and removal of empty TimeCamp groups."""
    
    def __init__(self, api: TimeCampAPI, config: TimeCampConfig):
        self.api = api
        self.config = config
    
    def build_group_hierarchy(self, groups: List[Dict[str, Any]]) -> Dict[int, Set[int]]:
        """Build a map of parent groups to their child groups."""
        hierarchy = {}
        
        for group in groups:
            group_id = int(group['group_id'])
            parent_id = int(group.get('parent_id', 0))
            
            # Skip root group
            if parent_id == 0:
                continue
                
            if parent_id not in hierarchy:
                hierarchy[parent_id] = set()
            hierarchy[parent_id].add(group_id)
            
        return hierarchy
    
    def build_group_user_map(self, users: List[Dict[str, Any]]) -> Dict[int, Set[int]]:
        """Build a map of groups to their users."""
        group_users = {}
        
        for user in users:
            # Skip disabled users
            if not user.get('is_enabled', True):
                continue
                
            group_id = int(user.get('group_id', 0))
            user_id = int(user['user_id'])
            
            if group_id not in group_users:
                group_users[group_id] = set()
            group_users[group_id].add(user_id)
            
        return group_users
    
    def find_empty_groups(self, groups: List[Dict[str, Any]], 
                         users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify groups that have no users and no subgroups."""
        # Build hierarchy and user maps
        hierarchy = self.build_group_hierarchy(groups)
        group_users = self.build_group_user_map(users)
        
        empty_groups = []
        
        for group in groups:
            group_id = int(group['group_id'])
            
            # Skip root group
            if group_id == self.config.root_group_id:
                continue
            
            # Check if group has subgroups
            has_subgroups = group_id in hierarchy and len(hierarchy[group_id]) > 0
            
            # Check if group has users
            has_users = group_id in group_users and len(group_users[group_id]) > 0
            
            # If group has neither subgroups nor users, it's empty
            if not has_subgroups and not has_users:
                empty_groups.append(group)
                
        return empty_groups
    
    def build_group_paths(self, groups: List[Dict[str, Any]]) -> Dict[int, str]:
        """Build full paths for all groups."""
        groups_by_id = {int(g['group_id']): g for g in groups}
        paths = {}
        
        for group in groups:
            group_id = int(group['group_id'])
            path_parts = []
            current = group
            
            # Follow the parent chain to build the full path
            while current:
                path_parts.insert(0, current['name'].strip())
                parent_id = int(current.get('parent_id', 0))
                current = groups_by_id.get(parent_id) if parent_id > 0 else None
                
            full_path = '/'.join(path_parts)
            paths[group_id] = full_path
            
        return paths
    
    def remove_empty_groups(self, dry_run: bool = False) -> None:
        """Main method to find and remove empty groups."""
        logger.info("Fetching groups and users from TimeCamp...")
        
        # Get all groups and users
        groups = self.api.get_groups()
        users = self.api.get_users()
        
        logger.info(f"Found {len(groups)} groups and {len(users)} users")
        
        # Find empty groups
        empty_groups = self.find_empty_groups(groups, users)
        
        if not empty_groups:
            logger.info("No empty groups found")
            return
            
        # Build paths for better logging
        group_paths = self.build_group_paths(groups)
        
        # Sort empty groups by depth (deepest first) to avoid issues with parent-child relationships
        empty_groups.sort(key=lambda g: group_paths[int(g['group_id'])].count('/'), reverse=True)
        
        logger.info(f"Found {len(empty_groups)} empty groups")
        
        # Process each empty group
        for group in empty_groups:
            group_id = int(group['group_id'])
            group_name = group['name']
            group_path = group_paths[group_id]
            
            if dry_run:
                logger.info(f"[DRY RUN] Would delete empty group: {group_path} (ID: {group_id})")
            else:
                try:
                    logger.info(f"Deleting empty group: {group_path} (ID: {group_id})")
                    self.api.delete_group(group_id)
                except Exception as e:
                    logger.error(f"Failed to delete group {group_path} (ID: {group_id}): {str(e)}")
                    # Continue with other groups even if one fails
                    continue
        
        if dry_run:
            logger.info(f"[DRY RUN] Would have deleted {len(empty_groups)} empty groups")
        else:
            logger.info(f"Completed. Attempted to delete {len(empty_groups)} empty groups")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Remove empty TimeCamp groups (groups without users or subgroups)"
    )
    parser.add_argument("--dry-run", action="store_true",
                      help="Simulate actions without making changes")
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = TimeCampConfig.from_env()
        logger.info("Loaded configuration")
        
        # Initialize API and remover
        api = TimeCampAPI(config)
        remover = EmptyGroupRemover(api, config)
        
        # Remove empty groups
        remover.remove_empty_groups(args.dry_run)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error during execution: {str(e)}")
        raise


if __name__ == "__main__":
    exit(main()) 