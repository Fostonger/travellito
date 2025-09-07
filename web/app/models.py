from sqlalchemy import (
    String, BigInteger, Integer, ForeignKey, Numeric, DateTime,
    func, select, UniqueConstraint, JSON, Index, Boolean, Time, Table
)
from sqlalchemy.orm import mapped_column, relationship, DeclarativeBase
from .roles import Role
from .security import _to_role_str
import uuid

# Helper to generate a short referral code
def _gen_referral_code() -> str:
    """Return random 8-char hex code for landlord referrals."""
    return uuid.uuid4().hex[:8]

class Base(DeclarativeBase): ...

# Association table for many-to-many relationship between Tour and TourCategory
class TourCategoryAssociation(Base):
    __tablename__ = "tour_category_associations"
    tour_id = mapped_column(ForeignKey("tours.id"), primary_key=True)
    category_id = mapped_column(ForeignKey("tour_categories.id"), primary_key=True)

# ---------- Core actors ----------
class Agency(Base):
    __tablename__ = "agencies"
    id          = mapped_column(Integer, primary_key=True)
    name        = mapped_column(String(120), unique=True, nullable=False)
    api_base    = mapped_column(String(256))        # optional third-party API
    tours       = relationship("Tour", back_populates="agency")

class Landlord(Base):
    __tablename__ = "landlords"
    id        = mapped_column(Integer, primary_key=True)
    name      = mapped_column(String(120))
    user_id   = mapped_column(ForeignKey("users.id"), nullable=True)
    referral_code = mapped_column(String(64), unique=True, default=_gen_referral_code)
    qr_sent   = mapped_column(DateTime)
    phone_number = mapped_column(String(32), nullable=True)
    bank_name = mapped_column(String(120), nullable=True)

    apartments = relationship("Apartment", back_populates="landlord")

    # Add relationship to landlord
    commissions = relationship(
        "LandlordCommission",
        back_populates="landlord",
        cascade="all, delete-orphan",
    )

class User(Base):
    __tablename__ = "users"
    id        = mapped_column(Integer, primary_key=True)
    # Optional Telegram chat id (null for email/password accounts)
    tg_id     = mapped_column(BigInteger, nullable=True)
    # Email/password accounts (admins, agencies, landlords, managers)
    email          = mapped_column(String(128), unique=True, nullable=True)
    password_hash  = mapped_column(String(128), nullable=True)
    # Store the role directly for convenience (admin, agency, landlord, bot_user, manager, ...)
    role       = mapped_column(String(16), default=Role.bot_user.value, nullable=False)
    first     = mapped_column(String(64))
    last      = mapped_column(String(64))
    username  = mapped_column(String(64))
    agency_id = mapped_column(ForeignKey("agencies.id"), nullable=True)
    created   = mapped_column(DateTime, server_default=func.now())
    phone     = mapped_column(String(32))  # optional Telegram phone
    # Apartment reference for tracking user origin
    apartment_id = mapped_column(ForeignKey("apartments.id"), nullable=True)
    apartment_set_at = mapped_column(DateTime, nullable=True)

    agency    = relationship("Agency", lazy="joined")
    apartment = relationship("Apartment", lazy="joined")

    @classmethod
    async def get_or_create(cls, session, tg: dict, *, role: "Role | str" = Role.bot_user):
        tg_id = int(tg["id"])
        stmt = select(cls).where(cls.tg_id == tg_id)
        result = await session.scalar(stmt)
        if result:
            # Update role if it changed (e.g. promoting a bot_user to manager)
            if role and _to_role_str(role) != result.role:
                result.role = _to_role_str(role)
            return result
        user = cls(
            tg_id=tg_id,
            first=tg.get("first_name"),
            last=tg.get("last_name"),
            username=tg.get("username"),
            phone=tg.get("phone") or tg.get("phone_number"),
            role=_to_role_str(role),
        )
        session.add(user)
        return user

