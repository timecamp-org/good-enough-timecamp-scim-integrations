import pytest
import sys
import os

# Add scripts directory to path to allow importing display_timecamp_tree
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from display_timecamp_tree import render_html_tree, build_tree_structure

class TestHtmlGeneration:
    """Tests for HTML tree generation."""

    def test_render_simple_tree(self):
        """Test rendering a simple tree with one group and user."""
        tree = {'GroupA': {}}
        user_groups = {
            'GroupA': [{'timecamp_user_name': 'User 1', 'timecamp_email': 'u1@example.com', 'timecamp_role': 'user'}]
        }
        
        html_output = render_html_tree(tree, user_groups)
        
        assert 'GroupA' in html_output
        assert 'User 1' in html_output
        assert 'u1@example.com' in html_output
        assert 'folder-icon' in html_output
        assert '<details open>' in html_output
        
    def test_render_nested_tree(self):
        """Test rendering a nested tree structure."""
        tree = {'Parent': {'Child': {}}}
        user_groups = {
            'Parent': [],
            'Parent/Child': [{'timecamp_user_name': 'User 2', 'timecamp_email': 'u2@example.com', 'timecamp_role': 'supervisor'}]
        }
        
        html_output = render_html_tree(tree, user_groups)
        
        assert 'Parent' in html_output
        assert 'Child' in html_output
        assert 'User 2' in html_output
        assert '👑' in html_output  # Supervisor icon
        
        # Verify nesting order roughly
        assert html_output.find('Parent') < html_output.find('Child')

    def test_escaping(self):
        """Test that HTML special characters are escaped."""
        tree = {'Group<B>': {}}
        user_groups = {
            'Group<B>': [{'timecamp_user_name': 'User & Name', 'timecamp_email': 'u&n@example.com', 'timecamp_role': 'user'}]
        }
        
        html_output = render_html_tree(tree, user_groups)
        
        assert 'Group&lt;B&gt;' in html_output
        assert 'User &amp; Name' in html_output
        
    def test_empty_tree(self):
        """Test rendering an empty tree."""
        html_output = render_html_tree({}, {})
        assert html_output == ""

