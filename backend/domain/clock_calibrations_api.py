from fastapi import APIRouter, Depends

from core.auth import actor, allow
from core.audit import record
from core.db import transaction
from core.records import scan
from domain import clock_calibrations_service as service
from domain.clock_calibrations_model import clock_calibrations
from domain.clock_calibrations_schemas import SubmitCalibration

router = APIRouter()


@router.get('/clock_calibrations')
def list_clock_calibrations(user=Depends(actor)):
    with transaction() as conn:
        return scan(conn, clock_calibrations)


@router.post('/clock_calibrations/submit-calibration')
def submit_calibration(data: SubmitCalibration, user=Depends(actor)):
    allow(user, ('operator', 'reviewer'))
    with transaction() as conn:
        output = service.submit_calibration(conn, user, data)
        record(conn, user, 'clock_calibrations.submit_calibration')
        return output
