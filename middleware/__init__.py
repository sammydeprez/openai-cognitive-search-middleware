import logging
import azure.functions as func
import re
from urllib.parse import urlparse
import requests
import os
import sys
import json
import pandas as pd
import openai

def main(req: func.HttpRequest) -> func.HttpResponse:
    if is_semantic_search_req(req):
        #get semantic search results
        response = forward_req(req, remove_middleware_fields = True)

        #check if the request was successful
        if response.status_code != 200:
            return response

        #get search results
        content_field = req.get_json().get('contentField', os.environ["SEARCHSERVICE_FIELD_CONTENT"])
        key_field = req.get_json().get('keyField', os.environ["SEARCHSERVICE_FIELD_KEY"])
        results = get_context(response,content_field, key_field)

        #get question from the request body
        question = req.get_json().get('search', '')

        #get gpt answer
        answer = get_openai_answer(question, results, os.environ['OPENAI_API_DEFAULT_MODEL'])

        #update response body with the answer
        response_body = json.loads(response.get_body().decode('utf-8'))
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

        response_body.update(semantic_answer_replacement)

        return func.HttpResponse(
            body=json.dumps(response_body),
            status_code=response.status_code,
            headers=response.headers)

    else:
        return forward_req(req)


#this function is used to check if the request is for document search
def is_semantic_search_req(req: func.HttpRequest) -> bool:

    #check if the request is for document search
    indexes = re.findall('indexes/([a-z0-9_-]*)/docs/search', req.url)
    if len(indexes) == 0 or req.method != 'POST':
        return False
    
    #check if the request is for semantic search
    body = req.get_json()
    if body.get('queryType', '') != 'semantic':
        return False
    
    return True

#this function is used to get the relative path from the request url
def get_request_path(req: func.HttpRequest) -> str:
    path = urlparse(req.url).path + '?' + urlparse(req.url).query
    return path

#this function is used to send the request again
def forward_req(req:func.HttpRequest, remove_middleware_fields:bool = False) -> func.HttpResponse:
    url = f"https://{os.environ['SEARCHSERVICE_NAME']}.search.windows.net" + get_request_path(req)
    headers = clean_headers(req.headers, keysToKeep = ["api-key", "Content-Type"])
    body = req.get_json()
    if remove_middleware_fields:
        body.pop('contentField', None)
        body.pop('keyField', None)
    response = requests.request(method=req.method, url=url, headers=headers, json=body)
    resp_headers = clean_headers(response.headers, keysToRemove=["Content-Length", "Content-Encoding"])
    return func.HttpResponse(
        body=response.text,
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

def normalize_text(s):
    s = re.sub(r'\s+',  ' ', s).strip()
    s = re.sub(r". ,","",s)
    # remove all instances of multiple spaces
    s = s.replace("..",".")
    s = s.replace(". .",".")
    s = s.replace("\n", "")
    s = s.strip()
    
    return s

def get_context(response:func.HttpResponse, content_field:str, key_field:str) -> str:
        response_body = json.loads(response.get_body().decode('utf-8'))

        #retrieve results and filter based on threshold
        results = pd.DataFrame.from_dict(response_body['value'])
        highest_score = results["@search.rerankerScore"].max()
        threshold = highest_score * float(os.environ['SEARCHSERVICE_SCORE_THRESHOLD'])
        results = results[results["@search.rerankerScore"] >= threshold]

        #filter based on max number of results
        max_no_results = int(os.environ['SEARCHSERVICE_MAX_NO_RESULTS'])
        if len(results) > max_no_results:
            results = results[:max_no_results]

        #clean content field from the results
        results[content_field] = results[content_field].apply(normalize_text)

        #concat content field and id field to create a new field
        results[content_field] = results[key_field] + ": " +results[key_field]

        return results[content_field].str.cat(sep="\n")

def get_openai_answer(question:str, context:str, model:str)->str:
    answer = ""

    if context == "":
        return answer
    
    system_message = os.environ["OPENAI_API_SYSTEM_MESSAGE"]
    prompt = [
        {
            "role":"system",
            "content": system_message
        },
        {
            "role":"user",
            "content":f"""### SOURCES:
            {context}"""
        },
        {
            "role":"user",
            "content": f"""### QUESTION:
            {question}"""
        }
    ]
    try:
        answer = openai.ChatCompletion.create(
            engine=model,
            max_tokens=100,
            temperature=0.3,
            messages = prompt)["choices"][0]["message"]["content"]
    except Exception as e:
        logging.info(e)
    
    return answer