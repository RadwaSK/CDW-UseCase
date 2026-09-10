"""Response schema for GET /sample-apps."""

from pydantic import BaseModel


class SampleAppResponse(BaseModel):
    id: str
    name: str
    description: str
