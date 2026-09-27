from sqlalchemy.orm import Session
from app.db.base import SessionLocal, engine, Base
from app.db.models import DiagnosticCentre, DiagnosticTest
from app.core.logging import logger

SAMPLE_DATA = [
    {
        "name": "Max Super Speciality Hospital Diagnostic Lab - Saket",
        "location": "1, 2 Press Enclave Road, Saket, New Delhi (Delhi NCR)",
        "tests": [
            {"name": "Complete Blood Count (CBC)", "price": 450.0},
            {"name": "Lipid Profile", "price": 750.0},
            {"name": "Thyroid Profile (T3, T4, TSH)", "price": 600.0},
            {"name": "HbA1c (Glycosylated Hemoglobin)", "price": 500.0},
        ],
    },
    {
        "name": "Apollo Diagnostics - South Extension",
        "location": "Ring Road, South Extension Part II, New Delhi (Delhi NCR)",
        "tests": [
            {"name": "Liver Function Test (LFT)", "price": 800.0},
            {"name": "Kidney Function Test (KFT)", "price": 850.0},
            {"name": "Vitamin D (25-OH)", "price": 1200.0},
            {"name": "Vitamin B12", "price": 1100.0},
        ],
    },
    {
        "name": "Fortis Memorial Research Institute Lab - Gurugram",
        "location": "Sector 44, Opposite Millennium City Centre, Gurugram (Delhi NCR)",
        "tests": [
            {"name": "Comprehensive Full Body Health Checkup", "price": 2499.0},
            {"name": "Urine Routine & Microscopic", "price": 250.0},
            {"name": "Fasting Blood Glucose", "price": 150.0},
        ],
    },
]


def seed_database(db: Session = None) -> None:
    close_at_end = False
    if db is None:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        close_at_end = True

    try:
        # Check if already seeded
        centres = db.query(DiagnosticCentre).order_by(DiagnosticCentre.id).all()
        if centres:
            # Update existing records to Delhi NCR
            for idx, c in enumerate(centres):
                if idx < len(SAMPLE_DATA):
                    c.name = SAMPLE_DATA[idx]["name"]
                    c.location = SAMPLE_DATA[idx]["location"]
            db.commit()
            logger.info("Diagnostic centres refreshed with Delhi NCR locations.")
            return

        for centre_info in SAMPLE_DATA:
            centre = DiagnosticCentre(
                name=centre_info["name"],
                location=centre_info["location"],
            )
            db.add(centre)
            db.flush()  # to obtain centre.id

            for test_info in centre_info["tests"]:
                test = DiagnosticTest(
                    centre_id=centre.id,
                    name=test_info["name"],
                    price=test_info["price"],
                )
                db.add(test)

        db.commit()
        logger.info("Successfully seeded diagnostic centres and tests.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        if close_at_end:
            db.close()


if __name__ == "__main__":
    seed_database()
