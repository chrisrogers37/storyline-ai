"""Pydantic request/response models for onboarding API."""

from pydantic import BaseModel, Field


class InitRequest(BaseModel):
    init_data: str
    chat_id: int


class MediaFolderRequest(BaseModel):
    init_data: str
    chat_id: int
    folder_url: str


class StartIndexingRequest(BaseModel):
    init_data: str
    chat_id: int


class ScheduleRequest(BaseModel):
    init_data: str
    chat_id: int
    posts_per_day: int = Field(ge=1, le=50)
    posting_hours_start: int = Field(ge=0, le=23)
    posting_hours_end: int = Field(ge=0, le=23)


class CompleteRequest(BaseModel):
    init_data: str
    chat_id: int
    create_schedule: bool = False
    schedule_days: int = Field(default=7, ge=1, le=30)


class ToggleSettingRequest(BaseModel):
    init_data: str
    chat_id: int
    setting_name: str


class UpdateSettingRequest(BaseModel):
    init_data: str
    chat_id: int
    setting_name: str
    value: int = Field(ge=0, le=50)


class SwitchAccountRequest(BaseModel):
    init_data: str
    chat_id: int
    account_id: str


class RemoveAccountRequest(BaseModel):
    init_data: str
    chat_id: int
    account_id: str


class ScheduleActionRequest(BaseModel):
    init_data: str
    chat_id: int
    days: int = Field(default=7, ge=1, le=30)
