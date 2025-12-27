import os
import pickle
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']

class GooglePhotosManager:
    def __init__(self):
        self.creds = None
        self.service = None
        # Use system Local AppData for secure storage
        self.app_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'FrameTamer')
        if not os.path.exists(self.app_data_dir):
            os.makedirs(self.app_data_dir)
            
        self.token_path = os.path.join(self.app_data_dir, 'token.pickle')
        # We also check for credentials.json in the app data dir or project root
        self.creds_path = os.path.join(self.app_data_dir, 'credentials.json')
        if not os.path.exists(self.creds_path):
            self.creds_path = 'credentials.json' # Fallback to local file for dev

    def authenticate(self):
        """Authenticates the user and returns the credentials."""
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                self.creds = pickle.load(token)
        
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not os.path.exists(self.creds_path):
                    raise FileNotFoundError("credentials.json not found. Please follow instructions in implementation plan.")
                flow = InstalledAppFlow.from_client_secrets_file(self.creds_path, SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(self.token_path, 'wb') as token:
                pickle.dump(self.creds, token)
        
        return self.creds

    def list_media_items(self, page_token=None):
        """Lists media items from Google Photos."""
        if not self.creds:
            self.authenticate()
            
        url = 'https://photoslibrary.googleapis.com/v1/mediaItems'
        params = {
            'pageSize': 50,
        }
        if page_token:
            params['pageToken'] = page_token
            
        headers = {
            'Authorization': f'Bearer {self.creds.token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_image_data(self, base_url, width=1024, height=1024):
        """Fetches image data from a base URL with specific dimensions."""
        download_url = f"{base_url}=w{width}-h{height}"
        response = requests.get(download_url)
        response.raise_for_status()
        return response.content
