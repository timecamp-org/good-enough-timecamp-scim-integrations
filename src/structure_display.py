"""
Structure display utilities for TimeCamp sync.

This module provides functions to visualize the group structure that would be created
during synchronization without actually performing the sync.
"""

import json
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict, Counter
from common.utils import TimeCampConfig, get_users_file
from common.supervisor_groups import process_source_data


def build_tree_structure(department_paths: Set[str]) -> Dict[str, Any]:
    """
    Build a tree structure from flat department paths.
    
    Args:
        department_paths: Set of department paths like {"Engineering/John Doe", "Sales/Bob Smith"}
        
    Returns:
        Nested dictionary representing the tree structure
    """
    tree = {}
    
    for path in sorted(department_paths):
        if not path:  # Skip empty paths (root group assignments)
            continue
            
        parts = path.split('/')
        current = tree
        
        for part in parts:
            if part not in current:
                current[part] = {}
            current = current[part]
    
    return tree


def count_users_by_group(source_users: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    """
    Count how many users would be assigned to each group.
    
    Args:
        source_users: Dictionary mapping emails to user data
        
    Returns:
        Dictionary mapping group paths to user counts
    """
    group_counts = defaultdict(int)
    
    for email, user_data in source_users.items():
        # Only count active users
        if user_data.get('status', '').lower() == 'active':
            department = user_data.get('department', '')
            if department:
                group_counts[department] += 1
            else:
                group_counts['<root>'] += 1
    
    return dict(group_counts)


def get_users_in_group(source_users: Dict[str, Dict[str, Any]], group_path: str) -> List[Dict[str, Any]]:
    """
    Get list of users that would be assigned to a specific group.
    
    Args:
        source_users: Dictionary mapping emails to user data
        group_path: The group path to filter by
        
    Returns:
        List of user data dictionaries for users in the specified group
    """
    users_in_group = []
    
    for email, user_data in source_users.items():
        # Only include active users
        if user_data.get('status', '').lower() == 'active':
            user_department = user_data.get('department', '')
            if (group_path == '<root>' and not user_department) or user_department == group_path:
                users_in_group.append({
                    'email': email,
                    'name': user_data.get('name', 'Unknown'),
                    'external_id': user_data.get('external_id', ''),
                    'role_id': user_data.get('role_id', '3'),
                    'supervisor_id': user_data.get('supervisor_id', ''),
                    'real_email': user_data.get('real_email', '')
                })
    
    return sorted(users_in_group, key=lambda x: x['name'])


def print_tree(tree: Dict[str, Any], prefix: str = "", is_last: bool = True, level: int = 0) -> None:
    """
    Print tree structure with nice ASCII art.
    
    Args:
        tree: Nested dictionary representing the tree
        prefix: Current prefix for tree drawing
        is_last: Whether this is the last item at current level
        level: Current depth level
    """
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
            print_tree(subtree, new_prefix, is_last_item, level + 1)


def display_structure_summary(config: TimeCampConfig, source_users: Dict[str, Dict[str, Any]], 
                            department_paths: Set[str]) -> None:
    """
    Display a comprehensive summary of the structure that would be created.
    
    Args:
        config: TimeCamp configuration
        source_users: Dictionary mapping emails to user data
        department_paths: Set of department paths that would be created
    """
    print("=" * 80)
    print("TIMECAMP GROUP STRUCTURE PREVIEW")
    print("=" * 80)
    
    # Display configuration
    print(f"\n📋 CONFIGURATION:")
    print(f"   • Supervisor Groups: {'✅ Enabled' if config.use_supervisor_groups else '❌ Disabled'}")
    print(f"   • Department Groups: {'✅ Enabled' if config.use_department_groups else '❌ Disabled'}")
    
    if config.use_supervisor_groups and config.use_department_groups:
        print(f"   • Mode: 🔄 HYBRID (Department + Supervisor structure)")
    elif config.use_supervisor_groups:
        print(f"   • Mode: 👥 SUPERVISOR-ONLY structure")
    else:
        print(f"   • Mode: 🏢 DEPARTMENT-ONLY structure")
    
    if config.skip_departments:
        print(f"   • Skip Departments: '{config.skip_departments}'")
    
    # Count users and groups
    active_users = [u for u in source_users.values() if u.get('status', '').lower() == 'active']
    supervisor_count = len([u for u in active_users if u.get('role_id') == '2'])
    regular_user_count = len([u for u in active_users if u.get('role_id') == '3'])
    
    print(f"\n📊 STATISTICS:")
    print(f"   • Total Active Users: {len(active_users)}")
    print(f"   • Supervisors: {supervisor_count}")
    print(f"   • Regular Users: {regular_user_count}")
    print(f"   • Groups to Create: {len(department_paths)}")
    
    # Build and display tree structure
    if department_paths:
        print(f"\n🌳 GROUP STRUCTURE:")
        tree = build_tree_structure(department_paths)
        if tree:
            print_tree(tree)
        else:
            print("   (All users will be placed in root group)")
    else:
        print(f"\n🌳 GROUP STRUCTURE:")
        print("   (All users will be placed in root group)")
    
    # Show user distribution
    group_counts = count_users_by_group(source_users)
    if group_counts:
        print(f"\n👥 USER DISTRIBUTION:")
        max_group_name_length = max(len(group) for group in group_counts.keys())
        
        for group_path in sorted(group_counts.keys()):
            count = group_counts[group_path]
            group_display = group_path if group_path != '<root>' else '(root group)'
            print(f"   • {group_display:<{max_group_name_length + 5}} {count:>3} user{'s' if count != 1 else ''}")


def display_detailed_structure(config: TimeCampConfig, source_users: Dict[str, Dict[str, Any]], 
                             department_paths: Set[str]) -> None:
    """
    Display detailed structure with users listed in each group.
    
    Args:
        config: TimeCamp configuration
        source_users: Dictionary mapping emails to user data
        department_paths: Set of department paths that would be created
    """
    print("\n" + "=" * 80)
    print("DETAILED GROUP BREAKDOWN")
    print("=" * 80)
    
    group_counts = count_users_by_group(source_users)
    
    # Handle root group users
    if '<root>' in group_counts:
        print(f"\n📁 ROOT GROUP ({group_counts['<root>']} users):")
        root_users = get_users_in_group(source_users, '<root>')
        for user in root_users:
            role_emoji = "👑" if user['role_id'] == '2' else "👤"
            supervisor_info = f" (reports to: {user['supervisor_id']})" if user['supervisor_id'] else ""
            print(f"   {role_emoji} {user['name']} <{user['email']}>{supervisor_info}")
    
    # Handle departmental groups
    for group_path in sorted(department_paths):
        if group_path and group_path in group_counts:
            print(f"\n📁 {group_path.upper()} ({group_counts[group_path]} users):")
            group_users = get_users_in_group(source_users, group_path)
            for user in group_users:
                role_emoji = "👑" if user['role_id'] == '2' else "👤"
                supervisor_info = f" (reports to: {user['supervisor_id']})" if user['supervisor_id'] else ""
                real_email_info = f" [real: {user['real_email']}]" if user['real_email'] and user['real_email'] != user['email'] else ""
                print(f"   {role_emoji} {user['name']} <{user['email']}>{real_email_info}{supervisor_info}")


def show_structure(config: TimeCampConfig, users_file: str, detailed: bool = False) -> None:
    """
    Main function to display the structure that would be created.
    
    Args:
        config: TimeCamp configuration
        users_file: Path to the users JSON file
        detailed: Whether to show detailed breakdown with individual users
    """
    try:
        # Load and process source data
        with open(users_file, 'r') as f:
            source_data = json.load(f)
        
        # Process using the same logic as the main sync
        source_users, department_paths = process_source_data(source_data, config)
        
        # Display structure summary
        display_structure_summary(config, source_users, department_paths)
        
        # Display detailed breakdown if requested
        if detailed:
            display_detailed_structure(config, source_users, department_paths)
        
        print("\n" + "=" * 80)
        print("ℹ️  This is a preview only. Use without --show-structure to perform actual sync.")
        print("=" * 80)
        
    except FileNotFoundError:
        print(f"❌ Error: Users file '{users_file}' not found.")
        print("Please run the integration script first to generate users.json")
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in users file: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def main() -> None:
    """
    Standalone main function for testing the structure display.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Display TimeCamp group structure preview")
    parser.add_argument("--detailed", action="store_true", help="Show detailed user breakdown")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    # Set up configuration
    config = TimeCampConfig.from_env()
    users_file = get_users_file()
    
    show_structure(config, users_file, detailed=args.detailed)


if __name__ == "__main__":
    main() 