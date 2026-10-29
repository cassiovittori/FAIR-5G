"""Erros com código estável para o frontend traduzir (chave i18n `errors.<code>`).

Formato de toda resposta de erro em JSON:
    {"detail": {"code": "run_busy", "params": {...}, "message": "texto pt-BR de fallback"}}

`message` continua em português para curl, logs e clientes antigos; quem tem i18n usa
`code` + `params`. O param `context` tem uso especial: o i18next o usa para escolher a
variante da chave (`errors.run_busy_starting`, `errors.run_busy_stopping`...).
"""
from enum import StrEnum

from fastapi import HTTPException


class ErrorCode(StrEnum):
    # código novo = uma chave `errors.<code>` em pt-BR.ts e en.ts no frontend

    # auth
    NOT_AUTHENTICATED = "not_authenticated"
    TOKEN_INVALID = "token_invalid"
    USER_NOT_FOUND = "user_not_found"
    INVALID_CREDENTIALS = "invalid_credentials"
    EMAIL_TAKEN = "email_taken"
    INVALID_ROLE = "invalid_role"

    # ambientes (runs)
    RUN_BUSY = "run_busy"                      # context: starting | running | stopping
    RUN_NOT_FOUND = "run_not_found"
    CLEANUP_IN_PROGRESS = "cleanup_in_progress"
    NOTHING_TO_STOP = "nothing_to_stop"
    STOP_WHILE_STARTING = "stop_while_starting"
    ALREADY_STOPPING = "already_stopping"

    # config do /up (também valida templates e rascunhos)
    INVALID_SLICES = "invalid_slices"
    INVALID_UES_PER_SLICE = "invalid_ues_per_slice"

    # presets (templates e rascunhos)
    PRESET_NOT_FOUND = "preset_not_found"
    PRESET_NAME_REQUIRED = "preset_name_required"
    PRESET_LIMIT_REACHED = "preset_limit_reached"

    # métricas
    UNKNOWN_METRICS = "unknown_metrics"

    # genéricos (handlers globais em main.py)
    VALIDATION_ERROR = "validation_error"
    INTERNAL_ERROR = "internal_error"


class ReasonCode(StrEnum):
    """`reason_code` das respostas 200 `{available: false, reason}` das métricas."""
    NO_ACTIVE_RUN = "no_active_run"
    PROMETHEUS_UNREACHABLE = "prometheus_unreachable"


def error_detail(code: str, message: str, **params) -> dict:
    return {"code": str(code), "params": params, "message": message}


class AppError(HTTPException):
    def __init__(self, status_code: int, code: ErrorCode, message: str, headers: dict | None = None, **params):
        super().__init__(status_code=status_code, detail=error_detail(code, message, **params), headers=headers)
