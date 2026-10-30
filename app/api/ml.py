"""ML-эндпоинты: загрузка модели, прогноз по записям и по CSV.

Модели:
- hit — вероятность, что игра станет хитом (верхние 10% по оценке игроков);
- press — вероятность, что пресса оценит игру на 75+.
"""

import io
from typing import Annotated, Any, Literal

import numpy as np
import pandas as pd
from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, Field
from sklearn.metrics import roc_auc_score

from app.core.errors import AppError
from app.ml.registry import registry

router = APIRouter(prefix="/ml", tags=["ml"])
ModelName = Literal["hit", "press"]
TARGET = "target"


class UploadResult(BaseModel):
    status: Literal["success"] = "success"
    model: ModelName
    estimator: str = Field(examples=["Pipeline"])


class PredictRequest(BaseModel):
    model: ModelName = "hit"
    records: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=1000,
        examples=[
            [
                {
                    "app_id": "504230",
                    "release_date": "2018-01-25",
                    "price": "19.99",
                    "genres": '["Action", "Indie"]',
                    "tags": '["Platformer", "Difficult"]',
                    "categories": '["Single-player"]',
                    "supported_languages": '["English", "Russian"]',
                    "windows": "True",
                    "mac": "True",
                    "linux": "True",
                }
            ]
        ],
    )


class PredictFromCsvResult(BaseModel):
    model: ModelName
    rows: int
    roc_auc: float | None = Field(description="Есть, если в CSV передана колонка target с 0/1")
    data: list[dict[str, Any]]


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.replace({np.nan: None}).to_dict(orient="records")


@router.post("/upload-model", summary="Загрузить обученную модель (pkl)")
def upload_model(model: Annotated[ModelName, Form()], file: Annotated[UploadFile, File()]) -> UploadResult:
    if not (file.filename or "").endswith(".pkl"):
        raise AppError("Нужен файл с расширением .pkl")
    estimator = registry.upload(model, file.file.read())
    return UploadResult(model=model, estimator=type(estimator).__name__)


@router.post("/predict", summary="Прогноз по одной или нескольким записям")
def predict(request: PredictRequest) -> list[dict[str, Any]]:
    frame = pd.DataFrame(request.records)
    return _records(registry.predict(request.model, frame))


@router.post("/predict-from-csv", summary="Прогноз по CSV: сырой steam_games.csv или готовые признаки")
def predict_from_csv(model: Annotated[ModelName, Form()], file: Annotated[UploadFile, File()]) -> PredictFromCsvResult:
    try:
        frame = pd.read_csv(io.BytesIO(file.file.read()), dtype=str, keep_default_na=False)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError("Файл не читается как CSV", str(exc)) from exc
    if frame.empty:
        raise AppError("CSV пустой")
    target = frame.pop(TARGET) if TARGET in frame else None
    result = registry.predict(model, frame)
    roc_auc = None
    if target is not None:
        y = pd.to_numeric(target, errors="coerce")
        if y.isna().any() or set(y.unique()) - {0, 1}:
            raise AppError("Колонка target должна содержать только 0 и 1")
        if y.nunique() == 2:
            roc_auc = round(float(roc_auc_score(y, result[f"{model}_probability"])), 4)
        result[TARGET] = y.astype(int)
    return PredictFromCsvResult(model=model, rows=len(result), roc_auc=roc_auc, data=_records(result))
