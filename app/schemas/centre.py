from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class DiagnosticTestResponse(BaseModel):
    id: int
    centre_id: int
    name: str
    price: float = Field(..., gt=0, description="Test price must be positive")

    model_config = ConfigDict(from_attributes=True)


class DiagnosticCentreResponse(BaseModel):
    id: int
    name: str
    location: str
    tests: Optional[List[DiagnosticTestResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class DiagnosticCentreListResponse(BaseModel):
    items: List[DiagnosticCentreResponse]
    total: int
    skip: int
    limit: int


class DiagnosticTestListResponse(BaseModel):
    items: List[DiagnosticTestResponse]
    total: int
    skip: int
    limit: int
