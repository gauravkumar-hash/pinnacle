from typing import Callable, Generic, Iterable, TypeVar
from enum import Enum
import csv
import io
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from sqlalchemy import ScalarResult
from sqlalchemy.orm import Session

T = TypeVar("T")

class FrontendComponent(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"

class AdminQueryColumn(BaseModel):
    id: str
    name: str
    width: str | None = None
    component: FrontendComponent = FrontendComponent.TEXT
    allow_sort: bool = False

class AdminQueryFilter(BaseModel):
    id: str
    name: str
    component: FrontendComponent = FrontendComponent.TEXT
    options: list[str] = []

class AdminQueryModel(BaseModel, Generic[T]):
    model: T
    columns: list[AdminQueryColumn]
    filters: list[AdminQueryFilter]

class AdminQueryApiParams(BaseModel):
    page: int
    rows: int | None = 20
    filters: dict = {}
    order_by: list[dict[str, str]] = []

class AdminQuery:
    def __init__(
        self,
        model: AdminQueryModel[T],
        params: AdminQueryApiParams,
        query_fn: Callable[[AdminQueryModel[T]], AdminQueryApiParams],
        transform_fn: Callable[[list[T]], list[T]]
    ):
        self.model = model
        self.params = params
        self.query_fn = query_fn
        self.transform_fn = transform_fn

    # def get_api_response(self) -> AdminQueryApiResponse:
    #     data = self.query_fn(self.model)
    #     transformed_data = self.transform_fn(data)
    #     return AdminQueryApiResponse(
    #         data=transformed_data,
    #         columns=self.model.columns,
    #         pager=self.model.pager
    #     )

    def get_csv_response(self, db: Session, formattings: dict = {}, fname: str = 'export.csv') -> StreamingResponse:
        stmt = self.query_fn(self.model, self.params)
        data_rows: ScalarResult = db.execute(stmt).scalars()
        transformed_data = self.transform_fn(data_rows)
        csv_data = self._generate_csv(transformed_data, formattings)

        return StreamingResponse(
            csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={fname}"}
        )

    def _generate_csv(self, data: list[T], formattings: dict) -> Iterable[str]:
        def format_data(id, item):
            data = getattr(item, id)
            if type(data) in formattings:
                return formattings[type(data)](data)
            elif id in formattings:
                return formattings[id](data)
            return str(data) if data is not None else ""

        # Use StringIO buffer with csv.writer for proper escaping
        buffer = io.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)

        # Write header
        writer.writerow([col.name for col in self.model.columns])
        buffer.seek(0)
        yield buffer.read()

        # Write data rows
        for item in data:
            buffer = io.StringIO()
            writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)
            row = [format_data(col.id, item) for col in self.model.columns]
            writer.writerow(row)
            buffer.seek(0)
            yield buffer.read()
