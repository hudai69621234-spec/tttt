import os
import re
import uuid
from urllib.parse import quote, unquote
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI(title="Facebook Reliable Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COOKIES_FILE = "cookies.txt"
PROXY_FILE = "proxy.txt"
DOWNLOAD_DIR = "downloads"

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

def remove_file(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"Error deleting file: {e}")

def clean_and_resolve_url(url: str) -> str:
    try:
        url = unquote(url)
        return re.sub(r'(\?|\&)(mibextid|rdid|share_id)=[^&]+', '', url)
    except Exception:
        return url

def get_base_opts():
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'no_color': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }
    
    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        ydl_opts['cookiefile'] = COOKIES_FILE
        
    if os.path.exists(PROXY_FILE) and os.path.getsize(PROXY_FILE) > 0:
        with open(PROXY_FILE, 'r', encoding='utf-8') as f:
            proxy_url = f.read().strip()
            if proxy_url:
                ydl_opts['proxy'] = proxy_url
                
    return ydl_opts

@app.get("/", response_class=HTMLResponse)
def read_root():
    return FileResponse("index.html")

@app.get("/api/fb-download")
def download_fb_info(url: str = Query(..., description="Facebook Video/Reel URL")):
    clean_url = clean_and_resolve_url(url)
    ydl_opts = get_base_opts()

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            
            encoded_url = quote(clean_url, safe='')
            
            # সার্ভার-সাইড ডাউনলোড এন্ডপয়েন্ট লিংক তৈরি করা হচ্ছে
            download_720_url = f"http://127.0.0.1:8000/api/download-720p?url={encoded_url}"
            download_1080_url = f"http://127.0.0.1:8000/api/render-1080p?url={encoded_url}"

            medias = [
                {
                    "quality": "720p (HD)",
                    "need_render": False,
                    "download_url": download_720_url
                },
                {
                    "quality": "1080p (Full HD)",
                    "need_render": True,
                    "download_url": download_1080_url
                }
            ]

            return {
                "status": "success",
                "title": info.get('title', 'Facebook Video'),
                "thumbnail": info.get('thumbnail'),
                "duration": info.get('duration_string', 'N/A'),
                "medias": medias
            }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing video: {str(e)}")

@app.get("/api/download-720p")
def download_720p_video(url: str, background_tasks: BackgroundTasks):
    clean_url = clean_and_resolve_url(url)
    file_id = uuid.uuid4().hex[:8]
    output_path = os.path.join(DOWNLOAD_DIR, f"fb_720p_{file_id}.mp4")

    ydl_opts = get_base_opts()
    ydl_opts.update({
        'format': 'best[height<=720]/best',
        'outtmpl': output_path,
    })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([clean_url])

        background_tasks.add_task(remove_file, output_path)

        return FileResponse(
            path=output_path,
            filename=f"Facebook_720p_{file_id}.mp4",
            media_type="application/octet-stream",
            content_disposition_type="attachment"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@app.get("/api/render-1080p")
def render_1080p_video(url: str, background_tasks: BackgroundTasks):
    clean_url = clean_and_resolve_url(url)
    file_id = uuid.uuid4().hex[:8]
    output_path = os.path.join(DOWNLOAD_DIR, f"fb_1080p_{file_id}.mp4")

    ydl_opts = get_base_opts()
    ydl_opts.update({
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
    })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([clean_url])

        background_tasks.add_task(remove_file, output_path)

        return FileResponse(
            path=output_path,
            filename=f"Facebook_1080p_{file_id}.mp4",
            media_type="application/octet-stream",
            content_disposition_type="attachment"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering failed: {str(e)}")
