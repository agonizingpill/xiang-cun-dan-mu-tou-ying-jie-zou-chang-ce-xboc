from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class BeatPair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    old: float
    new: float


class SubmitCalibration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    metronome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    valid_from: datetime
    valid_to: datetime
    pairs: list[BeatPair]
