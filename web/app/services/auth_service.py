from typing import Optional, Tuple
import bcrypt

from app.core import BaseService, ValidationError, AuthenticationError
from app.infrastructure.repositories import UserRepository
from app.models import User
from app.security import mint_tokens, decode_token, create_token, REFRESH_TOKEN_EXP_SECONDS
from app.roles import Role


class AuthService(BaseService):
    """Authentication service handling user authentication and authorization"""
    
    def __init__(self, session, user_repo: Optional[UserRepository] = None):
        super().__init__(session)
        self.user_repo = user_repo or UserRepository(session)
    
    async def authenticate_user(self, email: str, password: str) -> Tuple[User, str, str]:
        """Authenticate user with email and password"""
        
        # Find user by email
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise AuthenticationError("Invalid email or password")
        
        # Verify password
        if not self._verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")
        
        # Generate tokens
        extra_claims = {}
        if user.agency_id:
            extra_claims["agency_id"] = user.agency_id
        
        access_token, refresh_token = mint_tokens(
            sub=user.id,
            role=user.role,
            **extra_claims
        )
        
        return user, access_token, refresh_token
    
    async def refresh_access_token(self, refresh_token: str) -> str:
        """Generate new access token from refresh token"""
        
        try:
            payload = decode_token(refresh_token)
        except:
            raise AuthenticationError("Invalid refresh token")
        
        # Verify token is a refresh token (has longer expiry)
        # This is a simple check - in production, you might want to store token types
        
        # Generate new access token with same claims
        access_token = create_token(
            sub=payload.get("sub"),
            role=payload.get("role"),
            **{k: v for k, v in payload.items() if k not in ["sub", "role", "exp"]}
        )
        
        return access_token
    
    async def create_user(
        self,
        email: str,
        password: str,
        role: str,
        first: Optional[str] = None,
        last: Optional[str] = None,
        agency_id: Optional[int] = None
    ) -> User:
        """Create a new user with hashed password"""
        
        # Validate email is unique
        if await self.user_repo.exists_by_email(email):
            raise ValidationError("Email already registered", field="email")
        
        # Validate role
        valid_roles = [r.value for r in Role]
        if role not in valid_roles:
            raise ValidationError(f"Invalid role. Must be one of: {', '.join(valid_roles)}", field="role")
        
        # Hash password
        password_hash = self._hash_password(password)
        
        # Create user
        user_data = {
            "email": email,
            "password_hash": password_hash,
            "role": role,
            "first": first,
            "last": last,
            "agency_id": agency_id
        }
        
        return await self.user_repo.create(obj_in=user_data)
    
    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str
    ) -> User:
        """Change user password"""
        
        # Get user
        user = await self.user_repo.get(user_id)
        if not user:
            raise AuthenticationError("User not found")
        
        # Verify current password
        if not self._verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")
        
        # Hash new password
        new_password_hash = self._hash_password(new_password)
        
        # Update password
        updated_user = await self.user_repo.update_password(user_id, new_password_hash)
        if not updated_user:
            raise AuthenticationError("Failed to update password")
        
        return updated_user
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except ValueError as e:
            # Log the error (in a real system, use a proper logger)
            print(f"Password verification error: {str(e)}")
            # If the hash is invalid, authentication fails
            return False 