def main() -> None:
    import uvicorn

    uvicorn.run("hm_dianping_py.app.app:app", host="0.0.0.0", port=8000)
