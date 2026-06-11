from fastapi.middleware.cors import CORSMiddleware

from api import ApiResponse, app, success_response


if not any(middleware.cls is CORSMiddleware for middleware in app.user_middleware):
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/", response_model=ApiResponse)
def root():
    return success_response("ok", {"message": "Robot Agent API is running"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, timeout_keep_alive=300)
