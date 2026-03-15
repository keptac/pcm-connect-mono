from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from ..db.base import Base


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=True)
    listing_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String, nullable=True)
    price_text = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")
    university = relationship("University", back_populates="marketplace_listings")
    interests = relationship("MarketplaceInterest", back_populates="listing", cascade="all, delete-orphan")


class MarketplaceInterest(Base):
    __tablename__ = "marketplace_interests"
    __table_args__ = (UniqueConstraint("listing_id", "user_id", name="uq_marketplace_interest_listing_user"),)

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("marketplace_listings.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    listing = relationship("MarketplaceListing", back_populates="interests")
    user = relationship("User", back_populates="marketplace_interests")
