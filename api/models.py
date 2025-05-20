from pydantic import BaseModel, Field
from typing import Union, Annotated
import datetime


class Response(BaseModel):
    connected: bool
    reason: str | None = None


class PublishResponse(BaseModel):
    success: bool
    reason: str | None = None


class PublishAndWaitReplyResponse(BaseModel):
    success: bool
    topic: str | None = None
    payload: str | dict | None = None
    key: str | None = None
    value: str | dict | None = None
    timestamp: float | None = None
    datetime: str | None = None
    reason: str | None = None


class BrokerCredentials(BaseModel):
    host: Annotated[str, Field(min_length=1, frozen=True)] | None = None
    port: Annotated[int, Field(ge=1000, le=10000, frozen=True)] | None = None
    username: Annotated[str, Field(frozen=True)] | None = None
    password: Annotated[str, Field(frozen=True)] | None = None
    ssl: Annotated[int, Field(ge=0, le=1, frozen=True)] | None = None


class ResponseBrokerCredentials(BrokerCredentials):
    connected: bool
    last_connection_time: str | None = None


default_brokercredentials = BrokerCredentials().model_validate({"host": "test.mosquitto.org", "port": 1883,
                                                                "username": str(), "password": str(), "ssl": 0})
