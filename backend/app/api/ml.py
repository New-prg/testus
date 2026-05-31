from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models import MLModelRun, MLResult
from app.db.session import get_db
from app.services.ml.anomaly_service import AnomalyService
from app.services.ml.clustering_service import ClusteringService
from app.services.ml.dataset_builder import FeatureBuilder
from app.services.ml.forecasting_service import ForecastingService


router = APIRouter(prefix="/ml", tags=["ml"], dependencies=[Depends(deps.get_fleet_access_user)])


@router.post("/recalculate")
def recalculate(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[Any, Depends(deps.get_admin_user)],
    limit: Annotated[int, Query(ge=10, le=1000)] = 500,
) -> dict[str, Any]:
    rows = FeatureBuilder().build(db, limit)
    anomalies = AnomalyService().detect(rows)
    clusters = ClusteringService().cluster(rows)
    forecasts = ForecastingService().forecast(rows)

    db.execute(delete(MLResult).where(MLResult.result_type.in_(["anomaly", "cluster", "forecast"])))
    _persist_runs(db, "anomaly", anomalies, len(rows))
    _persist_runs(db, "cluster", clusters, len(rows))
    _persist_runs(db, "forecast", forecasts, len(rows))
    for result in anomalies.get("results", []):
        if result.get("label") == "anomaly":
            db.add(MLResult(result_type="anomaly", vehicle_id=result.get("vehicle_id"), period_start=None, period_end=None, payload=result))
    for result in clusters.get("results", []):
        db.add(MLResult(result_type="cluster", vehicle_id=result.get("vehicle_id"), payload=result))
    for result in forecasts.get("results", []):
        db.add(MLResult(result_type="forecast", vehicle_id=result.get("vehicle_id"), payload=result))
    db.commit()
    return {"anomalies": anomalies, "clusters": clusters, "forecasts": forecasts}


@router.get("/model-comparison")
def model_comparison(db: Annotated[Session, Depends(get_db)], limit: int = 20) -> dict[str, Any]:
    runs = db.scalars(select(MLModelRun).order_by(MLModelRun.created_at.desc()).limit(min(limit, 100))).all()
    return {"results": [_run_payload(run) for run in runs]}


@router.get("/anomalies")
def anomalies(db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    results = db.query(MLResult).filter(MLResult.result_type == "anomaly").order_by(MLResult.created_at.desc()).all()
    return {"results": [result.payload for result in results]}


@router.get("/clusters")
def clusters(db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    results = db.query(MLResult).filter(MLResult.result_type == "cluster").order_by(MLResult.created_at.desc()).all()
    return {"results": [result.payload for result in results]}


@router.get("/forecasts")
def forecasts(db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    results = db.query(MLResult).filter(MLResult.result_type == "forecast").order_by(MLResult.created_at.desc()).all()
    return {"results": [result.payload for result in results]}


@router.get("/explanations/{vehicle_id}")
def explanations(vehicle_id: str, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    rows = (
        db.query(MLResult)
        .filter(MLResult.vehicle_id == vehicle_id)
        .filter(MLResult.result_type.in_(["anomaly", "cluster", "forecast"]))
        .order_by(MLResult.created_at.desc())
        .all()
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.result_type, []).append(row.payload)
    return {"vehicle_id": vehicle_id, "results": grouped}


def _persist_runs(db: Session, run_type: str, payload: dict[str, Any], row_count: int) -> None:
    model_runs = payload.get("model_runs")
    if isinstance(model_runs, list) and model_runs:
        for run in model_runs:
            if isinstance(run, dict):
                _persist_run(db, run_type, payload, row_count, run)
        return
    _persist_run(db, run_type, payload, row_count, payload)


def _persist_run(db: Session, run_type: str, parent_payload: dict[str, Any], row_count: int, run_payload: dict[str, Any]) -> None:
    status = "success" if parent_payload.get("message") == "ok" else "skipped"
    db.add(
        MLModelRun(
            run_type=run_type,
            model_name=str(run_payload.get("model_name") or parent_payload.get("model_name") or run_type),
            status=status,
            row_count=row_count,
            feature_names=list(parent_payload.get("feature_names") or []),
            metrics=dict(run_payload.get("metrics") or {}),
            parameters={"message": parent_payload.get("message"), "comparison_group": parent_payload.get("model_name")},
        )
    )


def _run_payload(run: MLModelRun) -> dict[str, Any]:
    display_names = {
        "anomaly": "Аномалии",
        "cluster": "Кластеры",
        "forecast": "Прогноз",
    }
    return {
        "id": run.id,
        "run_type": run.run_type,
        "model_name": run.model_name,
        "model": run.model_name,
        "display_name": display_names.get(run.run_type, run.run_type),
        "status": run.status,
        "row_count": run.row_count,
        "feature_names": run.feature_names,
        "metrics": run.metrics,
        "metrics_summary": _metrics_summary(run.metrics),
        "parameters": run.parameters,
        "created_at": run.created_at.isoformat(),
    }


def _metrics_summary(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for key, value in metrics.items():
        if isinstance(value, int | float) or value is None:
            summary.append({"name": key, "value": value})
        elif isinstance(value, dict):
            for nested_key, nested_value in value.items():
                if isinstance(nested_value, int | float) or nested_value is None:
                    summary.append({"name": f"{key}.{nested_key}", "value": nested_value})
    return summary
