from pydantic import BaseModel, field_validator
import numpy as np


class SystemRequest(BaseModel):
    title: str
    istate: str
    effect: str
    causes: str


class SystemResponse(SystemRequest):
    id: int
    tensor: str

    # @field_validator('tensor', mode='before')
    # def convert_tensor_to_string(cls, v):
    #     if isinstance(v, np.matrix):
    #         return np.array_str(v)
    #     return v
