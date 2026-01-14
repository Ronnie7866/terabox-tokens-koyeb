from fastapi import FastAPI, Query, Request
from fastapi.responses import Response, StreamingResponse
import httpx
from urllib.parse import unquote, quote
import logging

app = FastAPI()
logging.basicConfig(level=logging.ERROR)

@app.get("/")
async def handle_request(request: Request, url: str = Query(None)):
    if not url:
        return Response('Missing url parameter', status_code=400)
    
    try:
        # Decode URL
        decoded_url = unquote(url)
    except Exception as e:
        logging.error(f'URL parsing error: {e}')
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.terabox.app/',
            'Origin': 'https://www.terabox.app',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        
        # Add Range header if present
        range_header = request.headers.get('Range')
        if range_header:
            headers['Range'] = range_header
        
        # Fetch the video
        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            response = await client.get(url, headers=headers)
        
        if not response.is_success and response.status_code != 206:
            raise Exception(f'HTTP error! status: {response.status_code}')
        
        content_type = response.headers.get('content-type', '')
        
        # Handle m3u8 files (HLS manifests)
        if 'application/vnd.apple.mpegurl' in content_type or url.endswith('.m3u8'):
            text = response.text
            
            if not text.startswith('#EXTM3U'):
                return Response(
                    text,
                    status_code=500,
                    headers={
                        'Content-Type': 'text/plain',
                        'Access-Control-Allow-Origin': '*'
                    }
                )
            
            # Replace first TS segment URL
            first_segment_replaced = False
            modified_lines = []
            
            for line in text.split('\n'):
                if not first_segment_replaced and line.strip().endswith('.ts') and line.strip().startswith('http'):
                    host_url = f"{request.url.scheme}://{request.url.netloc}"
                    modified_lines.append(f"{host_url}/?url={quote(line.strip())}")
                    first_segment_replaced = True
                else:
                    modified_lines.append(line)
            
            modified_text = '\n'.join(modified_lines)
            
            return Response(
                modified_text,
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
                    'Access-Control-Allow-Headers': 'Range',
                    'Content-Type': 'application/vnd.apple.mpegurl',
                    'Cache-Control': 'no-cache'
                }
            )
        
        # For other content types (e.g., TS segments)
        new_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
            'Access-Control-Allow-Headers': 'Range',
            'Access-Control-Expose-Headers': 'Content-Length, Content-Range',
        }
        
        headers_to_keep = ['content-type', 'content-length', 'content-range', 'content-encoding']
        for header in headers_to_keep:
            value = response.headers.get(header)
            if value:
                new_headers[header] = value
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=new_headers
        )
        
    except Exception as error:
        return Response(
            f'Error fetching content: {str(error)}',
            status_code=500,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Content-Type': 'text/plain'
            }
        )
