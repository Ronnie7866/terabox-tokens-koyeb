from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import aiohttp
import re
from typing import Optional

app = FastAPI(title="TeraBox Token Service")

class TokenRequest(BaseModel):
    url: str
    cookie: Optional[str] = None

class TokenResponse(BaseModel):
    dplogid: str
    thumbnail: str
    jstoken: str

def find_between(data: str, first: str, last: str) -> Optional[str]:
    try:
        start = data.index(first) + len(first)
        end = data.index(last, start)
        return data[start:end]
    except ValueError:
        return None

def get_surl_from_url(url: str) -> Optional[str]:
    from urllib.parse import urlparse, parse_qs
    
    if url.startswith('1'):
        url = url[1:]
    
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    if 'surl' in query_params:
        return query_params['surl'][0]
    
    path_match = re.search(r"/s/([A-Za-z0-9_-]+)", url)
    if path_match:
        surl = path_match.group(1)
        return surl[1:] if surl.startswith('1') else surl
    
    direct_match = re.search(r"([A-Za-z0-9_-]+)", url)
    if direct_match:
        surl = direct_match.group(0)
        return surl[1:] if surl.startswith('1') else surl
    
    return None

@app.post("/extract-tokens", response_model=TokenResponse)
async def extract_tokens(request: TokenRequest):
    surl = get_surl_from_url(request.url)
    if not surl:
        raise HTTPException(status_code=400, detail="Invalid TeraBox URL")
    
    safe_url = f"https://dm.1024tera.com/wap/share/filelist?surl={surl}"
    
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    if request.cookie:
        headers['cookie'] = request.cookie
    
    async with aiohttp.ClientSession() as session:
        async with session.get(safe_url, headers=headers) as response:
            if response.status != 200:
                raise HTTPException(status_code=response.status, detail="Failed to fetch page")
            
            text = await response.text()
            
            if len(text) < 100:
                raise HTTPException(status_code=400, detail="Invalid response from TeraBox")
    
    thumbnail = find_between(text, 'og:image" content="', '"')
    logid = find_between(text, "dp-logid=", "&")
    jstoken = find_between(text, "fn%28%22", "%22%29")
    
    if not all([thumbnail, logid, jstoken]):
        raise HTTPException(status_code=404, detail="Could not extract tokens")
    
    return TokenResponse(dplogid=logid, thumbnail=thumbnail, jstoken=jstoken)

@app.get("/")
async def root():
    return {"status": "TeraBox Token Service", "endpoint": "/extract-tokens"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
