"""Public service for public API operations."""

from __future__ import annotations

from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Dict, Any, Sequence, Optional
from sqlalchemy import select, func, and_, or_, Time
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.base import BaseService
from ..core.exceptions import NotFoundError, ValidationError
from ..models import (
    Tour, Departure, Purchase, TicketCategory, Referral, 
    LandlordCommission, City, TourCategory, TicketClass, 
    RepetitionType, Apartment, PurchaseItem, User
)
from ..infrastructure.repositories import TourRepository, DepartureRepository
from ..storage import presigned

HUNDRED = Decimal("100")  # module-level constant


class PublicService(BaseService):
    """Service for public API operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.tour_repository = TourRepository(session)
        self.departure_repository = DepartureRepository(session)
    
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
        """Search tours with filters and return discounted prices.
        
        Args:
            user_id: User ID for discount calculation
            city: City filter
            price_min: Minimum price filter
            price_max: Maximum price filter
            date_from: Start date filter
            date_to: End date filter
            time_from: Start time filter with timezone (format: HH:MM+TZ)
            time_to: End time filter with timezone (format: HH:MM+TZ)
            categories: List of category names to filter by
            duration_min: Minimum duration in minutes
            duration_max: Maximum duration in minutes
            limit: Maximum results
            offset: Results offset
            
        Returns:
            List of tours with discounted prices
        """
        # Parse time filters if provided
        time_filter_start_minutes = None
        time_filter_end_minutes = None
        
        if time_from:
            try:
                # Parse time in format HH:MM+TZ
                # We'll convert to minutes since midnight for simpler comparison
                parts = time_from.split('+')
                if len(parts) == 1:
                    parts = time_from.split('-')
                    if len(parts) > 1:
                        # Handle negative offset
                        tz_sign = -1
                        time_part = parts[0]
                        tz_part = parts[1]
                    else:
                        # No timezone specified, assume UTC
                        tz_sign = 1
                        time_part = time_from
                        tz_part = '00:00'
                else:
                    # Handle positive offset
                    tz_sign = 1
                    time_part = parts[0]
                    tz_part = parts[1]
                
                # Parse time component (HH:MM)
                hour, minute = map(int, time_part.split(':'))
                time_minutes = hour * 60 + minute
                
                # Parse timezone offset if present
                tz_hour, tz_minute = 0, 0
                if tz_part:
                    if ':' in tz_part:
                        tz_hour, tz_minute = map(int, tz_part.split(':'))
                    else:
                        tz_hour = int(tz_part)
                
                # Apply timezone offset to convert to UTC
                # Note: If client sends +03:00, we subtract 3 hours to get UTC time
                tz_offset_minutes = tz_sign * (tz_hour * 60 + tz_minute)
                time_filter_start_minutes = (time_minutes - tz_offset_minutes) % (24 * 60)
            except (ValueError, IndexError):
                # If parsing fails, ignore this filter
                pass

        if time_to:
            try:
                # Similar parsing for end time
                parts = time_to.split('+')
                if len(parts) == 1:
                    parts = time_to.split('-')
                    if len(parts) > 1:
                        tz_sign = -1
                        time_part = parts[0]
                        tz_part = parts[1]
                    else:
                        tz_sign = 1
                        time_part = time_to
                        tz_part = '00:00'
                else:
                    tz_sign = 1
                    time_part = parts[0]
                    tz_part = parts[1]
                
                hour, minute = map(int, time_part.split(':'))
                time_minutes = hour * 60 + minute
                
                tz_hour, tz_minute = 0, 0
                if tz_part:
                    if ':' in tz_part:
                        tz_hour, tz_minute = map(int, tz_part.split(':'))
                    else:
                        tz_hour = int(tz_part)
                
                tz_offset_minutes = tz_sign * (tz_hour * 60 + tz_minute)
                time_filter_end_minutes = (time_minutes - tz_offset_minutes) % (24 * 60)
            except (ValueError, IndexError):
                # If parsing fails, ignore this filter
                pass
        
        # Determine landlord for discount calculation
        landlord_id = None
        if user_id is not None:
            landlord_id = await self._last_referral_landlord_id(user_id)
        
        # We'll combine results from two sources:
        # 1. Tours with actual departures matching the time criteria
        # 2. Repeating tours that would have virtual departures at the requested time
        
        # ---- QUERY 1: Tours with actual departures ----
        # Don't use loader options here since we're only selecting IDs
        stmt1 = select(Tour.id)
        
        # Price filters (raw list price)
        if price_min is not None or price_max is not None:
            # Join with TicketCategory to filter by price
            price_subq = select(TicketCategory.tour_id, TicketCategory.price)\
                .where(TicketCategory.ticket_class_id == 0)\
                .subquery()
            stmt1 = stmt1.join(price_subq, Tour.id == price_subq.c.tour_id)
            
            if price_min is not None:
                stmt1 = stmt1.where(price_subq.c.price >= price_min)
            if price_max is not None:
                stmt1 = stmt1.where(price_subq.c.price <= price_max)
        
        # Date/time range - need to join departures
        if date_from or date_to or (time_filter_start_minutes is not None or time_filter_end_minutes is not None):
            stmt1 = stmt1.join(Departure, Departure.tour_id == Tour.id)
            
            # Date filtering
            if date_from:
                stmt1 = stmt1.where(Departure.starts_at >= date_from)
            if date_to:
                # Add one day to include the entire end date
                next_day = date_to + timedelta(days=1)
                stmt1 = stmt1.where(Departure.starts_at < next_day)
            
            # Time filtering with timezone awareness
            if time_filter_start_minutes is not None or time_filter_end_minutes is not None:
                # Extract minutes since midnight in UTC
                minutes_expr = func.extract('hour', Departure.starts_at) * 60 + func.extract('minute', Departure.starts_at)
                
                if time_filter_start_minutes is not None and time_filter_end_minutes is not None:
                    if time_filter_start_minutes <= time_filter_end_minutes:
                        # Normal case: e.g., 10:00 to 14:00
                        stmt1 = stmt1.where(
                            minutes_expr.between(time_filter_start_minutes, time_filter_end_minutes)
                        )
                    else:
                        # Wraparound case: e.g., 22:00 to 02:00
                        stmt1 = stmt1.where(
                            or_(
                                minutes_expr >= time_filter_start_minutes,
                                minutes_expr <= time_filter_end_minutes
                            )
                        )
                elif time_filter_start_minutes is not None:
                    stmt1 = stmt1.where(minutes_expr >= time_filter_start_minutes)
                elif time_filter_end_minutes is not None:
                    stmt1 = stmt1.where(minutes_expr <= time_filter_end_minutes)
        
        # ---- QUERY 2: Repeating tours with virtual departures ----
        stmt2 = select(Tour.id)
        
        # Apply same non-time filters
        if price_min is not None or price_max is not None:
            price_subq = select(TicketCategory.tour_id, TicketCategory.price)\
                .where(TicketCategory.ticket_class_id == 0)\
                .subquery()
            stmt2 = stmt2.join(price_subq, Tour.id == price_subq.c.tour_id)
            
            if price_min is not None:
                stmt2 = stmt2.where(price_subq.c.price >= price_min)
            if price_max is not None:
                stmt2 = stmt2.where(price_subq.c.price <= price_max)
        
        # Add repeating tour conditions
        # Only include repeating tours
        stmt2 = stmt2.where(Tour.repeat_type.isnot(None))
        
        # Time filtering for repeating tours
        if time_filter_start_minutes is not None or time_filter_end_minutes is not None:
            # Parse time from repeat_time column into minutes
            # Assuming repeat_time is stored as HH:MM
            repeat_time_minutes = func.extract('hour', func.cast(Tour.repeat_time, Time)) * 60 + \
                                 func.extract('minute', func.cast(Tour.repeat_time, Time))
            
            if time_filter_start_minutes is not None and time_filter_end_minutes is not None:
                if time_filter_start_minutes <= time_filter_end_minutes:
                    # Normal case: e.g., 10:00 to 14:00
                    stmt2 = stmt2.where(
                        repeat_time_minutes.between(time_filter_start_minutes, time_filter_end_minutes)
                    )
                else:
                    # Wraparound case: e.g., 22:00 to 02:00
                    stmt2 = stmt2.where(
                        or_(
                            repeat_time_minutes >= time_filter_start_minutes,
                            repeat_time_minutes <= time_filter_end_minutes
                        )
                    )
            elif time_filter_start_minutes is not None:
                stmt2 = stmt2.where(repeat_time_minutes >= time_filter_start_minutes)
            elif time_filter_end_minutes is not None:
                stmt2 = stmt2.where(repeat_time_minutes <= time_filter_end_minutes)
                
        # For weekly repeating tours, filter by day of week if we have date filters
        # This ensures we only get tours that repeat on the days included in our date range
        if date_from or date_to:
            # If we have a date filter, we need to make sure the repeating days match
            # For simplicity, we'll just include all weekly repeating tours for now
            # A more precise implementation would check the weekdays
            pass
        
        # Apply common filters to both queries
        
        # Category filter
        if categories and len(categories) > 0:
            # Use EXISTS subquery with join to avoid issues with JSON columns and distinct
            from sqlalchemy.sql import exists
            
            # Create a subquery to find tours with matching categories
            category_exists = exists().where(
                and_(
                    Tour.id == TourCategory.tour_id,
                    TourCategory.name.in_(categories)
                )
            ).correlate(Tour)
            
            stmt1 = stmt1.where(category_exists)
            stmt2 = stmt2.where(category_exists)
        
        # Duration filters (minutes)
        if duration_min is not None:
            stmt1 = stmt1.where(Tour.duration_minutes >= duration_min)
            stmt2 = stmt2.where(Tour.duration_minutes >= duration_min)
        if duration_max is not None:
            stmt1 = stmt1.where(Tour.duration_minutes <= duration_max)
            stmt2 = stmt2.where(Tour.duration_minutes <= duration_max)
        
        # City filter via City table if provided
        if city is not None:
            stmt1 = stmt1.join(City, City.id == Tour.city_id)
            stmt1 = stmt1.where(func.lower(City.name) == city.lower())
            
            stmt2 = stmt2.join(City, City.id == Tour.city_id)
            stmt2 = stmt2.where(func.lower(City.name) == city.lower())
        
        # Combine the two queries with UNION
        from sqlalchemy import union
        combined_stmt = union(stmt1, stmt2).alias()
        
        # Query to get unique tour IDs with limit and offset
        final_stmt = select(combined_stmt.c.id).distinct().order_by(combined_stmt.c.id.desc())
        final_stmt = final_stmt.limit(limit).offset(offset)
        
        # Get the tour IDs
        tour_ids = [id for id, in await self.session.execute(final_stmt)]
        
        # Then fetch full tour data
        if tour_ids:
            tours_stmt = select(Tour).options(
                selectinload(Tour.category),
                selectinload(Tour.tour_categories)
            ).where(Tour.id.in_(tour_ids)).order_by(Tour.id.desc())
            tours = (await self.session.scalars(tours_stmt)).unique().all()
        else:
            tours = []
        
        out: List[Dict[str, Any]] = []
        for t in tours:
            # chosen_comm = await self._chosen_commission(landlord_id, t.id, t.max_commission_pct)
            price = await self.session.scalar(select(TicketCategory.price).where(TicketCategory.tour_id == t.id, TicketCategory.ticket_class_id == 0))
            # price_net = self._discounted_price(price, t.max_commission_pct, chosen_comm)
            
            # Get categories from the many-to-many relationship
            categories = []
            if t.tour_categories:
                categories = [cat.name for cat in t.tour_categories]
            
            # For backward compatibility
            legacy_category = t.category.name if t.category is not None else None
            
            out.append({
                "id": t.id,
                "title": t.title,
                "price_raw": str(price) if price else "0",
                "price_net": str(price) if price else "0",
                "category": legacy_category,
                "categories": categories,
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
            Purchase.departure_id == dep.id
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
        
        # Get the tour to check its repetition type
        tour: Tour | None = await self.session.get(Tour, tour_id)
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
        
        # Calculate future departures based on repetition type
        if tour.repeat_type != "none" and tour.repeat_time:
            future_days = 30
            default_capacity = 10
            if deps:
                default_capacity = deps[0].capacity
            
            # Generate dates based on repetition type
            future_dates = []
            
            if tour.repeat_type == "daily":
                for i in range(future_days):
                    future_date = now.date() + timedelta(days=i)
                    future_datetime = datetime.combine(future_date, tour.repeat_time)
                    if future_datetime > now:
                        future_dates.append(future_datetime)
            
            elif tour.repeat_type == "weekly" and tour.repeat_weekdays:
                for i in range(future_days):
                    future_date = now.date() + timedelta(days=i)
                    weekday = future_date.weekday()
                    
                    if weekday in tour.repeat_weekdays:
                        future_datetime = datetime.combine(future_date, tour.repeat_time)
                        if future_datetime > now:
                            future_dates.append(future_datetime)
            
            # Filter out existing dates
            new_dates = [date for date in future_dates if date.date() not in existing_dates]
            
            # Add virtual departures
            for date in new_dates:
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
        """List tours with basic information."""
        stmt = (
            select(Tour)
            .order_by(Tour.id.desc())
            .limit(limit)
            .offset(offset)
        )
        tours = await self.session.scalars(stmt)
        
        result = []
        for tour in tours:
            # Get the standard price from TicketCategory with id=0
            price = await self.session.scalar(
                select(TicketCategory.price)
                .where(TicketCategory.tour_id == tour.id, TicketCategory.ticket_class_id == 0)
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
        tour_standart_price = await self.session.scalar(select(TicketCategory.price).where(TicketCategory.tour_id == tour_id, TicketCategory.ticket_class_id == 0))
        
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
            "categories": categories
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
    ) -> Dict[str, Any]:
        """Create a booking for a user.
        
        Args:
            departure_id: Departure ID (negative for virtual)
            items: List of {"category_id": int, "qty": int}
            user_id: User ID for discount calculation
            contact_name: Customer name
            contact_phone: Customer phone
            virtual_timestamp: Timestamp for virtual departures in milliseconds (UTC)
            
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
            one_week_ago = datetime.utcnow() - timedelta(days=7)
            
            if user.apartment_set_at > one_week_ago:
                # Less than a week - use the apartment_id for this purchase
                apartment_id = user.apartment_id
            else:
                # More than a week - clear the apartment_id from user
                user.apartment_id = None
                user.apartment_set_at = None
            
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
        
        return {
            "booking_id": purchase.id,
            "total_amount": str(purchase.amount),
            "seats_left": quote["seats_left"] - quote["total_qty"]
        }
