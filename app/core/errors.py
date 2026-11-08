"""Единый формат ошибок API и централизованная обработка исключений.

Любая ошибка возвращается так:
{"error": {"code": "not_found", "message": "Игра 42 не найдена", "details": null}}
"""

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"

    def __init__(self, message: str, details: object = None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


def error_body(code: str, message: str, details: object = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


# Сообщения Pydantic по-русски: тип ошибки → шаблон, параметры берутся из ctx ошибки
VALIDATION_MESSAGES = {
    "missing": "обязательное поле",
    "string_too_short": "минимум {min_length} симв.",
    "string_too_long": "максимум {max_length} симв.",
    "too_short": "минимум {min_length} элем.",
    "too_long": "максимум {max_length} элем.",
    "greater_than": "должно быть больше {gt}",
    "greater_than_equal": "должно быть не меньше {ge}",
    "less_than": "должно быть меньше {lt}",
    "less_than_equal": "должно быть не больше {le}",
    "multiple_of": "должно быть кратно {multiple_of}",
    "int_parsing": "нужно целое число",
    "int_from_float": "нужно целое число",
    "float_parsing": "нужно число",
    "decimal_parsing": "нужно число",
    "decimal_max_digits": "не больше {max_digits} цифр",
    "decimal_max_places": "не больше {decimal_places} знаков после запятой",
    "bool_parsing": "нужно true или false",
    "date_parsing": "нужна дата в формате ГГГГ-ММ-ДД",
    "date_from_datetime_parsing": "нужна дата в формате ГГГГ-ММ-ДД",
    "literal_error": "допустимые значения: {expected}",
    "enum": "допустимые значения: {expected}",
    "string_type": "нужна строка",
    "list_type": "нужен список",
    "dict_type": "нужен объект",
    "json_invalid": "некорректный JSON",
}


def translate_error(error: dict) -> str:
    """Перевести сообщение ошибки валидации; неизвестный тип остаётся как есть."""
    if error["type"] == "value_error":  # наши валидаторы уже пишут по-русски
        return str(error.get("ctx", {}).get("error", error["msg"]))
    template = VALIDATION_MESSAGES.get(error["type"])
    ctx = dict(error.get("ctx", {}))
    if "expected" in ctx:  # Pydantic перечисляет варианты как "'a', 'b' or 'c'"
        ctx["expected"] = str(ctx["expected"]).replace(" or ", ", ")
    try:
        return template.format(**ctx) if template else error["msg"]
    except KeyError:
        return error["msg"]


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{**err, "msg": translate_error(err)} for err in exc.errors()]
        details = jsonable_encoder(errors, exclude={"input", "ctx", "url"})
        return JSONResponse(
            error_body("validation_error", "Некорректные данные запроса", details),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        # сюда попадают нарушения UNIQUE и CHECK, которые не поймала валидация
        return JSONResponse(
            error_body("conflict", "Данные нарушают ограничение целостности БД", str(exc.orig).splitlines()[0]),
            status_code=status.HTTP_409_CONFLICT,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(error_body(code, str(exc.detail)), status_code=exc.status_code)
