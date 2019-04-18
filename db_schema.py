import os
import sys 
import psycopg2
from sqlalchemy import Table, Column, ForeignKey, Integer, String, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class Follow(Base):
    __tablename__ = 'users_following_tv_series'

    # Columns
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    tv_series_id = Column(Integer, ForeignKey('tv_series.id'), primary_key=True)
    is_following = Column(Boolean, unique=False, default=False)
    
    # Relationships
    user = relationship('User', back_populates='series_followed')
    tv_series = relationship('TV_Series', back_populates='followed_by')


class User(Base):
    __tablename__ = 'users'

    # Columns
    id = Column(Integer, primary_key=True, unique=True)
    slack_id = Column(String(30), unique=True, nullable=False)
    slack_name = Column(String(30), unique=True, nullable=False)
    notifications = Column('Receive Notifications', Boolean, unique=False, default=True)

    # Relationships
    series_followed = relationship('Follow', cascade='all, delete-orphan', back_populates='user')


class TV_Series(Base):
    __tablename__ = 'tv_series'

    # Columns
    id = Column(Integer, primary_key=True, unique=True)
    tvmaze_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(100))
    status = Column(String(20))
    api_url = Column(String(100))
    next_episode_season = Column(Integer)
    next_episode_number = Column(Integer)
    next_episode_name = Column(String(50))
    next_episode_date = Column(Date)
    next_episode_api_url = Column(String(100))
    
    # Relationships
    followed_by = relationship('Follow', cascade='all, delete-orphan', back_populates='tv_series')


def create_db_session():

    # engine = create_engine('sqlite:///tvmaze.db')
    engine = create_engine('postgresql://localhost/jarvis')
    Base.metadata.bind = engine
    DBSession = sessionmaker(bind=engine)
    session = DBSession()

    return session


# Create an engine that stores data in the local directory
# engine = create_engine('sqlite:///tvmaze.db')
engine = create_engine('postgresql://localhost/jarvis')

# Create all tables in the engine. This is equivalent to "Create Table"
# statements in raw SQL.
Base.metadata.create_all(engine)