# ---------- Tours ----------
class Tour(Base):
    __tablename__ = "tours"
    id          = mapped_column(Integer, primary_key=True)
    agency_id   = mapped_column(ForeignKey("agencies.id"))
    title       = mapped_column(String(200))
    description = mapped_column(String(2000))
    description_translations = mapped_column(JSON, nullable=True, comment="{lang: description}")
    max_commission_pct = mapped_column(Numeric(5, 2), default=10)  # system admin configurable
    free_cancellation_cutoff_h = mapped_column(Integer, default=24, nullable=False, comment="Hours before start when free cancellation is allowed")
    # Optional additional metadata used for filtering / future geo features
    duration_minutes = mapped_column(Integer, nullable=True)
    # Normalised city FK instead of free-text string
    city_id   = mapped_column(ForeignKey("cities.id"))
    # -------- Recurrence ---------
    repeat_type = mapped_column(String(16), ForeignKey("repetition_types.code"), default="none", nullable=False, comment="none | daily | weekly")
    # For weekly repetition store list of weekday numbers 0=Mon .. 6=Sun
    repeat_weekdays = mapped_column(JSON, nullable=True)
    # Time of day (HH:MM:SS) when repeat departs
    repeat_time = mapped_column(Time, nullable=True)
    # Location information
    address    = mapped_column(String(500), nullable=True)  # Human-readable address
    latitude   = mapped_column(Numeric(8, 6))   # nullable
    longitude  = mapped_column(Numeric(9, 6))
    # Custom booking template for notifications
    booking_template = mapped_column(String(2000), nullable=True, comment="Custom template for booking confirmation messages")
    agency      = relationship("Agency", back_populates="tours")
    images      = relationship("TourImage", back_populates="tour")
    categories  = relationship("TicketCategory", back_populates="tour")
    city        = relationship("City", back_populates="tours")
    repeat_type_rel = relationship("RepetitionType")
    
    # Many-to-many relationship with categories
    tour_categories = relationship(
        "TourCategory",
        secondary="tour_category_associations",
        back_populates="tour_list",
    )
    
    # NEW: multiple repetition rules
    repetitions = relationship(
        "TourRepetition",
        back_populates="tour",
        cascade="all, delete-orphan"
    )

class TourImage(Base):
    __tablename__ = "tour_images"
    id       = mapped_column(Integer, primary_key=True)
    tour_id  = mapped_column(ForeignKey("tours.id"))
    key      = mapped_column(String(256))
    tour     = relationship("Tour", back_populates="images")

# ---------- Departures (specific date/time instances of a Tour) ----------
class Departure(Base):
    __tablename__ = "departures"
    id          = mapped_column(Integer, primary_key=True)
    tour_id     = mapped_column(ForeignKey("tours.id"), nullable=False)
    starts_at   = mapped_column(DateTime)
    capacity    = mapped_column(Integer, nullable=False)
    # Flag toggled by nightly job once free-cancellation cutoff is reached.
    modifiable = mapped_column(Boolean, nullable=False, server_default="true")

    tour        = relationship("Tour")

# ---------- Landlord chosen commission per Tour ----------
class LandlordCommission(Base):
    __tablename__ = "landlord_commissions"
    landlord_id = mapped_column(ForeignKey("landlords.id"), primary_key=True)
    tour_id     = mapped_column(ForeignKey("tours.id"), primary_key=True)
    commission_pct = mapped_column(Numeric(5, 2), nullable=False)

    landlord = relationship("Landlord", back_populates="commissions")
    tour     = relationship("Tour")

    __table_args__ = (
        UniqueConstraint("landlord_id", "tour_id", name="uix_landlord_tour_commission"),
        Index("ix_landlord_commission_landlord_pct", "landlord_id", "commission_pct"),
    )

# ---------- Referrals & Purchases ----------
class Referral(Base):
    __tablename__ = "referrals"
    user_id      = mapped_column(ForeignKey("users.id"), primary_key=True)
    landlord_id  = mapped_column(ForeignKey("landlords.id"), primary_key=True)
    ts           = mapped_column(DateTime, server_default=func.now())

class Purchase(Base):
    __tablename__ = "purchases"
    id           = mapped_column(Integer, primary_key=True)
    user_id      = mapped_column(ForeignKey("users.id"))
    departure_id = mapped_column(ForeignKey("departures.id"))
    landlord_id  = mapped_column(ForeignKey("landlords.id"))
    apartment_id = mapped_column(ForeignKey("apartments.id"), nullable=True)
    qty          = mapped_column(Integer, default=1)
    amount       = mapped_column(Numeric(10, 2))
    ts           = mapped_column(DateTime, server_default=func.now())
    status      = mapped_column(String(20), default="pending", nullable=False, comment="Booking status: pending, confirmed, rejected")
    viewed      = mapped_column(Boolean, default=False, nullable=False, comment="Whether the booking has been viewed by the agency")
    status_changed_at = mapped_column(DateTime, nullable=True, comment="When the status was last changed")
    tourist_notified = mapped_column(Boolean, default=False, nullable=False, comment="Whether the tourist has been notified of status change")

    user         = relationship("User")
    departure    = relationship("Departure")
    items        = relationship("PurchaseItem", back_populates="purchase")
    apartment    = relationship("Apartment")

    # Speed up look-ups of bookings for a departure (cancellation window job, capacity checks)
    __table_args__ = (
        Index("ix_purchase_departure_ts", "departure_id", "ts"),
    )

