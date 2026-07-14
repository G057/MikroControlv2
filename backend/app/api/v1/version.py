from fastapi import APIRouter
from app.core.version import VERSION_INFO

router = APIRouter()


@router.get("")
def get_version():
    return VERSION_INFO
