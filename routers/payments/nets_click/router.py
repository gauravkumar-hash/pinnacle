from datetime import datetime
import json
import os
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .helpers import GmtReg, NofPurchaseApi, get_unique_ref_num, nof_gmt_reg, nof_purchase

router = APIRouter()

class NetsClickRegisterReq(BaseModel):
    nof: str

@router.post("/api/nets_click/register")
def register(req: NetsClickRegisterReq, request: Request):
    ref_num = get_unique_ref_num()
    nof_gmt_reg(req.nof, ref_num)
    return {"status": "ok"}

class NetsClickDeregisterReq(BaseModel):
    muuid: str

@router.get("/api/nets_click/deregister")
def deregister(req: NetsClickDeregisterReq, request: Request):
    print(f"Deregistering {req.muuid}: {datetime.now().strftime('%Y-%m-%d %H%M%S')}")
    os.remove('gmt_reg.json')
    return {"status": "ok"}

class NetsClickPurchaseReq(BaseModel):
    nof: NofPurchaseApi

@router.post("/api/nets_click/purchase")
def purchase(req: NetsClickPurchaseReq):
    with open('gmt_reg.json') as f:
        gmt_reg = json.load(f)[0]
        gmt_reg = GmtReg(**gmt_reg)

    muid = "88281231234"
    ref_num = get_unique_ref_num()
    amt = req.nof.amt
    resp = nof_purchase(gmt_reg, req.nof, muid, ref_num, amt)
    if not resp:
        raise HTTPException(500, "NETS Click failed")
    
    # Approved Transaction
    if resp.body.response_code == '00':
        return {
            "status": "approved",
        }
    
    # Handle PIN Mode
    cryptogram = ''
    if resp.body.response_code in ['U9', '55']:
        for r in resp.body.txn_specific_data:
            if r.sub_id == '53':
                cryptogram = f"{r.sub_id}{r.sub_length}{r.sub_data}"
    
        if not cryptogram:
            raise HTTPException(500, "NETS Click: Require PIN but Cryptogram not found")
        
        return {
            "status": resp.body.response_code,
            "cryptogram": cryptogram
        }
        
    raise HTTPException(500, f"NETS Click: {resp.body.response_code}")

# nets_click
# nets_qr
# 2c2p
