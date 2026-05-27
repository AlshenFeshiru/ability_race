from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base

class User(Base):
    __tablename__ = "users"
    id                    = Column(String(64), primary_key=True)
    nickname              = Column(String(64), unique=True, nullable=False)
    full_name             = Column(String(128), nullable=False)
    status                = Column(String(32), nullable=False)
    public_key_pem        = Column(Text, nullable=False)
    field_multiple_choice = Column(JSON, default=list)
    field_championship    = Column(Integer, nullable=True)
    payment_verified      = Column(Boolean, default=True)
    registration_complete = Column(Boolean, default=False)
    created_at            = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    machine_id            = Column(String(128), nullable=True)
    ip_subnet             = Column(String(64), nullable=True)
    eliminated            = Column(Boolean, default=False)
    avatar_id             = Column(Integer, nullable=True)
    exit_count            = Column(Integer, default=0)
    audio_granted         = Column(Boolean, default=False)
    age_verified          = Column(String(32), default="pending")
    age_inference         = Column(Text, nullable=True)
    is_root_device        = Column(Boolean, default=False)
    payments  = relationship("Payment", back_populates="user")
    scores    = relationship("Score", back_populates="user")
    abilities = relationship("Ability", back_populates="user")
    state     = relationship("ChampionshipState", back_populates="user", uselist=False)
    node      = relationship("Node", back_populates="user", uselist=False)
    effects   = relationship("AbilityEffect", back_populates="target_user", foreign_keys="AbilityEffect.target_user_id")

class Payment(Base):
    __tablename__ = "payments"
    id            = Column(String(64), primary_key=True)
    user_id       = Column(String(64), ForeignKey("users.id"), nullable=False)
    amount        = Column(Integer, nullable=False, default=0)
    bank_reference= Column(String(128), nullable=True)
    payment_hash  = Column(String(128), nullable=False)
    verified      = Column(Boolean, default=True)
    verified_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    verified_by   = Column(String(64), nullable=True, default="FREE")
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user = relationship("User", back_populates="payments")

class Question(Base):
    __tablename__ = "questions"
    id             = Column(String(64), primary_key=True)
    field          = Column(String(64), nullable=False)
    week           = Column(Integer, nullable=False)
    test_type      = Column(String(64), nullable=False)
    question_text  = Column(Text, nullable=False)
    option_a       = Column(Text, nullable=True)
    option_b       = Column(Text, nullable=True)
    options_json   = Column(JSON, nullable=True)
    correct_answer = Column(String(512), nullable=False)
    sequence_index = Column(Integer, default=0)
    sequence_group = Column(String(64), nullable=True)
    difficulty     = Column(String(32), default="mahasiswa")
    context_after  = Column(Text, nullable=True)
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Score(Base):
    __tablename__ = "scores"
    id             = Column(String(64), primary_key=True)
    user_id        = Column(String(64), ForeignKey("users.id"), nullable=False)
    field          = Column(String(64), nullable=False)
    week           = Column(Integer, nullable=False)
    day            = Column(Integer, nullable=False)
    raw_score      = Column(Float, default=0.0)
    composite_score= Column(Float, default=0.0)
    percentage     = Column(Float, default=0.0)
    total_questions= Column(Integer, default=0)
    correct_count  = Column(Integer, default=0)
    wrong_count    = Column(Integer, default=0)
    skip_count     = Column(Integer, default=0)
    updated_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user = relationship("User", back_populates="scores")

class Ability(Base):
    __tablename__ = "abilities"
    id           = Column(String(64), primary_key=True)
    user_id      = Column(String(64), ForeignKey("users.id"), nullable=False)
    ability_type = Column(String(64), nullable=False)
    acquired_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at   = Column(DateTime, nullable=True)
    used         = Column(Boolean, default=False)
    used_at      = Column(DateTime, nullable=True)
    week         = Column(Integer, nullable=False)
    day          = Column(Integer, nullable=False)
    user = relationship("User", back_populates="abilities")

class AbilityEffect(Base):
    __tablename__ = "ability_effects"
    id             = Column(String(64), primary_key=True)
    source_user_id = Column(String(64), ForeignKey("users.id"), nullable=False)
    target_user_id = Column(String(64), ForeignKey("users.id"), nullable=False)
    ability_type   = Column(String(64), nullable=False)
    applied_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at     = Column(DateTime, nullable=True)
    active         = Column(Boolean, default=True)
    effect_data    = Column(JSON, nullable=True)
    target_user = relationship("User", back_populates="effects", foreign_keys=[target_user_id])

class ChampionshipState(Base):
    __tablename__ = "championship_states"
    id                        = Column(String(64), primary_key=True)
    user_id                   = Column(String(64), ForeignKey("users.id"), unique=True, nullable=False)
    current_week              = Column(Integer, default=1)
    current_day               = Column(Integer, default=1)
    current_question_index    = Column(Integer, default=0)
    answers_log               = Column(JSON, default=list)
    consecutive_correct       = Column(Integer, default=0)
    ability_selection_pending = Column(Boolean, default=False)
    ability_options           = Column(JSON, default=list)
    daily_complete            = Column(Boolean, default=False)
    last_active               = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    grand_prix_phase          = Column(Integer, default=1)
    user = relationship("User", back_populates="state")

class Node(Base):
    __tablename__ = "nodes"
    id                  = Column(String(64), primary_key=True)
    user_id             = Column(String(64), ForeignKey("users.id"), unique=True, nullable=False)
    ip_subnet           = Column(String(64), nullable=False)
    machine_fingerprint = Column(String(256), nullable=False)
    championship_field  = Column(Integer, nullable=True)
    amplitude           = Column(Float, default=1.0)
    temporal_offset     = Column(Float, default=0.0)
    question_seed       = Column(Integer, nullable=False)
    registered_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user = relationship("User", back_populates="node")

class MachineRegistry(Base):
    __tablename__ = "machine_registry"
    id                  = Column(String(64), primary_key=True)
    machine_fingerprint = Column(String(256), unique=True, nullable=False)
    user_id             = Column(String(64), ForeignKey("users.id"), nullable=False)
    registered_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address          = Column(String(64), nullable=True)

class AvatarRegistry(Base):
    __tablename__ = "avatar_registry"
    id        = Column(Integer, primary_key=True)
    user_id   = Column(String(64), ForeignKey("users.id"), unique=True, nullable=False)
    avatar_id = Column(Integer, unique=True, nullable=False)
    claimed_at= Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ViewerRating(Base):
    __tablename__ = "viewer_ratings"
    id            = Column(String(64), primary_key=True)
    viewer_fp     = Column(String(128), nullable=False)
    target_user_id= Column(String(64), ForeignKey("users.id"), nullable=False)
    rating        = Column(Integer, nullable=False)
    locked        = Column(Boolean, default=False)
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class LeaderboardCache(Base):
    __tablename__ = "leaderboard_cache"
    id            = Column(String(64), primary_key=True)
    field         = Column(String(64), nullable=False)
    snapshot_week = Column(Integer, nullable=False)
    snapshot_day  = Column(Integer, nullable=False)
    rankings      = Column(JSON, nullable=False)
    generated_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
