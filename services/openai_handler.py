import re
import openai
from fastapi import Response
import pandas as pd
import os
import logging
from typing import List



def initOpenAI():
    openai.api_key = os.environ['OPENAI_API_KEY']
    openai.api_type = os.environ['OPENAI_API_TYPE']
    openai.api_base = os.environ['OPENAI_API_BASE']
    openai.api_version = os.environ['OPENAI_API_VERSION']

def normalize_text(s):
    s = re.sub(r'\s+',  ' ', s).strip()
    s = re.sub(r". ,","",s)
    # remove all instances of multiple spaces
    s = s.replace("..",".")
    s = s.replace(". .",".")
    s = s.replace("\n", "")
    s = s.strip()
    
    return s

def get_context(data:dict, content_fields:List[str], key_field:str) -> str:

        #retrieve results and filter based on threshold
        results = pd.DataFrame.from_dict(data['value'])
        highest_score = results["@search.rerankerScore"].max()
        threshold = highest_score * float(os.environ['SEARCHSERVICE_SCORE_THRESHOLD'])
        results = results[results["@search.rerankerScore"] >= threshold]

        #filter based on max number of results
        max_no_results = int(os.environ['SEARCHSERVICE_MAX_NO_RESULTS'])
        if len(results) > max_no_results:
            results = results[:max_no_results]

        #clean content field from the results
        for content_field in content_fields:
            results[content_field] = results[content_field].apply(normalize_text)

        #concat all content_fields into one string
        results["openai_data"] = results[key_field] + ": "
        for content_field in content_fields:
            results["openai_data"] = results["openai_data"] + results[content_field] + " "

        return results[content_field].str.cat(sep="\n")

def get_openai_answer(question:str, context:str, model:str)->str:
    initOpenAI()
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
            max_tokens=300,
            temperature=0.2,
            messages = prompt)["choices"][0]["message"]["content"]
    except Exception as e:
        logging.info(e)
    
    return answer


def generate_vector(content:dict, content_field:List[str]):
    initOpenAI()

    df = pd.DataFrame.from_dict(content)
    for field in content_field:
        df[field + "_normalized"] = df[field].apply(normalize_text)
        df[field + "_vector"] = df[field + "_normalized"].apply(get_embedding)
        df = df.drop(columns=[field + "_normalized"])
    return df

def get_embedding(content:str, model:str = os.environ("OPENAI_API_EMBEDDING_MODEL"))-> List[float]:
    initOpenAI()
    vector = openai.Embedding.create(input=content, engine=model)['data'][0]['embedding']
    return vector
