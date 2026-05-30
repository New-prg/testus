from datetime import date, datetime, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Report, VehicleMetricWindow, VehicleRatingWindow


class ReportService:
    def fleet_summary(self, db: Session, period_start: date, period_end: date) -> dict[str, Any]:
        start = datetime.combine(period_start, time.min)
        end = datetime.combine(period_end, time.max)
        metrics = db.scalars(select(VehicleMetricWindow).where(VehicleMetricWindow.period_start >= start, VehicleMetricWindow.period_end <= end)).all()
        ratings = db.scalars(select(VehicleRatingWindow).where(VehicleRatingWindow.period_start >= start, VehicleRatingWindow.period_end <= end)).all()
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "metric_windows": len(metrics),
            "rating_windows": len(ratings),
            "distance_km": round(sum(metric.distance_km for metric in metrics), 3),
            "fuel_consumed_liters": round(sum(metric.fuel_consumed_liters or 0.0 for metric in metrics), 3),
            "average_rating": round(sum(rating.final_rating for rating in ratings) / len(ratings), 3) if ratings else 0.0,
        }

    def vehicle_summary(self, db: Session, vehicle_id: str, period_start: date, period_end: date) -> dict[str, Any]:
        start = datetime.combine(period_start, time.min)
        end = datetime.combine(period_end, time.max)
        metrics = db.scalars(select(VehicleMetricWindow).where(VehicleMetricWindow.vehicle_id == vehicle_id, VehicleMetricWindow.period_start >= start, VehicleMetricWindow.period_end <= end)).all()
        ratings = db.scalars(select(VehicleRatingWindow).where(VehicleRatingWindow.vehicle_id == vehicle_id, VehicleRatingWindow.period_start >= start, VehicleRatingWindow.period_end <= end)).all()
        return {
            "vehicle_id": vehicle_id,
            "distance_km": round(sum(metric.distance_km for metric in metrics), 3),
            "fuel_consumed_liters": round(sum(metric.fuel_consumed_liters or 0.0 for metric in metrics), 3),
            "average_rating": round(sum(rating.final_rating for rating in ratings) / len(ratings), 3) if ratings else 0.0,
            "ratings": [{"period_start": rating.period_start, "final_rating": rating.final_rating} for rating in ratings],
        }

    def fleet_csv(self, db: Session, period_start: date, period_end: date) -> str:
        start = datetime.combine(period_start, time.min)
        end = datetime.combine(period_end, time.max)
        rows = db.scalars(select(VehicleMetricWindow).where(VehicleMetricWindow.period_start >= start, VehicleMetricWindow.period_end <= end).order_by(VehicleMetricWindow.vehicle_id, VehicleMetricWindow.period_start)).all()
        lines = ["vehicle_id,period_start,period_end,distance_km,fuel_consumed_liters,fuel_per_100km,idle_ratio"]
        for row in rows:
            lines.append(f"{row.vehicle_id},{row.period_start},{row.period_end},{row.distance_km},{row.fuel_consumed_liters or ''},{row.fuel_per_100km or ''},{row.idle_ratio or ''}")
        return "\n".join(lines) + "\n"

    def create_report(self, db: Session, user_id: str | None, period_start: date, period_end: date, name: str | None = None) -> Report:
        payload = self.fleet_summary(db, period_start, period_end)
        report = Report(created_by_id=user_id, name=name or f"Fleet summary {period_start}..{period_end}", report_type="fleet_summary", period_start=period_start, period_end=period_end, payload=payload)
        db.add(report)
        db.flush()
        return report