# ---------- Ticket categories (adult / child / student etc.) ------------
class TicketCategory(Base):
    __tablename__ = "ticket_categories"
    id       = mapped_column(Integer, primary_key=True)
    tour_id  = mapped_column(ForeignKey("tours.id"), nullable=False)
    name     = mapped_column(String(64), nullable=False)
    price    = mapped_column(Numeric(10, 2), nullable=False)

    # New normalisation: link to TicketClass (adult / child / student ...) instead of free text name.
    ticket_class_id = mapped_column(ForeignKey("ticket_classes.id"), nullable=True)

    tour     = relationship("Tour", back_populates="categories")

    # Optional relationship – populated after migration
    ticket_class = relationship("TicketClass")

# ---------- Purchase items (by category) --------------------------------
class PurchaseItem(Base):
    __tablename__ = "purchase_items"
    id           = mapped_column(Integer, primary_key=True)
    purchase_id  = mapped_column(ForeignKey("purchases.id"), nullable=False)
    category_id  = mapped_column(ForeignKey("ticket_categories.id"), nullable=False)
    qty          = mapped_column(Integer, nullable=False)
    amount       = mapped_column(Numeric(10, 2), nullable=False)

    purchase     = relationship("Purchase", back_populates="items")
    category     = relationship("TicketCategory")

# ---------- Apartments (one-to-many with Landlord) ----------
class Apartment(Base):
    __tablename__ = "apartments"
    id           = mapped_column(Integer, primary_key=True)
    landlord_id  = mapped_column(ForeignKey("landlords.id"), nullable=False)
    name         = mapped_column(String(120))
    city_id      = mapped_column(ForeignKey("cities.id"), nullable=False)
    latitude     = mapped_column(Numeric(8, 6))   # optional
    longitude    = mapped_column(Numeric(9, 6))   # optional

    landlord = relationship("Landlord", back_populates="apartments")
    city = relationship("City")

# ---------- Platform-wide settings (key → JSON value) ----------------------
class Setting(Base):
    """Simple key/value store for platform-wide configuration.

    Example rows:
        key = "default_max_commission", value = 10  (numeric JSON literal)
    """

    __tablename__ = "settings"

    key   = mapped_column(String(64), primary_key=True)
    value = mapped_column(JSON, nullable=False)

# ---------- Agency API keys (for external sync) --------------------------
class ApiKey(Base):
    __tablename__ = "api_keys"

    id         = mapped_column(Integer, primary_key=True)
    agency_id  = mapped_column(ForeignKey("agencies.id"), nullable=False)
    key        = mapped_column(String(64), unique=True, nullable=False)
    created    = mapped_column(DateTime, server_default=func.now())

    agency = relationship("Agency")

# ------------------------- New Normalised Tables ---------------------------

class City(Base):
    """Master table of cities so tours can be filtered reliably."""

    __tablename__ = "cities"

    id   = mapped_column(Integer, primary_key=True)
    name = mapped_column(String(64), unique=True, nullable=False, index=True)
    # Offset from UTC in minutes (e.g. Moscow +180, Samara +240)
    timezone_offset_min = mapped_column(Integer, nullable=True, comment="UTC offset in minutes")

    tours = relationship("Tour", back_populates="city")
    apartments = relationship("Apartment", back_populates="city")


class TicketClass(Base):
    """Lookup table for passenger types: adult, child, student, senior …"""

    __tablename__ = "ticket_classes"

    id        = mapped_column(Integer, primary_key=True)
    code      = mapped_column(String(32), unique=True, nullable=False)  # machine-friendly
    human_name = mapped_column(String(64), nullable=False)              # shown to users

    # Back-ref is defined in TicketCategory


class TourCategory(Base):
    """High-level thematic categories (walking, food, museum …)."""

    __tablename__ = "tour_categories"

    id   = mapped_column(Integer, primary_key=True)
    name = mapped_column(String(64), unique=True, nullable=False)
    
    # Many-to-many relationship with tours
    tour_list = relationship(
        "Tour",
        secondary="tour_category_associations",
        back_populates="tour_categories",
    )


