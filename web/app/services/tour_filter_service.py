"""Tour filtering service for search operations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy import select, func, and_, or_, Time, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import exists

from ..core.base import BaseService
from ..models import (
    Tour, Departure, TicketCategory, City, TourCategory, TourCategoryAssociation
)

# Set up logger
logger = logging.getLogger(__name__)

# Constants for repetition types
REPETITION_NONE = "none"
REPETITION_DAILY = "daily"
REPETITION_WEEKLY = "weekly"

class TourFilterService(BaseService):
    """Service for filtering tours with various criteria."""
    
    def __init__(self, session: AsyncSession):
        """Initialize the tour filter service with database session.
        
        Args:
            session: SQLAlchemy async session
        """
        super().__init__(session)
    
    async def filter_tours(
        self,
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
    ) -> List[int]:
        """Filter tours with various criteria and return matching tour IDs.
        
        Args:
            city: Optional city name to filter by
            price_min: Optional minimum price
            price_max: Optional maximum price
            date_from: Optional start date for departures
            date_to: Optional end date for departures
            time_from: Optional start time with timezone (format: HH:MM+TZ)
            time_to: Optional end time with timezone (format: HH:MM+TZ)
            categories: Optional list of tour categories
            duration_min: Optional minimum tour duration in minutes
            duration_max: Optional maximum tour duration in minutes
            limit: Maximum number of results to return
            offset: Results offset for pagination
            
        Returns:
            List of matching tour IDs
        """
        # Parse time filters
        time_filter_start_minutes, time_filter_end_minutes = self._parse_time_filters(time_from, time_to)
        
        # First, get all tours with recurring patterns for debugging
        if date_from is not None or date_to is not None:
            debug_stmt = select(Tour.id, Tour.title, Tour.repeat_type, Tour.repeat_time)
            debug_stmt = debug_stmt.where(
                and_(
                    Tour.repeat_type.isnot(None),
                    Tour.repeat_type != REPETITION_NONE,
                    Tour.repeat_time.isnot(None)
                )
            )
            result = await self.session.execute(debug_stmt)
            logger.debug("Available repeating tours:")
            for tour_id, title, repeat_type, repeat_time in result:
                logger.debug(f"  ID: {tour_id}, Title: {title}, Type: {repeat_type}, Time: {repeat_time}")
        
        # ------- QUERY PART 1: Tours with actual departures matching filters -------
        stmt1 = self._build_actual_departures_query(
            date_from, date_to, time_filter_start_minutes, time_filter_end_minutes
        )
        
        # ------- QUERY PART 2: Repeating tours with virtual departures matching filters -------
        stmt2 = self._build_virtual_departures_query(
            date_from, date_to, time_filter_start_minutes, time_filter_end_minutes
        )
        
        # ------- Apply common filters to both statements -------
        stmt1, stmt2 = self._apply_common_filters(
            stmt1, stmt2, city, price_min, price_max, 
            categories, duration_min, duration_max
        )
        
        # For debugging, check what virtual departures we have after filtering
        if date_from is not None or date_to is not None:
            # Execute the query for virtual departures only to see what we get
            virtual_tour_ids = [id for id, in await self.session.execute(stmt2)]
            logger.debug(f"Virtual departures after filtering: {virtual_tour_ids}")
            
            # If we have IDs, fetch their details
            if virtual_tour_ids:
                debug_tours = await self.session.execute(
                    select(Tour.id, Tour.title, Tour.repeat_type)
                    .where(Tour.id.in_(virtual_tour_ids))
                )
                for tour_id, title, repeat_type in debug_tours:
                    logger.debug(f"  Matched virtual tour: ID: {tour_id}, Title: {title}, Type: {repeat_type}")
        
        # ------- Combine results and apply limit/offset -------
        from sqlalchemy import union
        combined_stmt = union(stmt1, stmt2).alias()
        
        # Get distinct tour IDs
        final_stmt = select(combined_stmt.c.id).distinct().order_by(combined_stmt.c.id.desc())
        final_stmt = final_stmt.limit(limit).offset(offset)
        
        # Debug logging
        logger.debug(f"Searching tours with filters: city={city}, dates={date_from}-{date_to}, "
                    f"time={time_from}-{time_to}, categories={categories}")
        
        # Execute and return tour IDs
        tour_ids = [id for id, in await self.session.execute(final_stmt)]
        logger.debug(f"Found {len(tour_ids)} tours matching filters")
        return tour_ids
    
    def _parse_time_filters(
        self, time_from: str | None, time_to: str | None
    ) -> Tuple[int | None, int | None]:
        """Parse time filter strings into minutes since midnight in UTC.
        
        Args:
            time_from: Start time with timezone (format: HH:MM+TZ)
            time_to: End time with timezone (format: HH:MM+TZ)
            
        Returns:
            Tuple of (start_minutes, end_minutes) where each value is
            minutes since midnight in UTC or None if input was None
        """
        time_filter_start_minutes = None
        time_filter_end_minutes = None

        if time_from:
            try:
                # Parse time in format HH:MM+TZ
                time_filter_start_minutes = self._parse_time_with_timezone(time_from)
                logger.debug(f"Parsed time_from={time_from} to minutes={time_filter_start_minutes}")
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing time_from={time_from}: {str(e)}")

        if time_to:
            try:
                # Parse time in format HH:MM+TZ
                time_filter_end_minutes = self._parse_time_with_timezone(time_to)
                logger.debug(f"Parsed time_to={time_to} to minutes={time_filter_end_minutes}")
            except (ValueError, IndexError) as e:
                logger.error(f"Error parsing time_to={time_to}: {str(e)}")
        
        return time_filter_start_minutes, time_filter_end_minutes
    
    def _parse_time_with_timezone(self, time_string: str) -> int:
        """Parse time string with timezone into minutes since midnight in UTC.
        
        Args:
            time_string: Time string in format HH:MM+TZ or HH:MM-TZ
            
        Returns:
            Minutes since midnight in UTC
        """
        # Parse time in format HH:MM+TZ
        # We'll convert to minutes since midnight for simpler comparison
        parts = time_string.split('+')
        if len(parts) == 1:
            parts = time_string.split('-')
            if len(parts) > 1:
                # Handle negative offset
                tz_sign = -1
                time_part = parts[0]
                tz_part = parts[1]
            else:
                # No timezone specified, assume UTC
                tz_sign = 1
                time_part = time_string
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
        return (time_minutes - tz_offset_minutes) % (24 * 60)
    
    def _build_actual_departures_query(
        self, 
        date_from: date | None, 
        date_to: date | None,
        time_filter_start_minutes: int | None,
        time_filter_end_minutes: int | None
    ):
        """Build query for tours with actual departures matching date/time filters.
        
        Args:
            date_from: Optional start date for departures
            date_to: Optional end date for departures
            time_filter_start_minutes: Start time in minutes since midnight (UTC)
            time_filter_end_minutes: End time in minutes since midnight (UTC)
            
        Returns:
            SQLAlchemy query for tour IDs with actual departures
        """
        # Start with a clean query for tours with departures
        stmt = select(Tour.id)
        stmt = stmt.join(Departure, Departure.tour_id == Tour.id)
        
        # Date filtering for real departures
        if date_from:
            stmt = stmt.where(Departure.starts_at >= date_from)
        if date_to:
            # Add one day to include the entire end date
            next_day = date_to + timedelta(days=1)
            stmt = stmt.where(Departure.starts_at < next_day)

        # Time filtering for real departures
        if time_filter_start_minutes is not None or time_filter_end_minutes is not None:
            # Extract minutes since midnight in UTC
            minutes_expr = func.extract('hour', Departure.starts_at) * 60 + func.extract('minute', Departure.starts_at)
            
            stmt = self._apply_time_range_filter(stmt, minutes_expr, time_filter_start_minutes, time_filter_end_minutes)
            logger.debug(f"Applied time filtering to real departures: start={time_filter_start_minutes}, end={time_filter_end_minutes}")
        
        return stmt
    
    def _build_virtual_departures_query(
        self, 
        date_from: date | None, 
        date_to: date | None,
        time_filter_start_minutes: int | None,
        time_filter_end_minutes: int | None
    ):
        """Build query for tours with virtual departures matching date/time filters.
        
        Args:
            date_from: Optional start date for departures
            date_to: Optional end date for departures
            time_filter_start_minutes: Start time in minutes since midnight (UTC)
            time_filter_end_minutes: End time in minutes since midnight (UTC)
            
        Returns:
            SQLAlchemy query for tour IDs with virtual departures
        """
        # Start with a clean query for repeating tours - only include tours with repetition
        stmt = select(Tour.id)
        stmt = stmt.where(
            and_(
                Tour.repeat_type.isnot(None),
                Tour.repeat_type != REPETITION_NONE,  # Make sure we exclude tours with no repetition
                Tour.repeat_time.isnot(None)  # Make sure we have a repeat time
            )
        )
        
        # Add a debug log for the base query before any filters
        logger.debug(f"Base virtual departures query: tours with repetition != none and with repeat_time")

        # Time filtering for repeating tours
        if time_filter_start_minutes is not None or time_filter_end_minutes is not None:
            # Extract minutes since midnight from the repeat_time field
            repeat_time_minutes = func.extract('hour', func.cast(Tour.repeat_time, Time)) * 60 + \
                                func.extract('minute', func.cast(Tour.repeat_time, Time))
            
            stmt = self._apply_time_range_filter(stmt, repeat_time_minutes, time_filter_start_minutes, time_filter_end_minutes)
            logger.debug(f"Applied time filtering to virtual departures: start={time_filter_start_minutes}, end={time_filter_end_minutes}")

        # Date/weekday filtering for repeating tours
        if date_from or date_to:
            logger.debug(f"Filtering repeating tours with date_from={date_from}, date_to={date_to}")
            stmt = self._apply_weekday_filter_for_repeating_tours(stmt, date_from, date_to)
        else:
            logger.debug("No date filters applied to virtual departures")
        
        return stmt
    
    def _apply_time_range_filter(
        self, 
        stmt, 
        minutes_expr, 
        time_filter_start_minutes: int | None, 
        time_filter_end_minutes: int | None
    ):
        """Apply time range filter to a query.
        
        Args:
            stmt: SQLAlchemy query to modify
            minutes_expr: Expression that calculates minutes since midnight
            time_filter_start_minutes: Start time in minutes since midnight (UTC)
            time_filter_end_minutes: End time in minutes since midnight (UTC)
            
        Returns:
            Modified SQLAlchemy query
        """
        if time_filter_start_minutes is not None and time_filter_end_minutes is not None:
            if time_filter_start_minutes <= time_filter_end_minutes:
                # Normal case: e.g., 10:00 to 14:00
                stmt = stmt.where(
                    minutes_expr.between(time_filter_start_minutes, time_filter_end_minutes)
                )
            else:
                # Wraparound case: e.g., 22:00 to 02:00
                stmt = stmt.where(
                    or_(
                        minutes_expr >= time_filter_start_minutes,
                        minutes_expr <= time_filter_end_minutes
                    )
                )
        elif time_filter_start_minutes is not None:
            stmt = stmt.where(minutes_expr >= time_filter_start_minutes)
        elif time_filter_end_minutes is not None:
            stmt = stmt.where(minutes_expr <= time_filter_end_minutes)
        
        return stmt
    
    def _apply_weekday_filter_for_repeating_tours(self, stmt, date_from: date | None, date_to: date | None):
        """Apply weekday filter for repeating tours.
        
        Args:
            stmt: SQLAlchemy query to modify
            date_from: Start date for the filter
            date_to: End date for the filter
            
        Returns:
            Modified SQLAlchemy query
        """
        # If no date filters provided, return all repeating tours
        if not date_from and not date_to:
            logger.debug("No date filters, returning all repeating tours")
            return stmt
            
        try:
            # Create arrays for the days we want to match
            matching_weekdays = []
            
            # Get the weekday for the start date (0=Monday in both Python and our JSON data)
            if date_from is not None:
                from_dow = date_from.weekday()
                matching_weekdays.append(from_dow)
                logger.debug(f"Start date {date_from} weekday: {from_dow}")
            
            # Get the weekday for the end date
            if date_to is not None:
                to_dow = date_to.weekday()
                if to_dow not in matching_weekdays:  # Avoid duplicates
                    matching_weekdays.append(to_dow)
                logger.debug(f"End date {date_to} weekday: {to_dow}")
            
            # If the date range spans more than 1 day, add all weekdays in between
            if date_from is not None and date_to is not None:
                days_diff = (date_to - date_from).days
                logger.debug(f"Date range spans {days_diff} days")
                
                if days_diff > 0:
                    # Add all weekdays in between
                    current_date = date_from + timedelta(days=1)
                    while current_date < date_to:
                        current_dow = current_date.weekday()
                        if current_dow not in matching_weekdays:
                            matching_weekdays.append(current_dow)
                        current_date += timedelta(days=1)
            
            logger.debug(f"Matching weekdays for filter: {matching_weekdays}")
            
            # For daily repeating tours, we don't need to check weekdays,
            # they should always be included regardless of date.
            # IMPORTANT: Return tours with either daily repetition or weekly with matching weekdays
            
            # Daily repetition condition - these tours run every day, always include
            daily_condition = Tour.repeat_type == REPETITION_DAILY
            logger.debug(f"Looking for daily repetitions with: {REPETITION_DAILY}")
            
            # Build a condition for weekly repeating tours
            weekday_conditions = []
            
            # Must convert weekday integers to strings for JSON containment check
            # Also check surrounding brackets or commas to avoid partial matches
            for day in matching_weekdays:
                day_str = str(day)
                # Common JSON array patterns to check for:
                patterns = [
                    # Start of array with our day
                    f'[{day_str}',
                    f'[{day_str},',
                    # Middle of array
                    f', {day_str},',
                    # End of array
                    f',{day_str}]',
                    # Single element array
                    f'[{day_str}]'
                ]
                weekday_conditions.extend([
                    func.cast(Tour.repeat_weekdays, Text).like(f'%{pattern}%')
                    for pattern in patterns
                ])
            
            # For weekly repetitions, must check that the weekday matches
            weekly_condition = and_(
                Tour.repeat_type == REPETITION_WEEKLY,
                Tour.repeat_weekdays.isnot(None),
                or_(*weekday_conditions) if weekday_conditions else False
            )
            logger.debug(f"Looking for weekly repetitions with: {REPETITION_WEEKLY}")
            
            # Final condition for repeating tours: either daily OR weekly with matching day
            repeating_tours_condition = or_(daily_condition, weekly_condition)
            
            # Apply this condition to our statement for repeating tours
            stmt = stmt.where(repeating_tours_condition)
            
            logger.debug("Applied precise weekday filtering for repeating tours")
            
        except Exception as e:
            logger.error(f"Error in weekday filtering: {str(e)}")
            
        return stmt
    
    def _apply_common_filters(
        self,
        stmt1,
        stmt2,
        city: str | None,
        price_min: Decimal | None,
        price_max: Decimal | None,
        categories: List[str] | None,
        duration_min: int | None,
        duration_max: int | None,
    ):
        """Apply common filters to both query parts.
        
        Args:
            stmt1: First query part (actual departures)
            stmt2: Second query part (virtual departures)
            city: Optional city name to filter by
            price_min: Optional minimum price
            price_max: Optional maximum price
            categories: Optional list of tour categories
            duration_min: Optional minimum tour duration in minutes
            duration_max: Optional maximum tour duration in minutes
            
        Returns:
            Tuple of modified queries (stmt1, stmt2)
        """
        # Price filters
        if price_min is not None or price_max is not None:
            # Create price subquery
            price_subq = select(TicketCategory.tour_id, TicketCategory.price)\
                .where(TicketCategory.ticket_class_id == 0)\
                .subquery()
            
            # Apply to both statements
            stmt1 = stmt1.join(price_subq, Tour.id == price_subq.c.tour_id)
            stmt2 = stmt2.join(price_subq, Tour.id == price_subq.c.tour_id)
            
            if price_min is not None:
                stmt1 = stmt1.where(price_subq.c.price >= price_min)
                stmt2 = stmt2.where(price_subq.c.price >= price_min)
            if price_max is not None:
                stmt1 = stmt1.where(price_subq.c.price <= price_max)
                stmt2 = stmt2.where(price_subq.c.price <= price_max)
        
        # Category filter
        if categories and len(categories) > 0:
            # Create a subquery to find tours with matching categories
            # Use the association table TourCategoryAssociation to link tours and categories
            category_subq = (
                select(TourCategoryAssociation.tour_id)
                .join(TourCategory, TourCategoryAssociation.category_id == TourCategory.id)
                .where(TourCategory.name.in_(categories))
                .subquery()
            )
            
            # Apply category filter to both statements
            stmt1 = stmt1.join(category_subq, Tour.id == category_subq.c.tour_id)
            stmt2 = stmt2.join(category_subq, Tour.id == category_subq.c.tour_id)
        
        # Duration filters
        if duration_min is not None:
            stmt1 = stmt1.where(Tour.duration_minutes >= duration_min)
            stmt2 = stmt2.where(Tour.duration_minutes >= duration_min)
        if duration_max is not None:
            stmt1 = stmt1.where(Tour.duration_minutes <= duration_max)
            stmt2 = stmt2.where(Tour.duration_minutes <= duration_max)
        
        # City filter
        if city is not None:
            stmt1 = stmt1.join(City, City.id == Tour.city_id)
            stmt1 = stmt1.where(func.lower(City.name) == city.lower())
            
            stmt2 = stmt2.join(City, City.id == Tour.city_id)
            stmt2 = stmt2.where(func.lower(City.name) == city.lower())
        
        return stmt1, stmt2 