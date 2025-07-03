from app.core import BaseError


def get_agency_id(user: dict) -> int:
    """Extract agency ID from user token"""
    agency_id = user.get("agency_id")
    if not agency_id:
        raise BaseError("No agency associated with user", status_code=403)
    return int(agency_id)


def get_user_id(user: dict) -> int:
    """Extract user ID from user token"""
    user_id = user.get("sub")
    if not user_id:
        raise BaseError("Invalid user token", status_code=401)
    return int(user_id)


def get_user_role(user: dict) -> str:
    """Extract user role from user token"""
    role = user.get("role")
    if not role:
        raise BaseError("Invalid user token", status_code=401)
    return role 