"""Create the sample database at DATABASE_URL (default data/expenses.db)."""

from db import Base, Expense, SessionLocal, User, engine

USERS = [
    User(id="ana", name="Ana Silva", roles="employee", department="sales", region="emea"),
    User(id="ben", name="Ben Okafor", roles="employee", department="engineering", region="amer"),
    User(id="marco", name="Marco Rossi", roles="manager", department="sales", region="emea"),
    User(id="fiona", name="Fiona Walsh", roles="finance", department="finance", region="emea", review_threshold=1000),
    User(id="olga", name="Olga Petrova", roles="auditor", department="audit", region="amer"),
]

EXPENSES = [
    Expense(id=1, owner_id="ana", department="sales", region="emea", amount=80, status="draft", description="Taxi"),
    Expense(id=2, owner_id="ana", department="sales", region="emea", amount=4000, status="submitted", description="Trade show booth"),
    Expense(id=3, owner_id="ana", department="sales", region="emea", amount=4000, status="approved", archived=True, description="Last year's booth"),
    Expense(id=4, owner_id="ben", department="engineering", region="amer", amount=1200, status="submitted", description="Conference ticket"),
    Expense(id=5, owner_id="marco", department="sales", region="emea", amount=300, status="approved", description="Team lunch"),
]

if __name__ == "__main__":
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        session.add_all(USERS + EXPENSES)
        session.commit()
    print(f"Seeded {len(USERS)} users and {len(EXPENSES)} expense reports")
