"""
Validators for input data.
"""

import re
from typing import Optional, Callable


def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address string
        
    Returns:
        True if valid email, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password(password: str) -> bool:
    """
    Validate password strength.
    Minimum 6 characters with at least one letter and one digit.
    
    Args:
        password: Password string
        
    Returns:
        True if valid password, False otherwise
    """
    return len(password) >= 6 and any(c.isalpha() for c in password) and \
           any(c.isdigit() for c in password)


def validate_quantity(quantity: float) -> bool:
    """
    Validate transaction quantity.
    Must be positive.
    
    Args:
        quantity: Quantity value
        
    Returns:
        True if valid quantity, False otherwise
    """
    return quantity > 0


def validate_price(price: float) -> bool:
    """
    Validate transaction price.
    Must be positive.
    
    Args:
        price: Price value
        
    Returns:
        True if valid price, False otherwise
    """
    return price > 0
