"""Seed the database with a fixed set of real opportunities.

Run once with:  python -m data.seed_opportunities

The opportunities are hardcoded here (a curated list) rather than scraped live,
which keeps the demo reliable. To reset the data, delete instance/app.db and
run this script again.
"""
# NOTE: `app` is imported lazily inside seed() (not at module top) to avoid a
# circular import. app.py imports OPPORTUNITIES from this module at startup,
# so this module must be safe to import without triggering an `app` import.
from database import db
from models import Opportunity

# Curated list of real scholarships/internships. Add more dicts here (same shape)
# to grow the dataset — e.g. expand from 6 to 20-30 entries.
OPPORTUNITIES = [
    {
        "title": "Software Engineering Intern",
        "organization": "RBC",
        "type": "Internship",
        "field": "Computer Science",
        "location": "Toronto, ON",
        "gpa_requirement": "3.0+",
        "required_skills": "Python, SQL, Git, teamwork, communication",
        "description": "Build internal tools and support financial technology systems. Work with senior engineers on production code. Open to undergraduate students in CS, software engineering, or related fields.",
        "deadline": "2026-09-30",
    },
    {
        "title": "Schulich Leader Scholarship",
        "organization": "Schulich Foundation",
        "type": "Scholarship",
        "field": "STEM",
        "location": "Canada (any participating university)",
        "gpa_requirement": "85%+ average",
        "required_skills": "Leadership, entrepreneurship, academic excellence in STEM",
        "description": "$100,000 entrance scholarship for incoming undergraduate STEM students. Requires nomination from your high school. Looks for technological innovation, entrepreneurial drive, and civic engagement.",
        "deadline": "2026-01-25",
    },
    {
        "title": "Shopify Dev Degree",
        "organization": "Shopify",
        "type": "Internship",
        "field": "Software Engineering",
        "location": "Toronto / Ottawa / Remote (Canada)",
        "gpa_requirement": "No strict GPA cutoff",
        "required_skills": "Ruby on Rails, JavaScript, React, problem-solving, eagerness to learn",
        "description": "4-year paid work-integrated degree program combining university study with full-time engineering work at Shopify. Open to incoming first-year university students.",
        "deadline": "2026-03-15",
    },
    {
        "title": "TD Bank Technology Analyst",
        "organization": "TD Bank Group",
        "type": "Internship",
        "field": "Technology / Business Tech",
        "location": "Toronto, ON",
        "gpa_requirement": "3.0+",
        "required_skills": "Java or Python, SQL, business acumen, communication",
        "description": "16-month internship working on enterprise banking systems. Rotational program across engineering, data, and product teams.",
        "deadline": "2026-10-15",
    },
    {
        "title": "Loran Scholars Award",
        "organization": "Loran Scholars Foundation",
        "type": "Scholarship",
        "field": "Any field",
        "location": "Canada",
        "gpa_requirement": "85%+ average",
        "required_skills": "Character, service, leadership potential",
        "description": "$100,000 four-year undergraduate scholarship based on character, service, and leadership rather than purely academic performance. Includes summer programs and mentorship.",
        "deadline": "2026-10-23",
    },
    {
        "title": "Microsoft Software Engineering Intern",
        "organization": "Microsoft Canada",
        "type": "Internship",
        "field": "Computer Science",
        "location": "Vancouver / Toronto / Remote",
        "gpa_requirement": "3.0+",
        "required_skills": "C#, C++, Python, data structures, algorithms",
        "description": "12-16 week summer internship building features used by millions of customers. Open to students in CS, software engineering, or related disciplines.",
        "deadline": "2026-11-30",
    },
]


def seed():
    """Create the tables and insert the opportunities (skips if already seeded)."""
    from app import app                      # lazy import — see note at top
    with app.app_context():                  # DB work needs the Flask app context
        db.create_all()                      # create tables if they don't exist
        # Avoid inserting duplicates if this script is run more than once.
        if Opportunity.query.count() > 0:
            print("Opportunities already seeded. Skipping.")
            return
        for opp in OPPORTUNITIES:
            db.session.add(Opportunity(**opp))
        db.session.commit()
        print(f"Seeded {len(OPPORTUNITIES)} opportunities.")


if __name__ == "__main__":
    seed()
