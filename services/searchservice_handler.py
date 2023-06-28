import os
from typing import List
import requests
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential  
from azure.search.documents.models import Vector
from fastapi import Request
from services import openai_handler as oai




def validate_vector_fields(content_fields:List[str], search_service_key:str, search_index:str):
    response = requests.get(f"https://{os.environ['SEARCHSERVICE_NAME']}.search.windows.net/indexes/{search_index}?api-version=2023-07-01-preview", headers={"api-key": search_service_key})
    if response.status_code != 200:
        raise Exception(f"Error getting index {search_index}: {response.status_code} - {response.text}")
    
    fields = [field['name'] for field in response.json()['fields']]
    for field in content_fields:
        if f"{field}_vector" not in fields:
            raise Exception(f"Field {field}_vector is not in the index")
        
async def vector_search(req: Request, search_service_key:str, search_index:str, select_fields:List[str], search_fields:List[str]):
    body = await req.json()
    content_fields = body.get('contentField').split(",")
    if len(content_fields) == 1:
        raise Exception("contentField needs to be specified and can only be 1")
    content_fields = [ body.get('contentField') + "_vector" ]

    if body.get('top',"-1") != -1:
        top = int(body.get('top'))
    else:
        top = None

    if body.get('filter',"NA") != "NA":
        filter = body.get('filter')
    else:  
        filter = None	

    query = body.get('search')

    search_client = SearchClient(endpoint=f"https://{os.environ['SEARCHSERVICE_NAME']}.search.windows.net", 
                                 index_name=search_index, 
                                 credential=AzureKeyCredential(search_service_key))
    
    result = search_client.search(
            search_text =  "",
            include_total_count = body.get('include_total_count', None),
            facets = body.get('facets', None).split(","),
            filter = body.get('filter', None),
            highlight_fields = body.get('highlight_fields', None)
            highlight_post_tag = body.get('highlight_post_tag', None),
            highlight_pre_tag = body.get('highlight_pre_tag', None),
            minimum_coverage = body.get('minimum_coverage', None),
            order_by = Optional[List[str]] = None,
            query_type = Optional[Union[str, QueryType]] = None,
            scoring_parameters = Optional[List[str]] = None,
            scoring_profile = Optional[str] = None,
            search_fields = body.get('searchFields', None).split(","),
            search_mode = Optional[Union[str, SearchMode]] = None,
            query_language = Optional[Union[str, QueryLanguage]] = None,
            query_speller = Optional[Union[str, QuerySpellerType]] = None,
            query_answer = Optional[Union[str, QueryAnswerType]] = None,
            query_answer_count = Optional[int] = None,
            query_caption = Optional[Union[str, QueryCaptionType]] = None,
            query_caption_highlight = Optional[bool] = None,
            semantic_fields = Optional[List[str]] = None,
            semantic_configuration_name = Optional[str] = None,
            select = body.get('select', None).split(",")
            skip = Optional[int] = None,
            top = Optional[int] = None,
            scoring_statistics = Optional[Union[str, ScoringStatistics]] = None,
            session_id = Optional[str] = None,
            vector = Vector(value = oai.get_embedding(query), fields = content_fields, k=top)
            semantic_error_handling = Optional[Union[str, SemanticErrorHandling]] = None,
            semantic_max_wait_in_milliseconds = body.get('semanticMaxWaitInMilliseconds', None)

        search_fields = 
        include_total_count = body.get('includeTotalCount', None),
        facets = body.get('facets', None),
        order_by = body.get('orderBy', None),
        skip = body.get('skip', None),
        top = body.get('top', None),
        highlight_fields = body.get('highlightFields', None).split(","),
        highlight_post_tag = body.get('highlightPostTag', None),
        highlight_pre_tag = body.get('highlightPreTag', None),
        minimum_coverage = body.get('minimumCoverage', None),
        minimum_similarity = body.get('minimumSimilarity', None),
        scoring_parameters = body.get('scoringParameters', None),
        scoring_profile = body.get('scoringProfile', None),
        scoring_statistics = body.get('scoringStatistics', None),
        search_mode = body.get('searchMode', None),
        query_type = body.get('queryType', None),
        enable_fuzzy_query = body.get('enableFuzzyQuery', None),
        enable_stemming = body.get('enableStemming', None),
        enable_synonym_search = body.get('enableSynonymSearch', None),
        include_all_properties = body.get('includeAllProperties', None),
    
    )

