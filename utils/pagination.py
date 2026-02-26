from typing import Generic, TypeVar, Optional
from fastapi import Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, select

T = TypeVar("T")
MAX_RESULTS_PER_PAGE = 20

class PaginationInput(BaseModel):
    page: int = Field(default=1, ge=1, description="Requested page number")

class Pager(BaseModel):
    p: int = Field(ge=0, description="Page number")
    n: int = Field(ge=0, description="Number of items per page")
    pages: int = Field(ge=0, description="Total number of pages")
    rows: int = Field(ge=0, description="Number of total items")

class Page(BaseModel, Generic[T]):
    pager: Pager = Field(description="Pagination metadata")
    data: list[T] = Field(description="List of items on this Page")

def paginate(
    query,  # SQLAlchemy query
    db: Session,
    pagination_input: PaginationInput,
) -> Page[T]:
    # Get total count
    total_items = db.scalar(select(func.count()).select_from(query.subquery()))
    
    # Calculate pagination
    total_pages = max((total_items + MAX_RESULTS_PER_PAGE - 1) // MAX_RESULTS_PER_PAGE, 1)
    current_page = min(pagination_input.page, total_pages)
    offset = (current_page - 1) * MAX_RESULTS_PER_PAGE
    
    # Apply pagination to query
    items = query.offset(offset).limit(MAX_RESULTS_PER_PAGE).all()
    
    return Page[T](
        pager=Pager(
            p=current_page,
            n=0 if total_items == 0 else MAX_RESULTS_PER_PAGE,
            pages=total_pages,
            rows=total_items,
        ),
        data=items
    )

PaginationDep = Query(...)