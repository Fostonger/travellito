"""Admin service for platform administration logic."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Any, List
from secrets import token_hex
from sqlalchemy import select, func, delete as _delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.base import BaseService
from ..core.exceptions import NotFoundError, ConflictError
from ..models import Agency, Landlord, Tour, Departure, Purchase, ApiKey, User, Setting
from ..infrastructure.repositories import UserRepository, TourRepository
from .auth_service import AuthService


class AdminService(BaseService):
    """Service for admin operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.user_repository = UserRepository(session)
        self.tour_repository = TourRepository(session)
        self.auth_service = AuthService(session)

    async def set_tour_max_commission(self, tour_id: int, commission_pct: Decimal) -> Decimal:
        """Set maximum commission percentage for a tour.
        
        Args:
            tour_id: Tour ID
            commission_pct: Commission percentage (0-100)
            
        Returns:
            The set commission percentage
            
        Raises:
            NotFoundError: If tour not found
        """
        tour: Tour | None = await self.session.get(Tour, tour_id)
        if not tour:
            raise NotFoundError("Tour not found")
            
        tour.max_commission_pct = commission_pct
        await self.session.commit()
        
        return Decimal(tour.max_commission_pct)

    async def get_platform_metrics(self) -> Dict[str, Any]:
        """Get platform-wide metrics.
        
        Returns:
            Dictionary containing:
            - agencies: Total number of agencies
            - landlords: Total number of landlords
            - tours: Total number of tours
            - departures: Total number of departures
            - bookings: Total number of bookings
            - tickets_sold: Total tickets sold
            - sales_amount: Total sales amount
        """
        agencies = await self.session.scalar(select(func.count()).select_from(Agency)) or 0
        landlords = await self.session.scalar(select(func.count()).select_from(Landlord)) or 0
        tours = await self.session.scalar(select(func.count()).select_from(Tour)) or 0
        departures = await self.session.scalar(select(func.count()).select_from(Departure)) or 0
        bookings = await self.session.scalar(select(func.count()).select_from(Purchase)) or 0
        
        tickets_sold = await self.session.scalar(
            select(func.coalesce(func.sum(Purchase.qty), 0))
        ) or 0
        
        sales_amount_raw = await self.session.scalar(
            select(func.coalesce(func.sum(Purchase.amount), 0))
        ) or 0

        return {
            "agencies": agencies,
            "landlords": landlords,
            "tours": tours,
            "departures": departures,
            "bookings": bookings,
            "tickets_sold": tickets_sold,
            "sales_amount": Decimal(sales_amount_raw).quantize(Decimal("0.01")),
        }

    # API Key Management
    
    async def create_api_key(self, agency_id: int) -> ApiKey:
        """Create a new API key for an agency.
        
        Args:
            agency_id: Agency ID
            
        Returns:
            The created ApiKey object
            
        Raises:
            NotFoundError: If agency not found
        """
        agency: Agency | None = await self.session.get(Agency, agency_id)
        if not agency:
            raise NotFoundError("Agency not found")
            
        api_key = ApiKey(agency_id=agency_id, key=token_hex(32))
        self.session.add(api_key)
        await self.session.flush()
        await self.session.commit()
        
        return api_key

    async def list_api_keys(self, limit: int = 100, offset: int = 0) -> List[ApiKey]:
        """List all API keys.
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of ApiKey objects
        """
        stmt = (
            select(ApiKey)
            .order_by(ApiKey.created.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(stmt)
        return result.all()

    async def delete_api_key(self, key_id: int) -> None:
        """Delete an API key.
        
        Args:
            key_id: API key ID
            
        Raises:
            NotFoundError: If API key not found
        """
        stmt = _delete(ApiKey).where(ApiKey.id == key_id)
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            raise NotFoundError("API key not found")
        await self.session.commit()

    # Global settings management
    async def get_global_settings(self) -> Dict[str, Any]:
        """Get global settings.
        
        Returns:
            Dictionary of settings
        """
        # Get default max commission setting
        stmt = select(Setting).where(Setting.key == "default_max_commission")
        result = await self.session.scalar(stmt)
        default_max_commission = float(result.value) if result else 15.0  # Default value
        
        return {
            "default_max_commission": default_max_commission
        }
        
    async def update_global_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update global settings.
        
        Args:
            settings: Dictionary of settings to update
            
        Returns:
            Updated settings
        """
        result = {}
        
        # Update default max commission
        if "default_max_commission" in settings:
            await self._set_setting(
                "default_max_commission", 
                str(settings["default_max_commission"])
            )
            result["default_max_commission"] = settings["default_max_commission"]
            
        return result
    
    async def _set_setting(self, key: str, value: str) -> None:
        """Set a setting value.
        
        Args:
            key: Setting key
            value: Setting value
        """
        setting = await self.session.scalar(
            select(Setting).where(Setting.key == key)
        )
        
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value)
            self.session.add(setting)
            
        await self.session.commit()
    
    # QR Template settings
    async def get_qr_template_settings(self) -> Dict[str, Any]:
        """Get QR template settings.
        
        Returns:
            Dictionary with template settings or None
        """
        # Get QR template settings
        settings = {}
        
        # Get template URL
        template_url = await self.session.scalar(
            select(Setting).where(Setting.key == "qr_template_url")
        )
        if template_url:
            settings["template_url"] = template_url.value
            
            # Get position and size settings
            pos_x = await self.session.scalar(
                select(Setting).where(Setting.key == "qr_template_pos_x")
            )
            pos_y = await self.session.scalar(
                select(Setting).where(Setting.key == "qr_template_pos_y")
            )
            width = await self.session.scalar(
                select(Setting).where(Setting.key == "qr_template_width")
            )
            height = await self.session.scalar(
                select(Setting).where(Setting.key == "qr_template_height")
            )
            
            settings["position_x"] = int(pos_x.value) if pos_x else 50
            settings["position_y"] = int(pos_y.value) if pos_y else 50
            settings["width"] = int(width.value) if width else 200
            settings["height"] = int(height.value) if height else 200
            
        return settings if settings else None
    
    async def save_qr_template_settings(
        self, 
        template_url: str,
        position_x: int,
        position_y: int,
        width: int,
        height: int
    ) -> Dict[str, Any]:
        """Save QR template settings.
        
        Args:
            template_url: S3 object key for template image
            position_x: QR code X position in pixels
            position_y: QR code Y position in pixels
            width: QR code width in pixels
            height: QR code height in pixels
            
        Returns:
            Saved settings
        """
        await self._set_setting("qr_template_url", template_url)
        await self._set_setting("qr_template_pos_x", str(position_x))
        await self._set_setting("qr_template_pos_y", str(position_y))
        await self._set_setting("qr_template_width", str(width))
        await self._set_setting("qr_template_height", str(height))
        
        return {
            "template_url": template_url,
            "position_x": position_x,
            "position_y": position_y,
            "width": width,
            "height": height
        }

    # User Management
    
    async def create_user(
        self, 
        email: str, 
        password: str, 
        role: str, 
        agency_id: int | None = None
    ) -> User:
        """Create a new user.
        
        Args:
            email: User email
            password: User password (will be hashed)
            role: User role (admin, agency, landlord, manager)
            agency_id: Associated agency ID (optional)
            
        Returns:
            The created User object
            
        Raises:
            ConflictError: If email already exists
        """
        # Check if email already exists
        existing = await self.session.scalar(
            select(User).where(User.email == email)
        )
        if existing:
            raise ConflictError("Email already exists")
            
        # If role is agency and no agency_id provided, create a new agency
        if role == 'agency' and agency_id is None:
            # Create a new agency using email as name
            agency_name = f"Agency {email.split('@')[0]}"  # Use part before @ as agency name
            agency = Agency(name=agency_name)
            self.session.add(agency)
            await self.session.flush()  # Flush to get the ID
            agency_id = agency.id
            
        user = User(
            email=email,
            password_hash= self.auth_service._hash_password(password),
            role=role,
            agency_id=agency_id,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        
        return user

    async def list_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """List all users.
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of User objects
        """
        rows = await self.session.scalars(
            select(User)
            .order_by(User.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return rows.all()

    async def update_user(
        self,
        user_id: int,
        email: str | None = None,
        password: str | None = None,
        role: str | None = None,
        agency_id: int | None = None
    ) -> User:
        """Update a user.
        
        Args:
            user_id: User ID
            email: New email (optional)
            password: New password (optional, will be hashed)
            role: New role (optional)
            agency_id: New agency ID (optional)
            
        Returns:
            The updated User object
            
        Raises:
            NotFoundError: If user not found
        """
        user: User | None = await self.session.get(User, user_id)
        if not user:
            raise NotFoundError("User not found")
            
        if email is not None:
            user.email = email
        if password is not None:
            user.password_hash = self.auth_service._hash_password(password)
        if role is not None:
            user.role = role
        if agency_id is not None:
            user.agency_id = agency_id
            
        await self.session.commit()
        await self.session.refresh(user)
        
        return user

    async def delete_user(self, user_id: int) -> None:
        """Delete a user.
        
        Args:
            user_id: User ID
            
        Raises:
            NotFoundError: If user not found
        """
        user: User | None = await self.session.get(User, user_id)
        if not user:
            raise NotFoundError("User not found")
            
        await self.session.delete(user)
        await self.session.commit() 