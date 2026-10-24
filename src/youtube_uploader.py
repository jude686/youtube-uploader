import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional

import config

logger = logging.getLogger("ParableTales.YouTubeUploader")


class YouTubeUploader:
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

    def __init__(
        self,
        client_secrets_file: str = config.YOUTUBE_CLIENT_SECRETS_FILE,
        token_file: str = config.YOUTUBE_TOKEN_FILE
    ):
        self.client_secrets_file = Path(client_secrets_file)
        self.token_file = Path(token_file)
        self.service = None

    def authenticate(self, allow_browser: bool = True):
        """
        Authenticates with YouTube Data API v3.
        Loads existing token.json if present; otherwise prompts for one-time OAuth
        consent and caches permanent refresh token.
        """
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None
        if self.token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
            except Exception as e:
                logger.warning(f"Could not load token file: {e}")

        # Refresh or prompt
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired YouTube OAuth token...")
                creds.refresh(Request())
            elif allow_browser:
                if not self.client_secrets_file.exists():
                    raise FileNotFoundError(
                        f"Google Cloud client secret file not found at: {self.client_secrets_file}\n"
                        "Please download your OAuth 2.0 Client ID (Desktop app) credentials from "
                        "Google Cloud Console and save it to credentials/client_secret.json."
                    )
                logger.info("Opening local browser for one-time YouTube authentication...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.client_secrets_file), self.SCOPES
                )
                creds = flow.run_local_server(port=0)

                # Save token for all future autonomous runs
                self.token_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_file, "w") as token:
                    token.write(creds.to_json())
                logger.info(f"Saved permanent OAuth token to {self.token_file}")
            else:
                raise PermissionError("YouTube authentication required, but browser login is disabled.")

        self.service = build("youtube", "v3", credentials=creds)
        return self.service

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list,
        privacy_status: str = config.YOUTUBE_DEFAULT_PRIVACY,
        category_id: str = "1"  # 1 = Film & Animation
    ) -> Dict[str, Any]:
        """
        Uploads a video to YouTube using resumable chunked upload.
        """
        from googleapiclient.http import MediaFileUpload
        from googleapiclient.errors import HttpError

        if not self.service:
            # On a server there's no browser: require an existing token.json
            self.authenticate(allow_browser=not config.HEADLESS)

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
                "defaultLanguage": "en",
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            }
        }

        logger.info(f"Starting YouTube upload: '{title}' (Privacy: {privacy_status})...")
        media = MediaFileUpload(
            str(video_path),
            chunksize=1024 * 1024 * 5,  # 5MB chunks
            resumable=True,
            mimetype="video/mp4"
        )

        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logger.info(f"Upload progress: {progress}%")

        video_id = response.get("id")
        video_url = f"https://youtu.be/{video_id}"
        logger.info(f"✅ Video successfully uploaded! ID: {video_id} -> {video_url}")

        return {
            "id": video_id,
            "url": video_url,
            "title": title,
            "privacy": privacy_status
        }


def mock_upload_dry_run(video_path: Path, title: str, tags: list) -> Dict[str, Any]:
    """Dry run upload for local testing without YouTube API credentials."""
    logger.info(f"[DRY-RUN] Simulating YouTube upload for: '{title}'")
    logger.info(f"[DRY-RUN] File: {video_path} ({video_path.stat().st_size / (1024*1024):.2f} MB)")
    logger.info(f"[DRY-RUN] Tags ({len(tags)}): {', '.join(tags)}")
    return {
        "id": "MOCK_VIDEO_ID_12345",
        "url": "https://youtu.be/MOCK_VIDEO_ID_12345",
        "title": title,
        "privacy": "dry_run"
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uploader = YouTubeUploader()
    print("YouTube Uploader initialized.")
