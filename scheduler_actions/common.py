from models import CronLog
from sqlalchemy.orm import Session
from datetime import datetime
from utils import sg_datetime
from utils.integrations.sgimed import get

def load_cron_log(db: Session, id: str):
    record = db.query(CronLog).filter(CronLog.id == id).first()
    if not record:
        record = CronLog(id=id, last_modified=datetime(2000, 1, 1))
        db.add(record)
        db.commit()
    
    return record

class CronLogAPI:
    def __init__(self, db: Session, cron_id: str, endpoint, **kwargs):
        self.db = db
        self.cron_log = load_cron_log(db, cron_id)
        modified_since = self.cron_log.last_modified
        last_page = self.cron_log.last_page if self.cron_log.last_page else 1
        self.start_time = sg_datetime.now()
        self.data, self.next_page = fetch_updates_by_time_and_page(endpoint, modified_since, last_page, **kwargs)

    def commit(self):
        if self.next_page:
            self.cron_log.last_page = self.next_page
        else:
            self.cron_log.last_modified = self.start_time.replace(tzinfo=None)
            self.cron_log.last_page = None
        self.db.commit()

def fetch_updates_by_time_and_page(endpoint: str, modified_since: datetime, page: int, **kwargs):
    # Start with Page 1
    modified_since_str = modified_since.strftime("%Y-%m-%d %H:%M:%S")
    print(f"Fetching {endpoint}, {modified_since}, page {page}")
    resp = get(endpoint, { "modified_since": modified_since_str, "page": page, **kwargs })
    updated_rows = resp['data']
    # Restrict these endpoints to only 1 pages
    max_pages = 1 if endpoint in ['/order/mc', '/invoice'] else 5
    last_page = page
    # Only apply to appointment types API since it does not have pager
    if 'pager' not in resp:
        return updated_rows, None
    
    # More than Page 1, If pages more than 5, only take 5 pages to prevent overload
    for i in range(page + 1, min(resp['pager']['pages'] + 1, page + max_pages)):
        print(f"Fetching {endpoint}, {modified_since}, page {i}")
        resp = get(endpoint, { "modified_since": modified_since_str, "page": i, **kwargs })
        updated_rows += resp['data']
        last_page = i

    return updated_rows, last_page + 1 if last_page < resp['pager']['pages'] else None
