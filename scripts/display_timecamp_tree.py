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
import html
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


def render_html_tree(tree: Dict[str, Any], user_groups: Dict[str, List[Dict[str, Any]]], current_path: str = "") -> str:
    """Recursively render the tree as HTML."""
    if not tree and not (current_path and current_path in user_groups):
        return ""

    html_parts = []
    html_parts.append('<ul class="tree">')
    
    for key, subtree in sorted(tree.items()):
        full_path = f"{current_path}/{key}" if current_path else key
        
        # Get users for this specific group node
        users = user_groups.get(full_path, [])
        
        # Generate HTML for users
        users_html = ""
        if users:
            users_html += '<ul class="users">'
            for user in sorted(users, key=lambda u: u.get('timecamp_user_name', '')):
                role_icon = "👑" if user.get('timecamp_role') == 'supervisor' else "👤"
                name = html.escape(user.get('timecamp_user_name', 'Unknown'))
                email = html.escape(user.get('timecamp_email', ''))
                role_class = "supervisor" if user.get('timecamp_role') == 'supervisor' else "regular"
                
                users_html += f'''
                    <li class="user-node {role_class}">
                        <span class="user-icon">{role_icon}</span>
                        <span class="user-name">{name}</span>
                        <span class="user-email">&lt;{email}&gt;</span>
                    </li>
                '''
            users_html += '</ul>'

        # Recursive children
        children_html = ""
        if subtree:
            children_html = render_html_tree(subtree, user_groups, full_path)
            
        # Combine
        user_count = len(users)
        count_badge = f'<span class="count-badge">{user_count}</span>' if user_count > 0 else ''
        
        html_parts.append(f'''
            <li>
                <details open>
                    <summary>
                        <span class="folder-icon">📁</span>
                        <span class="group-name">{html.escape(key)}</span>
                        {count_badge}
                    </summary>
                    <div class="group-content">
                        {users_html}
                        {children_html}
                    </div>
                </details>
            </li>
        ''')
        
    html_parts.append('</ul>')
    return "".join(html_parts)


def save_html_tree(users: List[Dict[str, Any]], output_file: str) -> None:
    """Generate and save an HTML visualization of the tree."""
    # Prepare data
    active_users = [u for u in users if u.get('timecamp_status', '').lower() == 'active']
    group_paths = set()
    for user in active_users:
        path = user.get('timecamp_groups_breadcrumb', '')
        if path:
            group_paths.add(path)
            
    tree = build_tree_structure(group_paths)
    user_groups = count_users_by_group(users)
    
    # Calculate stats
    supervisor_count = len([u for u in active_users if u.get('timecamp_role') == 'supervisor'])
    regular_user_count = len([u for u in active_users if u.get('timecamp_role') == 'user'])
    
    # Render parts
    # Root users
    root_users = user_groups.get('<root>', [])
    root_users_html = ""
    if root_users:
        root_users_html += '<div class="root-users"><h3>Users in Root (No Group)</h3><ul class="users">'
        for user in sorted(root_users, key=lambda u: u.get('timecamp_user_name', '')):
            role_icon = "👑" if user.get('timecamp_role') == 'supervisor' else "👤"
            name = html.escape(user.get('timecamp_user_name', 'Unknown'))
            email = html.escape(user.get('timecamp_email', ''))
            root_users_html += f'<li class="user-node"><span class="user-icon">{role_icon}</span> {name} <span class="user-email">&lt;{email}&gt;</span></li>'
        root_users_html += '</ul></div>'

    tree_html = render_html_tree(tree, user_groups)
    
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TimeCamp Group Structure</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; padding: 20px; background: #f5f5f5; color: #333; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        h1 {{ margin-top: 0; color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; background: #f8f9fa; padding: 15px; border-radius: 6px; }}
        .stat-item {{ display: flex; flex-direction: column; }}
        .stat-label {{ font-size: 0.85em; text-transform: uppercase; color: #7f8c8d; letter-spacing: 0.5px; }}
        .stat-value {{ font-size: 1.5em; font-weight: bold; color: #2c3e50; }}
        
        /* Tree Styles */
        ul.tree {{ list-style-type: none; margin: 0; padding: 0; }}
        ul.tree ul {{ margin-left: 20px; padding-left: 10px; border-left: 1px solid #eee; }}
        ul.tree li {{ margin: 5px 0; }}
        
        details summary {{ cursor: pointer; padding: 5px; border-radius: 4px; list-style: none; transition: background 0.2s; }}
        details summary:hover {{ background: #f0f4f8; }}
        details summary::-webkit-details-marker {{ display: none; }} /* Hide default triangle */
        
        .folder-icon {{ margin-right: 5px; }}
        .group-name {{ font-weight: 600; color: #2c3e50; }}
        .count-badge {{ background: #e2e8f0; color: #475569; font-size: 0.75em; padding: 2px 6px; border-radius: 10px; margin-left: 8px; vertical-align: middle; }}
        
        .group-content {{ margin-left: 10px; }}
        
        /* User Styles */
        ul.users {{ list-style-type: none; padding-left: 20px; margin: 5px 0; }}
        li.user-node {{ padding: 3px 0; font-size: 0.95em; display: flex; align-items: center; color: #555; }}
        li.user-node:hover {{ color: #000; }}
        .user-icon {{ margin-right: 6px; font-size: 1.1em; }}
        .user-name {{ margin-right: 8px; }}
        .user-email {{ color: #95a5a6; font-size: 0.9em; }}
        
        .root-users {{ margin-bottom: 20px; border: 1px dashed #cbd5e0; padding: 15px; border-radius: 6px; }}
        .root-users h3 {{ margin-top: 0; font-size: 1em; color: #718096; }}
        
        .legend {{ margin-top: 30px; border-top: 1px solid #eee; padding-top: 15px; font-size: 0.9em; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>TimeCamp Group Structure</h1>
        
        <div class="stats">
            <div class="stat-item">
                <span class="stat-label">Total Active Users</span>
                <span class="stat-value">{len(active_users)}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Supervisors</span>
                <span class="stat-value">{supervisor_count}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Regular Users</span>
                <span class="stat-value">{regular_user_count}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Total Groups</span>
                <span class="stat-value">{len(group_paths)}</span>
            </div>
        </div>

        <div class="tree-container">
            {root_users_html}
            {tree_html}
        </div>
        
        <div class="legend">
            <strong>Legend:</strong> 👑 Supervisor &nbsp;•&nbsp; 👤 User &nbsp;•&nbsp; 📁 Group
        </div>
    </div>
</body>
</html>'''

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"\n✅ HTML tree visualization saved to: {output_file}")
    except Exception as e:
        print(f"\n❌ Error saving HTML file: {e}")


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
    import os
    
    # Calculate default file path relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_file = os.path.join(script_dir, '..', 'var', 'timecamp_users.json')
    
    parser = argparse.ArgumentParser(
        description="Display TimeCamp group structure from var/timecamp_users.json"
    )
    parser.add_argument(
        "--file", 
        default=default_file,
        help=f"Path to the TimeCamp users JSON file (default: {default_file})"
    )
    parser.add_argument(
        "--detailed", 
        action="store_true",
        help="Show detailed user breakdown for each group"
    )
    parser.add_argument(
        "--html", 
        metavar="OUTPUT_FILE",
        help="Generate HTML visualization to the specified file"
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
        
        # Generate HTML if requested
        if args.html:
            save_html_tree(users, args.html)
        
    except FileNotFoundError:
        print(f"❌ Error: File '{args.file}' not found.")
        print("Make sure ../var/timecamp_users.json exists or specify a different file with --file")
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in file: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main() 