class RepetitionType(Base):
    """Departure repetition types (none, daily, weekly)."""

    __tablename__ = "repetition_types"

    code = mapped_column(String(16), primary_key=True)
    name = mapped_column(String(64), nullable=False)
    description = mapped_column(String(255), nullable=True)
    
    tours = relationship("Tour", back_populates="repeat_type_rel")

# NEW: explicit repetitions per tour
class TourRepetition(Base):
    __tablename__ = "tour_repetitions"
    id = mapped_column(Integer, primary_key=True)
    tour_id = mapped_column(ForeignKey("tours.id"), nullable=False)
    repeat_type = mapped_column(String(16), ForeignKey("repetition_types.code"), nullable=False)
    repeat_weekdays = mapped_column(JSON, nullable=True)  # List[int] for weekly
    repeat_time = mapped_column(Time, nullable=False)

    tour = relationship("Tour", back_populates="repetitions")

# ---------- Referral Events (audit trail for referral changes) ----------
class ReferralEvent(Base):
    __tablename__ = "referral_events"
    id           = mapped_column(Integer, primary_key=True)
    user_id      = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    old_referral = mapped_column(ForeignKey("apartments.id"), nullable=True)
    new_referral = mapped_column(ForeignKey("apartments.id"), nullable=False)
    changed_at   = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User")
    old_apartment = relationship("Apartment", foreign_keys=[old_referral])
    new_apartment = relationship("Apartment", foreign_keys=[new_referral])

# ---------- Support System Models ----------
class SupportMessage(Base):
    __tablename__ = "support_messages"
    id           = mapped_column(Integer, primary_key=True)
    user_id      = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    message_type = mapped_column(String(20), nullable=False, comment="Type: issue, question, payment_request")
    message      = mapped_column(String(2000), nullable=False)
    created_at   = mapped_column(DateTime, server_default=func.now(), nullable=False)
    status       = mapped_column(String(20), default="pending", nullable=False, comment="Status: pending, in_progress, resolved")
    assigned_admin_id = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    assigned_admin = relationship("User", foreign_keys=[assigned_admin_id])
    responses = relationship("SupportResponse", back_populates="support_message", cascade="all, delete-orphan")

class SupportResponse(Base):
    __tablename__ = "support_responses"
    id              = mapped_column(Integer, primary_key=True)
    support_message_id = mapped_column(ForeignKey("support_messages.id"), nullable=False)
    admin_id        = mapped_column(ForeignKey("users.id"), nullable=False)
    response        = mapped_column(String(2000), nullable=False)
    created_at      = mapped_column(DateTime, server_default=func.now(), nullable=False)
    
    # Relationships
    support_message = relationship("SupportMessage", back_populates="responses")
    admin = relationship("User")

# ---------- Landlord Payment Tracking ----------
class LandlordPaymentRequest(Base):
    __tablename__ = "landlord_payment_requests"
    id              = mapped_column(Integer, primary_key=True)
    landlord_id     = mapped_column(ForeignKey("landlords.id"), nullable=False, index=True)
    amount          = mapped_column(Numeric(10, 2), nullable=False)
    phone_number    = mapped_column(String(32), nullable=False)
    bank_name       = mapped_column(String(120), nullable=True)
    status          = mapped_column(String(20), default="pending", nullable=False, comment="Status: pending, processing, completed, rejected")
    requested_at    = mapped_column(DateTime, server_default=func.now(), nullable=False)
    processed_at    = mapped_column(DateTime, nullable=True)
    processed_by_id = mapped_column(ForeignKey("users.id"), nullable=True)
    unique_users_count = mapped_column(Integer, nullable=False, comment="Number of unique users at time of request")
    
    # Relationships
    landlord = relationship("Landlord")
    processed_by = relationship("User")

class LandlordPaymentHistory(Base):
    __tablename__ = "landlord_payment_history"
    id          = mapped_column(Integer, primary_key=True)
    landlord_id = mapped_column(ForeignKey("landlords.id"), nullable=False, index=True)
    amount      = mapped_column(Numeric(10, 2), nullable=False)
    paid_at     = mapped_column(DateTime, server_default=func.now(), nullable=False)
    paid_by_id  = mapped_column(ForeignKey("users.id"), nullable=False)
    payment_request_id = mapped_column(ForeignKey("landlord_payment_requests.id"), nullable=True)
    
    # Relationships
    landlord = relationship("Landlord")
    paid_by = relationship("User")
    payment_request = relationship("LandlordPaymentRequest")
