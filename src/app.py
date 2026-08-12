"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.

This version uses SQLite for persistent storage of participant data and
loads activities from an activities.json configuration file.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import json
import os
from pathlib import Path
from datetime import datetime

# Database setup
DATABASE_URL = "sqlite:///./activities.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database model for participant signups
class Participant(Base):
    __tablename__ = "participants"
    
    id = Column(String, primary_key=True)  # Composite key: activity_name:email
    activity_name = Column(String, index=True)
    email = Column(String)
    signup_date = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# Load activities from JSON file
def load_activities():
    """Load activities from activities.json configuration file"""
    activities_file = os.path.join(Path(__file__).parent, "activities.json")
    try:
        with open(activities_file, 'r') as f:
            activities_list = json.load(f)
            # Convert to dictionary keyed by activity name
            return {activity["name"]: activity for activity in activities_list}
    except FileNotFoundError:
        raise RuntimeError(f"activities.json not found at {activities_file}")

# Load activities at startup
activities = load_activities()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()




@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities(db: Session = None):
    """Get all activities with their current participant lists"""
    if db is None:
        db = SessionLocal()
    
    try:
        result = {}
        
        for activity_name, activity_details in activities.items():
            # Get all participants for this activity from database
            participants_db = db.query(Participant).filter(
                Participant.activity_name == activity_name
            ).all()
            
            participant_emails = [p.email for p in participants_db]
            
            result[activity_name] = {
                "description": activity_details["description"],
                "schedule": activity_details["schedule"],
                "max_participants": activity_details["max_participants"],
                "participants": participant_emails
            }
        
        return result
    finally:
        if db:
            db.close()


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, db: Session = None):
    """Sign up a student for an activity"""
    if db is None:
        db = SessionLocal()
    
    try:
        # Validate activity exists
        if activity_name not in activities:
            raise HTTPException(status_code=404, detail="Activity not found")

        # Get the specific activity
        activity = activities[activity_name]

        # Check if student is already signed up
        existing = db.query(Participant).filter(
            Participant.activity_name == activity_name,
            Participant.email == email
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Student is already signed up"
            )

        # Check capacity
        current_participants = db.query(Participant).filter(
            Participant.activity_name == activity_name
        ).count()
        
        if current_participants >= activity["max_participants"]:
            raise HTTPException(
                status_code=400,
                detail="Activity is at maximum capacity"
            )

        # Add student to database
        participant = Participant(
            id=f"{activity_name}:{email}",
            activity_name=activity_name,
            email=email
        )
        db.add(participant)
        db.commit()
        
        return {"message": f"Signed up {email} for {activity_name}"}
    finally:
        if db:
            db.close()


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, db: Session = None):
    """Unregister a student from an activity"""
    if db is None:
        db = SessionLocal()
    
    try:
        # Validate activity exists
        if activity_name not in activities:
            raise HTTPException(status_code=404, detail="Activity not found")

        # Find and delete the participant
        participant = db.query(Participant).filter(
            Participant.activity_name == activity_name,
            Participant.email == email
        ).first()
        
        if not participant:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity"
            )

        db.delete(participant)
        db.commit()
        
        return {"message": f"Unregistered {email} from {activity_name}"}
    finally:
        if db:
            db.close()
