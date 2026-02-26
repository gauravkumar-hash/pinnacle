import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from models import get_db
from models.model_enums import CollectionMethod, ContentCategory, DayOfWeek
from models.pinnacle import Branch, Content, OperatingHour
from routers.patient.utils import validate_firebase_token
from sqlalchemy.orm import Session
from datetime import time
from utils import sg_datetime
from utils.system_config import get_config_value

router = APIRouter(dependencies=[Depends(validate_firebase_token)])

class BannerItem(BaseModel):
    headerTag: str | None = None
    title: str | None = None
    imageUrl: str
    imageRatio: float;
    actionText: str | None = None
    url: str

class Discover(BaseModel):
    title: str
    subtitle: str | None = None
    price: str | None = None
    imageUrl: str
    imageRatio: float
    url: str

class Banners(BaseModel):
    topSlider: list[BannerItem]
    highlights: list[BannerItem]
    discover: list[Discover]

default_banners = Banners(
    topSlider=[
        BannerItem(
            title="Vaccination",
            imageUrl="https://yaadelemrtuxfyxayxpu.supabase.co/storage/v1/object/public/uploads/home_banners/vaccinations.jpg",
            imageRatio=0.55,
            url="pinnaclesgplus://browser?url=https://pinnaclefamilyclinic.com.sg/medical-services/vaccinations/",
            actionText="Read"
        )
    ],
    highlights=[],
    discover=[],
)

@router.get('/banners', response_model=Banners)
def get_banners(db: Session = Depends(get_db)):
    banners = get_config_value(db, 'HOME_BANNERS', default_banners) # type: ignore
    return Banners.model_validate(banners)

class CarouselDetail(BaseModel):
    title: str
    image: Optional[str] = None
    url: str

@router.get('/carousel', response_model=list[CarouselDetail])
def get_carousel(db: Session = Depends(get_db)):
    records = db.query(Content).filter(Content.category == ContentCategory.HOME_BANNER).order_by(Content.sort_order).all()
    rows = []
    for r in records:
        data = json.loads(r.content)
        if not data:
            continue

        rows.append(CarouselDetail(
            title=r.title,
            image=data.get('image'),
            url=data.get('url')
        ))

    return rows

class BranchList(BaseModel):
    id: str
    name: str
    category: str
    availability: str
    # Legacy Fields
    image_url: Optional[str]
    operating_tag: str

@router.get('/branches', response_model=list[BranchList])
def get_branches(db: Session = Depends(get_db)):
    branches = db.query(Branch).filter(Branch.deleted == False, Branch.hidden == False).all()

    curr_dt = sg_datetime.now()
    def map_branch(branch: Branch):
        availability = 'Closed'
        operating = branch.is_operating(db, curr_dt, CollectionMethod.WALKIN)
        if operating:
            availability = 'Open'
        else:
            operating = branch.get_next_operating_hour(db, curr_dt, CollectionMethod.WALKIN)
            if operating:
                start_time_format = "%-I%p" if operating.start_time.minute == 0 else "%-I:%M%p"
                availability = f'Closed (Opens at {operating.start_time.strftime(start_time_format)})'

        return BranchList(
                id=str(branch.id),
                name=branch.name,
                category=branch.category,
                availability=availability,
                # Legacy Fields
                image_url=branch.image_url,
                operating_tag=availability
            )

    return [ map_branch(branch) for branch in branches ]

class OperatingHourDay(BaseModel):
    day: str
    hours: str

class BranchResp(BaseModel):
    name: str
    url: Optional[str]
    image_url: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    whatsapp: Optional[str]
    email: Optional[str]
    operating_hours: list[OperatingHourDay]

@router.get('/branch/{branch_id}', response_model=BranchResp)
def get_branch_details(branch_id: str, db: Session = Depends(get_db)):
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=400, detail="Branch not found")

    operating_hours = db.query(OperatingHour).filter(OperatingHour.branch_id == branch.id).order_by(OperatingHour.start_time).all()

    def time_to_str(curr_time: time):
        time_format = "%-I%p" if curr_time.minute == 0 else "%-I:%M%p"
        return curr_time.strftime(time_format)

    def hour_by_day(day: DayOfWeek):
        hours = ", ".join([f'{time_to_str(hr.start_time)}-{time_to_str(hr.end_time)}' for hr in operating_hours if hr.day == day])
        return OperatingHourDay(
            day=day.value,
            hours=hours if hours else 'CLOSED'
        )

    return BranchResp(
        name=branch.name,
        url=branch.url,
        image_url=branch.image_url,
        address=branch.address,
        phone=branch.phone,
        whatsapp=branch.whatsapp,
        email=branch.email,
        operating_hours=[hour_by_day(day) for day in DayOfWeek]
    )

class ContentResp(BaseModel):
    title: str
    content: str

@router.get('/about_us', response_model=list[ContentResp])
def about_us(db: Session = Depends(get_db)):
    records = db.query(Content).filter(Content.category == ContentCategory.ABOUT_US).order_by(Content.sort_order).all()
    return [ContentResp(title=r.title, content=r.content) for r in records]

@router.get('/faq', response_model=list[ContentResp])
def faq(db: Session = Depends(get_db)):
    records = db.query(Content).filter(Content.category == ContentCategory.FAQ).order_by(Content.sort_order).all()
    return [ContentResp(title=r.title, content=r.content) for r in records]

@router.get('/v2/faq', response_model=list[ContentResp])
def faq_v2(db: Session = Depends(get_db)):
    records = db.query(Content).filter(Content.category == ContentCategory.FAQ_SECTION).order_by(Content.sort_order).all()
    return [ContentResp(title=r.title, content=r.content) for r in records]

@router.get('/privacy_policy', response_model=list[ContentResp])
def privacy_policy(db: Session = Depends(get_db)):
    records = db.query(Content).filter(Content.category == ContentCategory.PRIVACY_POLICY).order_by(Content.sort_order).all()
    return [ContentResp(title=r.title, content=r.content) for r in records]
