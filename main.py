"""Start the web UI after building frontend/dist."""
if __name__ == '__main__':
    import uvicorn
    uvicorn.run('src.web_api:app', host='127.0.0.1', port=8000)
