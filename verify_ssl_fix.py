import os
import requests
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Suppress only the single warning from urllib3 needed.
warnings.simplefilter('ignore', InsecureRequestWarning)

# Monkeypatch Session.request to force verify=False
original_request = requests.Session.request

def patched_request(self, method, url, *args, **kwargs):
    kwargs['verify'] = False
    return original_request(self, method, url, *args, **kwargs)

requests.Session.request = patched_request

from huggingface_hub import hf_hub_download

print("Attempting to download config with monkeypatch...")
try:
    path = hf_hub_download(repo_id="sentence-transformers/all-MiniLM-L6-v2", filename="config.json")
    print(f"Success! File downloaded to: {path}")
except Exception as e:
    print(f"Failed: {e}")
