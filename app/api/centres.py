from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import DiagnosticCentre, DiagnosticTest
from app.schemas.centre import DiagnosticCentreResponse, DiagnosticTestResponse

router = APIRouter(prefix="/centres", tags=["Diagnostic Centres"])


@router.get("/", response_model=List[DiagnosticCentreResponse])
def get_centres(
    skip: int = Query(0, ge=0, description="Items to skip for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Max items to return"),
    db: Session = Depends(get_db),
) -> List[DiagnosticCentre]:
    centres = db.query(DiagnosticCentre).offset(skip).limit(limit).all()
    return centres


@router.get("/{centre_id}/tests", response_model=List[DiagnosticTestResponse])
def get_centre_tests(
    centre_id: int,
    skip: int = Query(0, ge=0, description="Items to skip for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Max items to return"),
    db: Session = Depends(get_db),
) -> List[DiagnosticTest]:
    centre = db.query(DiagnosticCentre).filter(DiagnosticCentre.id == centre_id).first()
    if not centre:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic centre with ID {centre_id} not found",
        )

    tests = (
        db.query(DiagnosticTest)
        .filter(DiagnosticTest.centre_id == centre_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return tests
