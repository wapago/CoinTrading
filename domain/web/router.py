from fastapi import APIRouter, Request, Depends
from fastapi.security import APIKeyHeader
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from config import templates_path


router = APIRouter(
    tags=['Web'],
    include_in_schema=True,
    default_response_class=HTMLResponse,
)
templates = Jinja2Templates(directory=templates_path)


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, '/client/admin.html')


@router.get("/admin")
async def index(request: Request):
    print("admin")
    return templates.TemplateResponse(request, '/client/admin.html')