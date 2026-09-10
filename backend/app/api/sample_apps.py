"""GET /sample-apps."""

from fastapi import APIRouter

from app.models.sample_app import SampleAppResponse
from app.services.sample_apps import SAMPLE_APPS

router = APIRouter(tags=["sample-apps"])


@router.get("/sample-apps", response_model=list[SampleAppResponse])
def list_sample_apps() -> list[SampleAppResponse]:
    return [SampleAppResponse(id=a.id, name=a.name, description=a.description) for a in SAMPLE_APPS]
