from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from app.api.v1.schemas.tour_schemas import TourReviewCreate, TourReviewOut, TourReviewUpdate
from app.deps import SessionDep
from app.security import current_user
from app.services.tour_service import TourService
from app.core.exceptions import NotFoundError, ValidationError, AuthorizationError

router = APIRouter()

logger = logging.getLogger(__name__)

@router.post("/", response_model=TourReviewOut, status_code=status.HTTP_201_CREATED)
async def create_review(
    review: TourReviewCreate, 
    sess: SessionDep,
    user=Depends(current_user),
):
    """Create a new tour review"""
    try:
        # Log the incoming request
        logger.info(f"Creating review: user={user.get('sub')}, booking_id={review.booking_id}, tour_id={review.tour_id}")
        
        # Extract user ID from token
        user_id = int(user["sub"])
        
        service = TourService(sess)
        new_review = await service.create_tour_review(
            user_id=user_id,
            tour_id=review.tour_id,
            booking_id=review.booking_id,
            text=review.text
        )
        
        await sess.commit()
        logger.info(f"Review created successfully: id={new_review.id}")
        
        return new_review
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        # Return 400 for validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AuthorizationError as e:
        logger.error(f"Authorization error: {str(e)}")
        # Return 403 for authorization errors
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except NotFoundError as e:
        logger.error(f"Not found error: {str(e)}")
        # Return 404 for not found errors
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Exception creating review: {str(e)}")
        # Return 409 if review already exists
        if "unique constraint" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Review for this booking already exists"
            )
        # Return 500 for all other errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/bot", response_model=TourReviewOut, status_code=status.HTTP_201_CREATED)
async def create_review_from_bot(
    review: TourReviewCreate,
    sess: SessionDep,
    tg_user_id: int = Query(..., description="Telegram user ID"),
    user=Depends(current_user),
):
    """Create a tour review from bot with telegram user ID"""
    try:
        # Verify the token is from bot
        logger.info(f"Bot review endpoint accessed with role={user.get('role')}")
        if user.get("role") != "bot":
            logger.error(f"Unauthorized access attempt to bot review endpoint with role={user.get('role')}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This endpoint is only accessible by the bot"
            )
        
        # Log the incoming request
        logger.info(f"Bot creating review: tg_user_id={tg_user_id}, booking_id={review.booking_id}, tour_id={review.tour_id}")
        
        # Get user by telegram ID
        from app.models import User
        from sqlalchemy import select
        
        stmt = select(User).where(User.tg_id == tg_user_id)
        result = await sess.execute(stmt)
        db_user = result.scalar_one_or_none()
        
        if not db_user:
            logger.error(f"User with telegram ID {tg_user_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        service = TourService(sess)
        new_review = await service.create_tour_review(
            user_id=db_user.id,
            tour_id=review.tour_id,
            booking_id=review.booking_id,
            text=review.text
        )
        
        await sess.commit()
        logger.info(f"Review created successfully via bot: id={new_review.id}")
        
        return new_review
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AuthorizationError as e:
        logger.error(f"Authorization error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except NotFoundError as e:
        logger.error(f"Not found error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.exception(f"Exception creating review via bot: {str(e)}")
        if "unique constraint" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Review for this booking already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/tour/{tour_id}", response_model=list[TourReviewOut])
async def get_tour_reviews(
    tour_id: int,
    sess: SessionDep
):
    """Get all reviews for a specific tour"""
    try:
        service = TourService(sess)
        reviews = await service.get_tour_reviews(tour_id)
        return reviews
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        ) 

@router.put("/{review_id}", response_model=TourReviewOut)
async def update_review(
    review_id: int,
    review_update: TourReviewUpdate,
    sess: SessionDep,
    user=Depends(current_user)
):
    """Update an existing tour review"""
    try:
        # Extract user ID from token
        user_id = int(user["sub"])
        
        service = TourService(sess)
        updated_review = await service.update_tour_review(
            review_id=review_id,
            user_id=user_id,
            text=review_update.text
        )
        
        await sess.commit()
        
        return updated_review
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: int,
    sess: SessionDep,
    user=Depends(current_user)
):
    """Delete a tour review"""
    try:
        # Extract user ID from token
        user_id = int(user["sub"])
        
        service = TourService(sess)
        await service.delete_tour_review(review_id=review_id, user_id=user_id)
        
        await sess.commit()
        
        return None
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        ) 