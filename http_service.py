#!/usr/bin/env python3

import os
import subprocess
import json
from flask import Flask, request, jsonify
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of available Python scripts in the project
AVAILABLE_SCRIPTS = [
    'fetch_bamboohr.py',
    'fetch_azuread.py', 
    'fetch_ldap.py',
    'fetch_factorialhr.py',
    'prepare_timecamp_json_from_fetch.py',
    'timecamp_sync_users.py',
    'timecamp_sync_time_off.py',
    'scripts/display_timecamp_tree.py',
    'scripts/remove_empty_groups.py'
]

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "timecamp-scim-http"})

@app.route('/scripts', methods=['GET'])
def list_scripts():
    """List all available scripts"""
    return jsonify({"available_scripts": AVAILABLE_SCRIPTS})

@app.route('/run', methods=['POST'])
def run_script():
    """
    Execute a Python script with arguments
    
    Expected JSON payload:
    {
        "script": "fetch_bamboohr.py",
        "args": ["--debug", "--dry-run"]
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        script = data.get('script')
        args = data.get('args', [])
        
        if not script:
            return jsonify({"error": "Script name is required"}), 400
            
        # Validate script exists in our allowed list
        if script not in AVAILABLE_SCRIPTS:
            return jsonify({
                "error": f"Script '{script}' not allowed",
                "available_scripts": AVAILABLE_SCRIPTS
            }), 400
            
        # Validate script file exists
        if not os.path.exists(script):
            return jsonify({"error": f"Script file '{script}' not found"}), 404
            
        # Prepare command
        command = ['python', script] + args
        
        logger.info(f"Executing command: {' '.join(command)}")
        
        # Execute the script
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        response = {
            "script": script,
            "args": args,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }
        
        status_code = 200 if result.returncode == 0 else 500
        
        logger.info(f"Command completed with return code: {result.returncode}")
        
        return jsonify(response), status_code
        
    except subprocess.TimeoutExpired:
        logger.error("Script execution timed out")
        return jsonify({"error": "Script execution timed out (5 minutes)"}), 408
        
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON payload"}), 400
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/run/<script_name>', methods=['POST'])
def run_script_by_path(script_name):
    """
    Alternative endpoint to run script by URL path
    
    POST /run/fetch_bamboohr.py
    Body: {"args": ["--debug"]}
    """
    try:
        data = request.get_json() or {}
        args = data.get('args', [])
        
        # Use the script name from URL path
        return run_script_internal(script_name, args)
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

def run_script_internal(script, args):
    """Internal function to run script (shared logic)"""
    # Validate script exists in our allowed list
    if script not in AVAILABLE_SCRIPTS:
        return jsonify({
            "error": f"Script '{script}' not allowed",
            "available_scripts": AVAILABLE_SCRIPTS
        }), 400
        
    # Validate script file exists
    if not os.path.exists(script):
        return jsonify({"error": f"Script file '{script}' not found"}), 404
        
    # Prepare command
    command = ['python', script] + args
    
    logger.info(f"Executing command: {' '.join(command)}")
    
    # Execute the script
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=300  # 5 minute timeout
    )
    
    response = {
        "script": script,
        "args": args,
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.returncode == 0
    }
    
    status_code = 200 if result.returncode == 0 else 500
    
    logger.info(f"Command completed with return code: {result.returncode}")
    
    return jsonify(response), status_code

if __name__ == '__main__':
    # Run the Flask app
    app.run(host='0.0.0.0', port=8181, debug=False) 