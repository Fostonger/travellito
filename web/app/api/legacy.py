from fastapi import APIRouter

# Legacy router to maintain backward compatibility during migration
# This will include all the old endpoints that haven't been refactored yet
legacy_router = APIRouter()

# TODO: Include old endpoints here temporarily during migration
# Once all endpoints are refactored, this file can be removed 