"""Public service for public API operations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, date, time
from decimal import Decimal
from typing import List, Dict, Any, Sequence, Optional
from sqlalchemy import select, func, and_, or_, Time, Text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

# Set up logger
logger = logging.getLogger(__name__)

from ..core.base import BaseService
from ..core.exceptions import NotFoundError, ValidationError
from ..models import (
    Tour, Departure, Purchase, TicketCategory, Referral, 
    LandlordCommission, City, TourCategory, TicketClass, 
    RepetitionType, Apartment, PurchaseItem, User
)
from ..infrastructure.repositories import TourRepository, DepartureRepository
from ..storage import presigned
from .tour_filter_service import TourFilterService

from app.infrastructure.metrika import track_async_event

HUNDRED = Decimal("100")  # module-level constant


class PublicService(BaseService):
    """Service for public API operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.tour_repository = TourRepository(session)
        self.departure_repository = DepartureRepository(session)
        self.tour_filter_service = TourFilterService(session)
    
    # Helper Methods
    
    async def _last_referral_landlord_id(self, user_id: int) -> int | None:
        """Return landlord_id of the most recent referral for user_id or None."""
        stmt = (
            select(Referral.landlord_id)
            .where(Referral.user_id == user_id)
            .order_by(Referral.ts.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)
    
    async def _chosen_commission(
        self, landlord_id: int | None, tour_id: int, max_commission: Decimal
    ) -> Decimal:
        """Return commission_pct chosen by landlord for tour (or 0 if none).
        
        Ensures it does not exceed max_commission.
        """
        if landlord_id is None:
            return Decimal("0")
        
        stmt = select(LandlordCommission.commission_pct).where(
            LandlordCommission.landlord_id == landlord_id,
            LandlordCommission.tour_id == tour_id,
        )
        pct: Decimal | None = await self.session.scalar(stmt)
        if pct is None:
            return Decimal("0")
        return min(pct, max_commission)
    
    def _discounted_price(
        self, raw_price: Decimal, max_commission: Decimal, chosen_commission: Decimal
    ) -> Decimal:
        """Return price applying discount given max and chosen commission."""
        discount_pct = (max_commission - chosen_commission).quantize(Decimal("0.01"))
        if discount_pct < 0:
            discount_pct = Decimal("0")
        return (raw_price * (HUNDRED - discount_pct) / HUNDRED).quantize(Decimal("0.01"))
    
    async def _materialize_virtual_departure(
        self, tour_id: int, starts_at: datetime, capacity: int = 10
    ) -> Departure:
        """Create a real departure from virtual departure data.
        
        This is used when a user tries to book a virtual departure that doesn't
        exist in the database yet. We materialize it on demand.
        """
        try:
            # First check if a departure at this exact time already exists
            stmt = select(Departure).where(
                Departure.tour_id == tour_id,
                Departure.starts_at == starts_at
            )
            existing = await self.session.scalar(stmt)
            if existing:
                return existing
            
            # Verify the tour exists
            tour = await self.session.get(Tour, tour_id)
            if not tour:
                raise ValidationError(f"Tour with ID {tour_id} not found")
            
            # Log the time being used for debugging
            print(f"Creating departure for tour {tour_id} at time: {starts_at.isoformat()}")
            
            # Create a new departure with the exact time from the virtual departure
            departure = Departure(
                tour_id=tour_id,
                starts_at=starts_at,
                capacity=capacity,
                modifiable=True
            )
            
            self.session.add(departure)
            await self.session.flush()
            await self.session.commit()
            
            return departure
        except Exception as e:
            # Roll back the transaction if there was an error
            await self.session.rollback()
            raise ValidationError(f"Failed to materialize virtual departure: {e}")
    
    # Tour Search and Listing
    
    async def search_tours(
        self,
        user_id: int | None,
        city: str | None = None,
        price_min: Decimal | None = None,
        price_max: Decimal | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        time_from: str | None = None,
        time_to: str | None = None,
        categories: List[str] | None = None,
        duration_min: int | None = None,
        duration_max: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Search tours with filters and return discounted prices."""
        # Determine landlord for discount calculation
        landlord_id = None
        if user_id is not None:
            landlord_id = await self._last_referral_landlord_id(user_id)
        
        # Use the new TourFilterService to get filtered tour IDs
        tour_ids = await self.tour_filter_service.filter_tours(
            city=city,
            price_min=price_min,
            price_max=price_max,
            date_from=date_from,
            date_to=date_to,
            time_from=time_from,
            time_to=time_to,
            categories=categories,
            duration_min=duration_min,
            duration_max=duration_max,
            limit=limit,
            offset=offset
        )
        
        # Fetch full tour data
        if tour_ids:
            tours_stmt = select(Tour).options(
                selectinload(Tour.tour_categories),
                selectinload(Tour.images)  # Also load images
            ).where(Tour.id.in_(tour_ids)).order_by(Tour.id.desc())
            tours = (await self.session.scalars(tours_stmt)).unique().all()
        else:
            tours = []
        
        # Format output data
        out: List[Dict[str, Any]] = []
        for t in tours:
            price = await self.session.scalar(select(TicketCategory.price).where(TicketCategory.tour_id == t.id, TicketCategory.ticket_class_id == 1))
            
            # Get categories
            categories = []
            if t.tour_categories:
                categories = [cat.name for cat in t.tour_categories]
            
            # Get images
            images = []
            if t.images:
                images = [
                    {"key": img.key, "url": presigned(img.key)}
                    for img in t.images
                ]
            
            out.append({
                "id": t.id,
                "title": t.title,
                "price_raw": str(price) if price else "0",
                "price_net": str(price) if price else "0",
                "categories": categories,
                "images": images,  # Add images to the response
                "address": t.address  # Add address for departure info
            })
        
        return out
    
    async def get_tour_categories(
        self, tour_id: int, user_id: int | None = None
    ) -> List[Dict[str, Any]]:
        """Get ticket categories for a tour with discounted prices.
        
        Args:
            tour_id: Tour ID
            user_id: User ID for discount calculation
            
        Returns:
            List of categories with prices
            
        Raises:
            NotFoundError: If tour not found
        """
        tour: Tour | None = await self.session.get(Tour, tour_id)
        if not tour:
            raise NotFoundError("Tour not found")
        
        landlord_id = None
        chosen_comm = None
        if user_id is not None:
            landlord_id = await self._last_referral_landlord_id(user_id)
            chosen_comm = await self._chosen_commission(landlord_id, tour_id, tour.max_commission_pct)
        
        categories = (
            await self.session.scalars(
                select(TicketCategory).where(TicketCategory.tour_id == tour_id)
            )
        ).all()
        
        out: List[Dict[str, Any]] = []
        for c in categories:
            if chosen_comm is not None:
                net = self._discounted_price(c.price, tour.max_commission_pct, chosen_comm)
            else:
                net = c.price
            out.append({
                "id": c.id,
                "name": c.name,
                "price_raw": str(c.price),
                "price_net": str(net),
            })
        
        return out
    
    async def calculate_price_quote(
        self,
        departure_id: int,
        items: List[Dict[str, int]],
        user_id: int,
        virtual_timestamp: int | None = None,
    ) -> Dict[str, Any]:
        """Calculate price quote for a booking.
        
        Args:
            departure_id: Departure ID (negative for virtual)
            items: List of {"category_id": int, "qty": int}
            user_id: User ID for discount calculation
            virtual_timestamp: Timestamp for virtual departures in milliseconds (UTC)
            
        Returns:
            Quote with total price and availability
        """
        # Validate items
        if not items:
            raise ValidationError("No items provided in the quote request")
            
        # Handle virtual departures
        if departure_id < 0:
            try:
                tour_id, starts_at = await self._decode_virtual_departure(
                    departure_id, virtual_timestamp
                )
                dep = await self._materialize_virtual_departure(tour_id, starts_at)
            except Exception as e:
                raise ValidationError(f"Failed to process virtual departure: {e}")
        else:
            dep: Departure | None = await self.session.get(Departure, departure_id)
            if not dep:
                raise NotFoundError("Departure not found")
        
        # Calculate capacity
        taken_stmt = select(func.coalesce(func.sum(Purchase.qty), 0)).where(
            Purchase.departure_id == dep.id,
            Purchase.status.notin_(["cancelled", "rejected"])
        )
        taken: int = await self.session.scalar(taken_stmt) or 0
        remaining = dep.capacity - taken
        
        # Get tour for commission calculation
        tour: Tour | None = await self.session.get(Tour, dep.tour_id)
        if tour is None:
            raise NotFoundError("Tour not found")
        
        landlord_id = await self._last_referral_landlord_id(user_id)
        chosen_comm = await self._chosen_commission(landlord_id, tour.id, tour.max_commission_pct)
        
        # Fetch categories
        cats = (
            await self.session.scalars(
                select(TicketCategory).where(TicketCategory.tour_id == dep.tour_id)
            )
        ).all()
        cat_map = {c.id: c for c in cats}
        
        total_net = Decimal("0")
        total_qty = 0
        items_out = []
        for item in items:
            cat_id = item.get("category_id")
            qty = item.get("qty", 0)
            
            if not cat_id or not isinstance(cat_id, int):
                raise ValidationError("Invalid category_id format")
                
            if not qty or not isinstance(qty, int) or qty <= 0:
                raise ValidationError("Invalid quantity format")
                
            cat = cat_map.get(cat_id)
            if not cat:
                raise ValidationError(f"Invalid category id: {cat_id}")
            
            total_net += cat.price * qty
            total_qty += qty
            items_out.append({
                "category_id": cat.id,
                "qty": qty,
                "amount": cat.price * qty
            })
        
        if total_qty > dep.capacity:
            raise ValidationError("Not enough seats available")
        
        return {
            "total_net": total_net.quantize(Decimal("0.01")),
            "seats_left": max(remaining, 0),
            "departure_id": dep.id,
            "total_qty": total_qty,
            "items": items_out
        }
    
    async def _decode_virtual_departure(
        self, departure_id: int, virtual_timestamp: int | None
    ) -> tuple[int, datetime]:
        """Decode virtual departure ID to extract tour_id and timestamp.
        
        Args:
            departure_id: The virtual departure ID (negative)
            virtual_timestamp: Client-side timestamp in milliseconds (UTC time)
        """
        try:
            # The new format is just the negative tour ID
            tour_id = abs(departure_id)
            
            # Verify the tour exists
            tour = await self.session.get(Tour, tour_id)
            if tour is None:
                # Fallback to the old format for backward compatibility
                encoded_id = str(abs(departure_id))
                
                # Try to find a valid tour ID by checking different prefixes
                tour_id = None
                for prefix_length in range(1, 6):  # Try 1-5 digit tour IDs
                    if prefix_length >= len(encoded_id):
                        continue
                    
                    potential_tour_id = int(encoded_id[:prefix_length])
                    tour = await self.session.get(Tour, potential_tour_id)
                    if tour is not None:
                        tour_id = potential_tour_id
                        break
                
                if tour_id is None:
                    # Fallback: try to extract tour ID from the first digit
                    if len(encoded_id) > 0:
                        potential_tour_id = int(encoded_id[0])
                        tour = await self.session.get(Tour, potential_tour_id)
                        if tour is not None:
                            tour_id = potential_tour_id
                
                if tour_id is None:
                    raise ValidationError("Could not determine tour from virtual departure ID")
            
            # Use provided timestamp or current time
            if virtual_timestamp:
                # JavaScript timestamps are UTC milliseconds since epoch
                # We should use utcfromtimestamp to interpret it correctly as UTC
                utc_time = datetime.utcfromtimestamp(virtual_timestamp / 1000)
                
                # No need for additional timezone adjustment since the timestamp is already in UTC
                # The JavaScript Date.getTime() already accounts for this
                starts_at = utc_time
                
                print(f"Virtual timestamp conversion: {virtual_timestamp}, UTC time: {utc_time.isoformat()}")
            else:
                starts_at = datetime.utcnow()
            
            return tour_id, starts_at
            
        except Exception as e:
            raise ValidationError(f"Invalid virtual departure ID: {e}")
    
    async def get_tour_departures(
        self, tour_id: int, limit: int = 30, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get upcoming departures for a tour including virtual ones.
        
        Args:
            tour_id: Tour ID
            limit: Maximum results
            offset: Results offset
            
        Returns:
            List of departures with availability
            
        Raises:
            NotFoundError: If tour not found
        """
        
        now = datetime.utcnow()
        
        # Load tour with repetitions if any
        stmt_tour = select(Tour).options(selectinload(Tour.repetitions)).where(Tour.id == tour_id)
        tour: Tour | None = await self.session.scalar(stmt_tour)
        if tour is None:
            raise NotFoundError("Tour not found")
        
        # Get existing departures
        stmt = (
            select(Departure)
            .where(Departure.tour_id == tour_id, Departure.starts_at >= now)
            .order_by(Departure.starts_at)
        )
        deps = (await self.session.scalars(stmt)).all()
        
        # Create list of all departure dates
        all_departures = []
        
        # Process existing departures
        existing_dates = set()
        existing_datetimes = set()
        for dep in deps:
            taken = await self.departure_repository.get_seats_taken(dep.id)
            all_departures.append({
                "id": dep.id,
                "starts_at": dep.starts_at,
                "capacity": dep.capacity,
                "seats_left": max(dep.capacity - taken, 0),
                "is_existing": True
            })
            existing_dates.add(dep.starts_at.date())
            existing_datetimes.add(dep.starts_at.replace(second=0, microsecond=0))
        
        # Calculate future departures based on repetition rules
        rules: list[dict[str, Any]] = []
        if getattr(tour, "repetitions", None):
            for r in tour.repetitions:
                if not r.repeat_time:
                    continue
                rules.append({
                    "type": r.repeat_type,
                    "weekdays": r.repeat_weekdays or [],
                    "time": r.repeat_time,
                })
        else:
            # Fallback to legacy single repetition on tour
            if tour.repeat_type and tour.repeat_type != "none" and tour.repeat_time:
                rules.append({
                    "type": tour.repeat_type,
                    "weekdays": tour.repeat_weekdays or [],
                    "time": tour.repeat_time,
                })
        
        if rules:
            future_days = 30
            default_capacity = 10
            if deps:
                default_capacity = deps[0].capacity
            
            future_dates: list[datetime] = []
            for rule in rules:
                rtype = rule["type"]
                rtime: time = rule["time"]
                if rtype == "daily":
                    for i in range(future_days):
                        future_date = now.date() + timedelta(days=i)
                        future_datetime = datetime.combine(future_date, rtime)
                        if future_datetime > now:
                            future_dates.append(future_datetime)
                elif rtype == "weekly":
                    weekdays = rule["weekdays"] or []
                    for i in range(future_days):
                        future_date = now.date() + timedelta(days=i)
                        weekday = future_date.weekday()
                        if weekday in weekdays:
                            future_datetime = datetime.combine(future_date, rtime)
                            if future_datetime > now:
                                future_dates.append(future_datetime)
            
            # Filter out dates that already have existing materialized departures for that date
            # and deduplicate identical datetimes (from overlapping rules)
            seen_virtual = set()
            for date in future_dates:
                dt_key = date.replace(second=0, microsecond=0)
                if dt_key in existing_datetimes:
                    continue
                if dt_key in seen_virtual:
                    continue
                seen_virtual.add(dt_key)
                all_departures.append({
                    "id": None,
                    "starts_at": date,
                    "capacity": default_capacity,
                    "seats_left": default_capacity,
                    "is_existing": False
                })
        
        # Sort and paginate
        all_departures.sort(key=lambda x: x["starts_at"])
        paginated_departures = all_departures[offset:offset+limit]
        
        # Format response
        out = []
        for dep in paginated_departures:
            out.append({
                "id": dep["id"],
                "starts_at": dep["starts_at"].isoformat() if dep["starts_at"] else None,
                "capacity": dep["capacity"],
                "seats_left": dep["seats_left"],
                "is_virtual": not dep["is_existing"]
            })
        
        return out
    
    # Listing Methods
    
    async def list_cities(self) -> List[Dict[str, Any]]:
        """List all cities for dropdown selection."""
        stmt = select(City.id, City.name).order_by(City.name)
        result = await self.session.execute(stmt)
        return [{"id": id, "name": name} for id, name in result]
    
    async def list_tour_categories(self) -> List[Dict[str, Any]]:
        """List all tour categories for dropdown selection."""
        stmt = select(TourCategory.id, TourCategory.name).order_by(TourCategory.name)
        result = await self.session.execute(stmt)
        return [{"id": id, "name": name} for id, name in result]
    
    async def list_ticket_classes(self) -> List[Dict[str, Any]]:
        """List all ticket classes for dropdown selection."""
        stmt = select(TicketClass.id, TicketClass.code, TicketClass.human_name).order_by(
            TicketClass.human_name
        )
        result = await self.session.execute(stmt)
        return [{"id": id, "code": code, "name": name} for id, code, name in result]
    
    async def list_repetition_types(self) -> List[Dict[str, Any]]:
        """Return all repetition types for dropdown selection."""
        stmt = select(RepetitionType).order_by(RepetitionType.id)
        rows = await self.session.scalars(stmt)
        return [{"id": r.id, "name": r.name} for r in rows.all()]
    
    async def create_landlord(
        self, 
        name: str, 
        email: str, 
        password: str
    ) -> Dict[str, Any]:
        """Create a new landlord user and landlord record.
        
        Args:
            name: Landlord name
            email: Email address
            password: Password (will be hashed)
            
        Returns:
            Dictionary with user and landlord info
            
        Raises:
            ValidationError: If email already exists
        """
        from app.services.auth_service import AuthService
        from app.models import Landlord
        from app.roles import Role
        
        # Create user with landlord role
        auth_service = AuthService(self.session)
        user = await auth_service.create_user(
            email=email,
            password=password,
            role=Role.landlord.value,
            first=name
        )
        
        # Create landlord record
        landlord = Landlord(name=name, user_id=user.id)
        self.session.add(landlord)
        await self.session.commit()
        
        return {
            "user_id": user.id,
            "landlord_id": landlord.id,
            "name": name,
            "email": email
        }
    
    async def list_tours(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List tours with basic information - only tours with upcoming departures."""
        from datetime import datetime
        from ..models import TourRepetition
        
        # Get current time for filtering
        now = datetime.utcnow()
        
        # Subquery for tours with upcoming materialized departures
        upcoming_departures_subq = (
            select(Departure.tour_id)
            .where(Departure.starts_at >= now)
            .subquery()
        )
        
        # Subquery for tours with repetitions (virtual departures)
        virtual_departures_subq = (
            select(TourRepetition.tour_id)
            .where(TourRepetition.repeat_time.isnot(None))
            .subquery()
        )
        
        # Main query: get tours that have either upcoming departures or repetitions
        stmt = (
            select(Tour)
            .where(
                or_(
                    Tour.id.in_(select(upcoming_departures_subq.c.tour_id)),
                    Tour.id.in_(select(virtual_departures_subq.c.tour_id))
                )
            )
            .order_by(Tour.id.desc())
            .limit(limit)
            .offset(offset)
        )
        tours = await self.session.scalars(stmt)
        
        result = []
        for tour in tours:
            # Get the standard price from TicketCategory with ticket_class_id=1
            price = await self.session.scalar(
                select(TicketCategory.price)
                .where(TicketCategory.tour_id == tour.id, TicketCategory.ticket_class_id == 1)
            )
            result.append({
                "id": tour.id,
                "title": tour.title,
                "price": str(price) if price else None
            })
        
        return result
    async def get_tour_detail(self, tour_id: int) -> Dict[str, Any]:
        """Get full tour details including images.
        
        Args:
            tour_id: Tour ID
            
        Returns:
            Tour details dictionary
            
        Raises:
            NotFoundError: If tour not found
        """
        # Use selectinload to eagerly load the images relationship and categories
        stmt = select(Tour).options(
            selectinload(Tour.images),
            selectinload(Tour.tour_categories)
        ).where(Tour.id == tour_id)
        
        tour = await self.session.scalar(stmt)
        tour_standart_price = await self.session.scalar(select(TicketCategory.price).where(TicketCategory.tour_id == tour_id, TicketCategory.ticket_class_id == 1))
        
        if not tour:
            raise NotFoundError("Tour not found")
        
        # Get categories from the many-to-many relationship
        categories = []
        if tour.tour_categories:
            categories = [cat.name for cat in tour.tour_categories]
        
        return {
            "id": tour.id,
            "title": tour.title,
            "description": tour.description,
            "price": str(tour_standart_price),
            "duration_minutes": tour.duration_minutes,
            "images": [
                {"key": img.key, "url": presigned(img.key)}
                for img in tour.images
            ],
            "categories": categories,
            "address": tour.address  # Add address for departure info
        }
    
    async def get_departure_availability(self, departure_id: int) -> Dict[str, Any]:
        """Get seats left for a departure.
        
        Args:
            departure_id: Departure ID
            
        Returns:
            Availability information
            
        Raises:
            NotFoundError: If departure not found
        """
        dep: Departure | None = await self.session.get(Departure, departure_id)
        if not dep:
            raise NotFoundError("Departure not found")
        
        # Get bookings count
        taken = await self.session.scalar(
            select(func.coalesce(func.sum(Purchase.qty), 0))
            .where(Purchase.departure_id == departure_id)
        ) or 0
        
        return {
            "departure_id": departure_id,
            "capacity": dep.capacity,
            "seats_taken": taken,
            "seats_left": max(dep.capacity - taken, 0)
        }

    async def create_booking(
        self,
        departure_id: int,
        items: List[Dict[str, int]],
        user_id: int,
        contact_name: str,
        contact_phone: str,
        virtual_timestamp: int | None = None,
        client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a booking for a user.
        
        Args:
            departure_id: Departure ID (negative for virtual)
            items: List of {"category_id": int, "qty": int}
            user_id: User ID for discount calculation
            contact_name: Customer name
            contact_phone: Customer phone
            virtual_timestamp: Timestamp for virtual departures in milliseconds (UTC)
            client_id: Client ID for analytics tracking
        Returns:
            Dict with booking details
            
        Raises:
            NotFoundError: If departure or categories not found
            ValidationError: If validation fails
            ConflictError: If not enough seats
        """
        from ..models import Purchase, PurchaseItem, User
        from datetime import datetime, timedelta

        # Validate inputs
        if not items:
            raise ValidationError("No items provided in the booking request")
        
        # First calculate the quote to validate availability and get prices
        try:
            quote = await self.calculate_price_quote(
                departure_id=departure_id,
                items=items,
                user_id=user_id,
                virtual_timestamp=virtual_timestamp
            )
        except Exception as e:
            raise ValidationError(f"Failed to calculate price quote: {e}")
        
        # Get the departure
        departure = await self.session.get(Departure, quote["departure_id"])
        if not departure:
            raise NotFoundError("Departure not found")
            
        # Get the user
        user = await self.session.get(User, user_id)
        if not user:
            raise NotFoundError("User not found")
            
        # Update user contact info if provided
        if contact_name:
            user.first = contact_name
        if contact_phone:
            user.phone = contact_phone
        
        # Handle apartment_id referral logic
        apartment_id = None
        if user.apartment_id and user.apartment_set_at:
            # Check if apartment_id was set less than a week ago
            one_week_ago = datetime.utcnow() - timedelta(days=14)
            
            if user.apartment_set_at > one_week_ago:
                # Less than a week - use the apartment_id for this purchase
                apartment_id = user.apartment_id
            
        # Create the purchase record
        purchase = Purchase(
            departure_id=departure.id,
            user_id=user_id,
            qty=quote["total_qty"],
            amount=Decimal(quote["total_net"]),
            status="pending",
            viewed=False,
            apartment_id=apartment_id
        )
        
        self.session.add(purchase)
        await self.session.flush()  # To get the purchase ID
        
        # Create purchase items
        for item_data in quote["items"]:
            item = PurchaseItem(
                purchase_id=purchase.id,
                category_id=item_data["category_id"],
                qty=item_data["qty"],
                amount=Decimal(item_data["amount"])
            )
            self.session.add(item)
            
        # Commit the transaction
        await self.session.commit()
        
        if client_id:
            track_async_event(
                client_id=client_id,
                action="booking_created",
                ec="booking",
                user_id=user_id,
                booking_id=purchase.id,
                departure_id=departure_id,
                apartment_id=apartment_id,
                total_price=purchase.amount
            )
        # Send Telegram confirmation asynchronously
        try:
            from .notification_service import NotificationService
            notif_svc = NotificationService(self.session)
            await notif_svc.send_booking_confirmation(purchase.id)
        except Exception as exc:
            # Log but do not fail booking creation if notification fails
            logger.exception("Failed to send Telegram booking confirmation: %s", exc)
        
        # Notify admins about the new booking
        try:
            from .notification_service import NotificationService
            notif_svc = NotificationService(self.session)
            await notif_svc.notify_admins_new_booking(purchase.id)
        except Exception as exc:
            # Log but do not fail booking creation if admin notification fails
            logger.exception("Failed to notify admins about new booking: %s", exc)
        
        return {
            "booking_id": purchase.id,
            "total_amount": str(purchase.amount),
            "seats_left": quote["seats_left"] - quote["total_qty"]
        }
