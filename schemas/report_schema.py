from pydantic import BaseModel
from typing import List

class NRICListRequest(BaseModel):
    nrics: List[str]
