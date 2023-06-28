import azure.functions as func
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from services import request_handler as rh
from services import openai_handler as oai
from services import searchservice_handler as sh
import pandas as pd
import os
import json

 
app = FastAPI()

SEARCHSERVICE_FIELD_CONTENT = os.environ["SEARCHSERVICE_FIELD_CONTENT"]
SEARCHSERVICE_FIELD_KEY = os.environ["SEARCHSERVICE_FIELD_KEY"]
OPENAI_API_DEFAULT_MODEL = os.environ["OPENAI_API_DEFAULT_MODEL"]

@app.post("/indexes/{index}/docs/search")
async def search_docs(req: Request) -> Response:
    body = await req.json()

    #if the request is not from openai, forward it to the search service
    if body.get('answers', "openai") != "openai":
        return await rh.forward_req(req)
    
    #if the request is from openai, forward it to the search service and generate an answer
    #replace answers field in body with semantic
    body['answers'] = "semantic"
    req.body = json.dumps(body)

    #if querytype is not vector, forward the request to the search service
    response = await rh.forward_req(req)
    if response.status_code != 200:
        return response
    
    #if querytype is vector, alter the request



    content_fields = body.get('contentField', SEARCHSERVICE_FIELD_CONTENT).split(",")
    key_field = body.get('keyField', SEARCHSERVICE_FIELD_KEY)
    data = json.loads(response.body)

    question = body.get('search', '')

    answer = oai.get_openai_answer(question, oai.get_context(data, content_fields, key_field), OPENAI_API_DEFAULT_MODEL)

    semantic_answer_replacement = { 
            "@search.answers": [
                {
                    "key": "openai",
                    "text": answer,
                    "highlights": answer,
                    "score": 0,
                }
            ]
        }
    
    data.update(semantic_answer_replacement)
    headers = rh.clean_headers(response.headers, keysToRemove=["Content-Length", "Content-Encoding"])
    #TODO: add headers to response
    return Response(content=json.dumps(data), status_code=response.status_code)

@app.post("/indexes/{index}/docs/index")
async def index_docs(req: Request, index: str):
    try:
        sh.validate_vector_fields(SEARCHSERVICE_FIELD_CONTENT.split(","), search_index=index, search_service_key=req.headers["api-key"])
    except Exception as e:
        return Response(content=str(e), status_code=400)
    
    body = await req.json()
    documents = body.get('value', [])
    content_fields = body.get('contentField', SEARCHSERVICE_FIELD_CONTENT).split(",")
    body['value'] = oai.generate_vector(documents, content_fields).to_dict(orient='records')
    req._body = json.dumps(body)
    return await rh.forward_req(req)

@app.api_route("/{path_name:path}")
async def catch_all(request: Request) -> Response:
    return await rh.forward_req(request)

async def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    """Each request is redirected to the ASGI handler."""
    return await func.AsgiMiddleware(app).handle_async(req, context)