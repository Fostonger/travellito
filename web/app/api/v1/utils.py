"""Utility functions for the API."""

import os
import hmac
import hashlib
import time
from urllib.parse import parse_qsl
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

def verify_telegram_webapp_data(init_data: str, max_age_seconds: int = 86400) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    Verify the integrity and authenticity of Telegram WebApp initData.
    
    Args:
        init_data: The raw initData string from Telegram.WebApp.initData
        max_age_seconds: Maximum allowed age of the auth_date in seconds (default: 24 hours)
    
    Returns:
        Tuple of (is_valid, data_dict, error_message)
        - is_valid: Boolean indicating if the data is valid
        - data_dict: Dictionary of parsed data if valid, None otherwise
        - error_message: Error message if validation failed, None otherwise
    """
    # Parse the data string into a dictionary
    try:
        data_dict = dict(parse_qsl(init_data, keep_blank_values=True))
        logger.debug(f"Parsed initData: {data_dict}")
    except Exception as e:
        logger.error(f"Failed to parse initData: {e}")
        return False, None, f"Invalid initData format: {e}"
    
    # Check required fields
    if not data_dict.get("auth_date"):
        return False, None, "Missing auth_date in initData"
    
    if not data_dict.get("hash"):
        return False, None, "Missing hash in initData"
    
    # Check auth_date is not too old
    try:
        auth_date = int(data_dict["auth_date"])
        current_time = int(time.time())
        if current_time - auth_date > max_age_seconds:
            return False, None, f"Auth date too old: {auth_date}, current: {current_time}, max age: {max_age_seconds}"
    except ValueError:
        return False, None, "Invalid auth_date format"
    
    # Get the hash from the data and remove it for validation
    hash_value = data_dict.pop("hash")
    
    # Get bot token and generate secret key
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error("BOT_TOKEN environment variable is not set")
        return False, None, "BOT_TOKEN not configured"
    
    # Generate secret key by hashing the bot token
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    
    # Build the data check string
    # Sort the keys alphabetically as required by Telegram
    sorted_items = sorted(data_dict.items())
    data_check_string = "\n".join([f"{k}={v}" for k, v in sorted_items])
    
    logger.debug(f"Data check string: {data_check_string}")
    
    # Calculate HMAC-SHA-256 signature
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    logger.debug(f"Computed hash: {computed_hash}")
    logger.debug(f"Received hash: {hash_value}")
    
    # Use constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(computed_hash, hash_value)
    
    # Add the hash back to the data dictionary for completeness
    data_dict["hash"] = hash_value
    
    if not is_valid:
        return False, data_dict, "Invalid hash"
    
    return True, data_dict, None 