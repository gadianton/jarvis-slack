#! Python 3.5.2
# http://pythoncentral.io/introductory-tutorial-python-sqlalchemy/

import os, sys #, MySQLdb
from sqlalchemy import Table, Column, ForeignKey, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

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
    id = Column(Integer, primary_key=True)
    slack_id = Column(String(30), unique=True, nullable=False)
    slack_name = Column(String(30), unique=True, nullable=False)
    notifications = Column('Receive Notifications', Boolean, unique=False, default=True)

    # Relationships
    series_followed = relationship('Follow', cascade='all, delete-orphan', back_populates='user')


class TV_Series(Base):
    __tablename__ = 'tv_series'

    # Columns
    id = Column(Integer, primary_key=True)
    tvmaze_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(100))
    api_url = Column(String(100))
    web_url = Column(String(100))
    
    # Relationships
    followed_by = relationship('Follow', cascade='all, delete-orphan', back_populates='tv_series')


# Create an engine that stores data in the local directory
engine = create_engine('sqlite:///tvmaze.db')

# connection_string = "mysql://root:" + os.environ['JARVIS_DB_PW'] + "@127.0.0.1:3306/jarvis"
# connection_string = "mysql://root:" + os.environ['JARVIS_DB_PW'] + "@127.0.0.1:3306/jarvis_test"
#engine = create_engine(connection_string)

# Create all tables in the engine. This is equivalent to "Create Table"
# statements in raw SQL.
Base.metadata.create_all(engine)



'''
To do:
* Setup many-to-many relationship
http://docs.sqlalchemy.org/en/rel_1_1/orm/basic_relationships.html#many-to-many
'''