from fastapi import status, APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

import numpy as np
from numpy.typing import NDArray

from sqlalchemy.orm import Session
from data.motors import get_sqlite

from api.models.props.structure import StructProps
from api.schemas.structure import StructureResponse
from api.services.analyze.compute import Compute
from api.shared.formatter import Format

from constants.structure import R5A, STRUCTURES
from api.services.structure.base import (
    get_structure_by_title,
)

from icecream import ic


router: APIRouter = APIRouter()


@router.get(
    '/sia-genetic/',
    response_description='Hallar la partición con menor pérdida de información, acercamiento mediante fuerza bruta.',
    status_code=status.HTTP_200_OK,
    response_model_by_alias=False,
)
async def genetic_strategy(
    title: str = STRUCTURES[R5A][StructProps.TITLE],
    istate: str = STRUCTURES[R5A][StructProps.ISTATE],
    effect: str = STRUCTURES[R5A][StructProps.EFFECT],
    causes: str = STRUCTURES[R5A][StructProps.CAUSES],
    dual: bool = False,
    # ! Should be a GLOBAL configuration
    # store_network: bool = False,
    db: Session = Depends(get_sqlite),
):
    ic(title)
    db_struct: StructureResponse = get_structure_by_title(title, db)
    form: Format = Format()
    subtensor: NDArray[np.float64] = form.deserialize_tensor(db_struct.tensor)
    ic(type(subtensor))

    computing: Compute = Compute(db_struct, istate, effect, causes, subtensor, dual)
    results = computing.use_genetic_algorithm(db)
    return JSONResponse(content=jsonable_encoder(results), status_code=status.HTTP_200_OK)


# @router.get(
#     '/sia-pyphi/',
#     response_description='Hallar la partición con menor pérdida de información, acercamiento mediante PyPhi.',
#     status_code=status.HTTP_200_OK,
#     response_model_by_alias=False,
# )
# async def pyphi_strategy(
#     title:  str = SYSTEMS[R10A][SysProps.TITLE],
#     istate: str = SYSTEMS[R10A][SysProps.ISTATE],
#     effect: str = SYSTEMS[R10A][SysProps.EFFECT],
#     causes: str = SYSTEMS[R10A][SysProps.CAUSES],
#     # ! Should be a GLOBAL configuration
#     store_network: bool = False,
#     db=Depends(get_sqlite)
# ):
#     db_system = get_system_by_title(title, db)
#     form: Format = Format()
#     subtensor = form.deserialize_tensor(db_system.tensor)

#     computing: Compute = Compute(db_system, istate, effect, causes, subtensor)
#     results = computing.use_pyphi()
#     return JSONResponse(content=jsonable_encoder(results), status_code=status.HTTP_200_OK)
