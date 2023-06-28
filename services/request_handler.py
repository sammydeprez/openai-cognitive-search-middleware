import azure.functions as func
from fastapi import Request, Response
import requests
import os
import json


#this function is used to send the request again
async def forward_req(req:Request, remove_middleware_fields:bool = False) -> Response:
    url = f"https://{os.environ['SEARCHSERVICE_NAME']}.search.windows.net" + req.url.path + '?' + req.url.query
    headers = clean_headers(req.headers, keysToKeep = ["api-key", "Content-Type"])
    ##TODO - why is this failing....
    try:
        body = await req.json()
    except Exception as e:
        body = None
    if remove_middleware_fields:
        body.pop('contentField', None)
        body.pop('keyField', None)
    response = requests.request(method=req.method, url=url, headers=headers, json=body)
    resp_headers = clean_headers(response.headers, keysToRemove=["Content-Length", "Content-Encoding"])
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=resp_headers)

#this function is used to clean the headers
def clean_headers(headers: dict, keysToRemove:list = [], keysToKeep:list = []) -> dict:
    new_headers = {}
    for key, value in headers.items():
        if len(keysToRemove) > 0:
            if key not in keysToRemove:
                new_headers[key] = value
        if len(keysToKeep) > 0:
            if key in keysToKeep:
                new_headers[key] = value
    return new_headers