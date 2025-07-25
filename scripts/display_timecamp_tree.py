#!/usr/bin/env python3
"""
Display tree structure from ../var/timecamp_users.json file.

This script reads the ../var/timecamp_users.json file and displays the group hierarchy
as a tree structure with user counts and optional detailed user listings.
"""

import json
import argparse
import csv
import io
from typing import Dict, List, Any, Set
from collections import defaultdict


def build_tree_structure(group_paths: Set[str]) -> Dict[str, Any]:
    """Build a tree structure from flat group paths."""
    tree = {}
    
    for path in sorted(group_paths):
        if not path:  # Skip empty paths
            continue
            
        parts = path.split('/')
        current = tree
        
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]
    
    return tree


def print_tree(tree: Dict[str, Any], prefix: str = "", is_last: bool = True) -> None:
    """Print tree structure with ASCII art."""
    items = list(tree.items())
    for i, (key, subtree) in enumerate(items):
        is_last_item = (i == len(items) - 1)
        
        # Draw the current item
        connector = "└── " if is_last_item else "├── "
        print(f"{prefix}{connector}{key}")
        
        # Prepare prefix for children
        if is_last_item:
            new_prefix = prefix + "    "
        else:
            new_prefix = prefix + "│   "
        
        # Recursively print children
        if subtree:
            print_tree(subtree, new_prefix, is_last_item)


def count_users_by_group(users: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group users by their group path."""
    groups = defaultdict(list)
    
    for user in users:
        # Only count active users
        if user.get('timecamp_status', '').lower() == 'active':
            group_path = user.get('timecamp_groups_breadcrumb', '')
            if group_path:
                groups[group_path].append(user)
            else:
                groups['<root>'].append(user)
    
    return dict(groups)


def parse_user_name(user_name: str) -> tuple[str, str]:
    """Parse user name to extract job title and name.
    
    Expected format: "Job Title [Name]" or just "Name"
    Returns: (job_title, name)
    """
    if not user_name:
        return "", ""
    
    # Check if name contains job title in brackets format
    if '[' in user_name and ']' in user_name:
        # Extract job title and name from "Job Title [Name]" format
        bracket_start = user_name.find('[')
        bracket_end = user_name.find(']')
        
        if bracket_start > 0 and bracket_end > bracket_start:
            job_title = user_name[:bracket_start].strip()
            name = user_name[bracket_start+1:bracket_end].strip()
            return job_title, name
    
    # If no brackets or invalid format, treat entire string as name
    return "", user_name


def generate_csv_output(users: List[Dict[str, Any]]) -> str:
    """Generate CSV output with all users."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['external_id', 'name', 'job_title', 'department', 'status', 'supervisor_id', 'role'])
    
    # Write user data
    for user in users:
        external_id = user.get('timecamp_external_id', '')
        user_name = user.get('timecamp_user_name', '')
        department = user.get('timecamp_groups_breadcrumb', '')
        status = user.get('timecamp_status', '')
        role = user.get('timecamp_role', '')
        
        # Parse name and job title
        job_title, name = parse_user_name(user_name)
        
        # supervisor_id is not available in current data structure
        supervisor_id = ''
        
        writer.writerow([external_id, name, job_title, department, status, supervisor_id, role])
    
    return output.getvalue()


def display_tree_structure(users: List[Dict[str, Any]], detailed: bool = False) -> None:
    """Display the tree structure with user counts."""
    # Extract unique group paths
    group_paths = set()
    active_users = []
    
    for user in users:
        if user.get('timecamp_status', '').lower() == 'active':
            active_users.append(user)
            group_path = user.get('timecamp_groups_breadcrumb', '')
            if group_path:
                group_paths.add(group_path)
    
    # Count users and roles
    supervisor_count = len([u for u in active_users if u.get('timecamp_role') == 'supervisor'])
    regular_user_count = len([u for u in active_users if u.get('timecamp_role') == 'user'])
    
    # Print header
    print("=" * 80)
    print("TIMECAMP GROUP STRUCTURE")
    print("=" * 80)
    
    # Print statistics
    print(f"\n📊 STATISTICS:")
    print(f"   • Total Active Users: {len(active_users)}")
    print(f"   • Supervisors: {supervisor_count}")
    print(f"   • Regular Users: {regular_user_count}")
    print(f"   • Total Groups: {len(group_paths)}")
    
    # Build and display tree
    print(f"\n🌳 GROUP HIERARCHY:")
    if group_paths:
        tree = build_tree_structure(group_paths)
        print_tree(tree)
    else:
        print("   (No group structure found - all users in root)")
    
    # Show user distribution
    user_groups = count_users_by_group(users)
    
    print(f"\n👥 USER DISTRIBUTION:")
    for group_path in sorted(user_groups.keys()):
        users_in_group = user_groups[group_path]
        count = len(users_in_group)
        group_display = group_path if group_path != '<root>' else '(root group)'
        print(f"   • {group_display:<40} {count:>3} user{'s' if count != 1 else ''}")
    
    # Show detailed breakdown if requested
    if detailed:
        print("\n" + "=" * 80)
        print("DETAILED USER BREAKDOWN")
        print("=" * 80)
        
        for group_path in sorted(user_groups.keys()):
            users_in_group = sorted(user_groups[group_path], 
                                  key=lambda x: x.get('timecamp_user_name', ''))
            
            group_display = group_path.upper() if group_path != '<root>' else 'ROOT GROUP'
            print(f"\n📁 {group_display} ({len(users_in_group)} users):")
            
            for user in users_in_group:
                role_emoji = "👑" if user.get('timecamp_role') == 'supervisor' else "👤"
                name = user.get('timecamp_user_name', 'Unknown')
                email = user.get('timecamp_email', '')
                real_email = user.get('timecamp_real_email', '')
                
                real_email_info = f" [real: {real_email}]" if real_email and real_email != email else ""
                print(f"   {role_emoji} {name} <{email}>{real_email_info}")

    # Generate and display CSV output
    print("\n" + "=" * 80)
    print("CSV OUTPUT (ALL USERS)")
    print("=" * 80)
    
    csv_output = generate_csv_output(users)
    print(csv_output)


def main():
    """Main function to run the tree display script."""
    parser = argparse.ArgumentParser(
        description="Display TimeCamp group structure from ../var/timecamp_users.json"
    )
    parser.add_argument(
        "--file", 
        default="../var/timecamp_users.json",
        help="Path to the TimeCamp users JSON file (default: ../var/timecamp_users.json)"
    )
    parser.add_argument(
        "--detailed", 
        action="store_true",
        help="Show detailed user breakdown for each group"
    )
    
    args = parser.parse_args()
    
    try:
        # Load the JSON file
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from common.storage import load_json_file
        
        users = load_json_file(args.file)
        
        if not isinstance(users, list):
            print(f"❌ Error: Expected a list of users in {args.file}")
            return
        
        # Display the tree structure
        display_tree_structure(users, detailed=args.detailed)
        
    except FileNotFoundError:
        print(f"❌ Error: File '{args.file}' not found.")
        print("Make sure ../var/timecamp_users.json exists or specify a different file with --file")
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in file: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main() 