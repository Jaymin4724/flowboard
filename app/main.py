from fastapi import FastAPI, status
from app.api.v1.api import api_router
from app.middleware.logging_middleware import log_requests_middleware
from app.middleware.rate_limitting_middleware import rate_limitter_middleware
from app.api.v1.schemas.response import ResponseSchema, create_response

app = FastAPI(title="FlowBoard", description="Scalable Task Management Platform")

app.middleware("http")(rate_limitter_middleware)
app.middleware("http")(log_requests_middleware)

app.include_router(api_router)

@app.get("/", status_code=status.HTTP_200_OK, response_model=ResponseSchema)
def root():
    return create_response([], "Server is running!")