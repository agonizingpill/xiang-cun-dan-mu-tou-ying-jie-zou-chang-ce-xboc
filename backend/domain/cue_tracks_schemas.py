from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, FiniteFloat, StringConstraints

CLOCK_ORIGINAL = '原时钟'
CLOCK_REPLACED = '换钟'
CLOCKS = (CLOCK_ORIGINAL, CLOCK_REPLACED)


class RecordTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    venue: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    timings: list | dict
    shift: FiniteFloat
    clock: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)] = CLOCK_ORIGINAL
    metronome: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]] = None
    measured_at: Optional[datetime] = None


class LockTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]


class ResolveTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
