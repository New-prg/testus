from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models import MLResult
from app.db.session import get_db
from app.services.ml.anomaly_service import AnomalyService
from app.services.ml.clustering_service import ClusteringService
from app.services.ml.dataset_builder import DatasetBuilder


router = APIRouter(prefix="/ml", tags=["ml"], dependencies=[Depends(deps.get_fleet_access_user)])


@router.post("/recalculate")
def recalculate(db: Annotated[Session, Depends(get_db)], limit: int = 500) -> dict[str, Any]:
    rows = DatasetBuilder().build(db, limit)
    anomalies = AnomalyService().detect(rows)
    clusters = ClusteringService().cluster(rows)
    db.execute(delete(MLResult).where(MLResult.result_type.in_(["anomaly", "cluster"])))
    for result in anomalies.get("results", []):
        if result.get("label") != "anomaly":
            continue
        db.add(MLResult(result_type="anomaly", vehicle_id=result.get("vehicle_id"), payload=result))
    for result in clusters.get("results", []):
        db.add(MLResult(result_type="cluster", vehicle_id=result.get("vehicle_id"), payload=result))
    db.commit()
    return {"anomalies": anomalies, "clusters": clusters}


@router.get("/anomalies")
def anomalies(db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    results = db.query(MLResult).filter(MLResult.result_type == "anomaly").order_by(MLResult.created_at.desc()).all()
    return {"results": [result.payload for result in results]}


@router.get("/clusters")
def clusters(db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    results = db.query(MLResult).filter(MLResult.result_type == "cluster").order_by(MLResult.created_at.desc()).all()
    return {"results": [result.payload for result in results]}
