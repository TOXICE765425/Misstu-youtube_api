from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import html
import os

import yt_dlp


# ==========================================
# MISSTU SONG SEARCH API
# ==========================================

API_NAME = "Misstu Song Search API"
API_VERSION = "2.0.0"
POWERED_BY = "Toxice Hacker"
DEVELOPER = "@misstu001"


# ==========================================
# JSON RESPONSE HELPER
# ==========================================

def send_json(handler, status_code, data):

    body = json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    ).encode("utf-8")

    handler.send_response(status_code)

    handler.send_header(
        "Content-Type",
        "application/json; charset=utf-8"
    )

    handler.send_header(
        "Access-Control-Allow-Origin",
        "*"
    )

    handler.send_header(
        "Access-Control-Allow-Methods",
        "GET, OPTIONS"
    )

    handler.send_header(
        "Access-Control-Allow-Headers",
        "*"
    )

    handler.send_header(
        "Content-Length",
        str(len(body))
    )

    handler.end_headers()

    handler.wfile.write(body)


# ==========================================
# YT-DLP AUDIO URL EXTRACTOR
# ==========================================

def get_mp3_url(video_id):

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "cachedir": False,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web"]
            }
        },
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}",
            download=False
        )

    return {
        "mp3_url": info.get("url"),
        "ext": info.get("ext"),
        "format": info.get("format"),
        "duration": info.get("duration"),
        "duration_string": info.get("duration_string"),
        "bitrate": info.get("abr"),
        "filesize": info.get("filesize") or info.get("filesize_approx"),
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "thumbnail": info.get("thumbnail"),
    }


# ==========================================
# MAIN HANDLER
# ==========================================

