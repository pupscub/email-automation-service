#!/usr/bin/env python3
"""
Setup script for Email Automation Service
This script helps configure the application for first-time use.
"""

import os
import sys
import subprocess
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_command(command, description):
    logger.info(f"\n{description}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        logger.info(f"{description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"{description} failed: {e.stderr}")
        return False

def check_requirements():
    logger.info("Checking system requirements...")
    
    required_tools = {
        "python3": "python3 --version",
        "pip": "pip --version",
        "git": "git --version"
    }
    
    missing_tools = []
    for tool, command in required_tools.items():
        try:
            subprocess.run(command, shell=True, check=True, capture_output=True)
            logger.info(f"{tool} is installed")
        except subprocess.CalledProcessError:
            logger.error(f"{tool} is not installed")
            missing_tools.append(tool)
    
    if missing_tools:
        logger.warning(f"Please install the following tools: {', '.join(missing_tools)}")
        return False
    
    return True

def setup_virtual_environment():
    if not os.path.exists("venv"):
        if not run_command("python3 -m venv venv", "Creating virtual environment"):
            return False
    else:
        logger.info("Virtual environment already exists")
    
    if sys.platform == "win32":
        activate_command = "venv\\Scripts\\activate"
        pip_command = "venv\\Scripts\\pip"
    else:
        activate_command = "source venv/bin/activate"
        pip_command = "venv/bin/pip"
    
    if not run_command(f"{pip_command} install -r requirements.txt", "Installing Python packages"):
        return False
    
    return True

def setup_environment_file():
    env_file = Path(".env")
    example_file = Path(".env.example")
    
    if not env_file.exists():
        if example_file.exists():
            logger.info("\nSetting up environment configuration...")
            
            logger.info("\nYou need to configure the following in your .env file:")
            logger.info("1. Azure App Registration (CLIENT_ID, CLIENT_SECRET, TENANT_ID)")
            logger.info("2. OpenAI API Key (OPENAI_API_KEY)")
            logger.info("3. Webhook URL (WEBHOOK_URL - use ngrok for development)")
            
            copy_env = input("\nCopy .env.example to .env? (y/N): ").lower().strip()
            if copy_env == 'y':
                example_file.read_text()
                env_file.write_text(example_file.read_text())
                logger.info("Created .env file from template")
                logger.warning("Please edit .env file with your actual configuration values")
            else:
                logger.warning("You'll need to create a .env file manually")
        else:
            logger.error(".env.example file not found")
            return False
    else:
        logger.info(".env file already exists")
    
    return True

def check_ngrok():
    try:
        subprocess.run("ngrok version", shell=True, check=True, capture_output=True)
        logger.info("ngrok is installed")
        logger.info("\nTo start ngrok for webhook development:")
        logger.info("   ngrok http 8000")
        logger.info("   Then update WEBHOOK_URL in .env with the https URL")
        return True
    except subprocess.CalledProcessError:
        logger.warning("ngrok is not installed")
        logger.info("   Install from: https://ngrok.com/download")
        logger.info("   This is needed for webhook development")
        return False

def main():
    logger.info("Email Automation Service Setup")
    logger.info("=" * 40)
    
    if not check_requirements():
        logger.error("\nSetup failed due to missing requirements")
        sys.exit(1)
    
    if not setup_virtual_environment():
        logger.error("\nSetup failed during virtual environment setup")
        sys.exit(1)
    
    if not setup_environment_file():
        logger.error("\nSetup failed during environment configuration")
        sys.exit(1)
    
    check_ngrok()
    
    logger.info("\nSetup completed successfully!")
    logger.info("\nNext steps:")
    logger.info("1. Configure your .env file with actual values")
    logger.info("2. Set up Azure App Registration")
    logger.info("3. Start ngrok: ngrok http 8000")
    logger.info("4. Update WEBHOOK_URL in .env")
    logger.info("5. Run the application: python main.py")

if __name__ == "__main__":
    main()