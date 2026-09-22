from typing import Annotated, Literal
from pydantic import Field
from .generation_schema import Strict

class FileRequest(Strict):
    kind:Literal['file']
    variant:str
    path:str
    question:str=Field(min_length=5,max_length=500)

class CheckRequest(Strict):
    kind:Literal['check']
    check_id:str
    question:str=Field(min_length=5,max_length=500)

class ScenarioRequest(Strict):
    kind:Literal['scenario']
    variant:str
    case_id:str
    question:str=Field(min_length=5,max_length=500)

EvidenceRequest=Annotated[FileRequest|CheckRequest|ScenarioRequest,Field(discriminator='kind')]

