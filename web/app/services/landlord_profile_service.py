from typing import Optional
import phonenumbers
from fastapi import HTTPException, status

from app.core.unit_of_work import UnitOfWork
from app.models import Landlord


class LandlordProfileService:
    """Service for landlord profile operations"""
    
    def __init__(self, uow: UnitOfWork):
        self.uow = uow
        
    async def get_landlord_profile(self, user_id: int) -> Optional[Landlord]:
        """Get landlord profile by user ID"""
        async with self.uow:
            return await self.uow.landlord_profile.get_by_user_id(user_id)

    async def get_landlord_profile_by_id(self, landlord_id: int) -> Optional[Landlord]:
        """Get landlord profile by landlord ID"""
        async with self.uow:
            return await self.uow.landlord_profile.get_by_id(landlord_id)
    
    def validate_phone_number(self, phone_number: str) -> str:
        """Validate and format an international phone number.
        
        Args:
            phone_number: Phone number to validate
            
        Returns:
            Formatted E.164 phone number
            
        Raises:
            HTTPException: If the phone number is invalid
        """
        if not phone_number or phone_number.strip() == '':
            return None
            
        try:
            # Parse the phone number
            parsed = phonenumbers.parse(phone_number, None)
            
            # Check if it's a valid number
            if not phonenumbers.is_valid_number(parsed):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail="Invalid phone number format"
                )
            
            # Format to E.164 standard (e.g. +12125551234)
            formatted = phonenumbers.format_number(
                parsed, 
                phonenumbers.PhoneNumberFormat.E164
            )
            
            return formatted
        except phonenumbers.NumberParseException:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid phone number format. Please include country code (e.g. +7 for Russia)."
            )
            
    async def update_payment_info(self, landlord_id: int, phone_number: Optional[str] = None, bank_name: Optional[str] = None) -> bool:
        """Update landlord's payment information"""
        # Validate phone number if provided
        validated_phone = None
        if phone_number is not None:
            validated_phone = self.validate_phone_number(phone_number)
            
        async with self.uow:
            result = await self.uow.landlord_profile.update_payment_info(
                landlord_id=landlord_id,
                phone_number=validated_phone,
                bank_name=bank_name
            )
            if result:
                await self.uow.commit()
            return result 