class handler(BaseHTTPRequestHandler):

    # ======================================
    # OPTIONS / CORS
    # ======================================

    def do_OPTIONS(self):

        send_json(
            self,
            200,
            {
                "success": True,
                "powered_by": POWERED_BY,
                "developer": DEVELOPER
            }
        )

    # ======================================
    # GET
    # ======================================

    def do_GET(self):

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)

        # ==================================
        # HOME
        # ==================================

        if path == "/" or path == "":

            send_json(
                self,
                200,
                {
                    "success": True,
                    "name": API_NAME,
                    "version": API_VERSION,
                    "powered_by": POWERED_BY,
                    "developer": DEVELOPER,
                    "endpoints": {
                        "search": "/api/song?query=Tum%20Hi%20Ho",
                        "mp3": "/api/mp3?video_id=Umqb9KENgmk"
                    }
                }
            )
            return

        # ==================================
        # SONG SEARCH
        # ==================================

        if path == "/api/song":
            self.handle_search(params)
            return

        # ==================================
        # MP3 URL
        # ==================================

        if path == "/api/mp3":
            self.handle_mp3(params)
            return

        # ==================================
        # NOT FOUND
        # ==================================

        send_json(
            self,
            404,
            {
                "success": False,
                "error": "Endpoint not found",
                "powered_by": POWERED_BY,
                "developer": DEVELOPER
            }
        )

    # ======================================
    # HANDLE: /api/song
    # ======================================

    def handle_search(self, params):

        query = params.get("query", [""])[0].strip()

        if not query:

            send_json(
                self,
                400,
                {
                    "success": False,
                    "error": "query parameter is required",
                    "example": "/api/song?query=Tum%20Hi%20Ho",
                    "powered_by": POWERED_BY,
                    "developer": DEVELOPER
                }
            )
            return

        API_KEY = os.environ.get("YOUTUBE_API_KEY")

        if not API_KEY:

            send_json(
                self,
                500,
                {
                    "success": False,
                    "error": "YOUTUBE_API_KEY is not configured",
                    "powered_by": POWERED_BY,
                    "developer": DEVELOPER
                }
            )
            return

        youtube_url = (
            "https://www.googleapis.com/youtube/v3/search"
            "?part=snippet"
            "&q=" + quote(query) +
            "&type=video"
            "&maxResults=10"
            "&order=relevance"
            "&regionCode=IN"
            "&key=" + quote(API_KEY)
        )

        try:

            request = Request(
                youtube_url,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            with urlopen(request, timeout=15) as result:

                youtube_data = json.loads(
                    result.read().decode("utf-8")
                )

        except HTTPError as error:

            try:
                error_data = json.loads(error.read().decode("utf-8"))
            except Exception:
                error_data = {"message": str(error)}

            send_json(
                self,
                error.code,
                {
                    "success": False,
                    "query": query,
                    "error": error_data,
                    "powered_by": POWERED_BY,
                    "developer": DEVELOPER
                }
            )
            return

        except URLError as error:

            send_json(
                self,
                502,
                {
                    "success": False,
                    "query": query,
                    "error": "YouTube connection failed",
                    "details": str(error),
                    "powered_by": POWERED_BY,
                    "developer": DEVELOPER
                }
            )
            return

        except Exception as error:

            send_json(
                self,
                500,
                {
                    "success": False,
                    "query": query,
                    "error": str(error),
                    "powered_by": POWERED_BY,
                    "developer": DEVELOPER
                }
            )
            return

        # ==================================
        # FORMAT RESULTS
        # ==================================

        results = []

        for item in youtube_data.get("items", []):

            video_id = item.get("id", {}).get("videoId")

            if not video_id:
                continue

            snippet = item.get("snippet", {})

            title = html.unescape(snippet.get("title", ""))
            description = html.unescape(snippet.get("description", ""))

            thumbnails = snippet.get("thumbnails", {})

            thumbnail = (
                thumbnails.get("high", {}).get("url")
                or thumbnails.get("medium", {}).get("url")
                or thumbnails.get("default", {}).get("url")
            )

            results.append(
                {
                    "video_id": video_id,
                    "title": title,
                    "artist": snippet.get("channelTitle"),
                    "channel": snippet.get("channelTitle"),
                    "description": description,
                    "published_at": snippet.get("publishedAt"),
                    "thumbnail": thumbnail,
                    "youtube_url":
                        "https://www.youtube.com/watch?v=" + video_id,
                    "mp3_endpoint":
                        "/api/mp3?video_id=" + video_id
                }
            )

        send_json(
            self,
            200,
            {
                "success": True,
                "query": query,
                "count": len(results),
                "results": results,
                "powered_by": POWERED_BY,
                "developer": DEVELOPER
            }
        )

    # ======================================
    # HANDLE: /api/mp3
    # ======================================

    def handle_mp3(self, params):

        video_id = params.get("video_id", [""])[0].strip()

        if not video_id:

            send_json(
                self,
                400,
                {
                    "success": False,
                    "error": "video_id parameter is required",
                    "example": "/api/mp3?video_id=Umqb9KENgmk",
                    "powered_by": POWERED_BY,
                    "developer": DEVELOPER
                }
            )
            return

        try:

            audio = get_mp3_url(video_id)

            if not audio.get("mp3_url"):

                send_json(
                    self,
                    404,
                    {
                        "success": False,
                        "error": "Audio stream not found",
                        "video_id": video_id,
                        "powered_by": POWERED_BY,
                        "developer": DEVELOPER
                    }
                )
                return

            send_json(
                self,
                200,
                {
                    "success": True,
                    "video_id": video_id,
                    "mp3_url": audio["mp3_url"],
                    "ext": audio["ext"],
                    "format": audio["format"],
                    "duration": audio["duration"],
                    "duration_string": audio["duration_string"],
                    "bitrate": audio["bitrate"],
                    "filesize": audio["filesize"],
                    "title": audio["title"],
                    "uploader": audio["uploader"],
                    "thumbnail": audio["thumbnail"],
                    "youtube_url":
                        "https://www.youtube.com/watch?v=" + video_id,
                    "powered_by": POWERED_BY,
                    "developer": DEVELOPER
                }
            )

        except Exception as error:

            send_json(
                self,
                500,
                {
                    "success": False,
                    "video_id": video_id,
                    "error": str(error),
                    "powered_by": POWERED_BY,
                    "developer": DEVELOPER
                }
            )
            return