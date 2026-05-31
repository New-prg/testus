import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Backend management commands")
    parser.add_argument("command", choices=["seed-demo", "import-pilot-current", "import-dataset"])
    parser.add_argument("--path")
    parser.add_argument("--replace-shared-fleet", action="store_true")
    parser.add_argument("--anonymize", action="store_true")
    args = parser.parse_args()

    if args.command == "seed-demo":
        from app.db.seed import seed_demo_data
        from app.db.session import SessionLocal

        with SessionLocal() as db:
            result = seed_demo_data(db)
            print(result)
    elif args.command == "import-pilot-current":
        from app.db.session import SessionLocal
        from app.services.pilot_gps.client import HttpPilotGpsClient
        from app.services.pilot_gps.sync_service import PilotSyncService

        with SessionLocal() as db:
            result = PilotSyncService(HttpPilotGpsClient()).import_live_current_snapshot(
                db,
                replace_shared_fleet=args.replace_shared_fleet,
                anonymize=args.anonymize,
            )
            print(result)
    elif args.command == "import-dataset":
        if not args.path:
            parser.error("import-dataset requires --path <path>")
        from app.db.session import SessionLocal
        from app.services.telemetry.dataset_importer import DatasetImporter

        with SessionLocal() as db:
            result = DatasetImporter().import_path(db, args.path)
            print(result)


if __name__ == "__main__":
    main()
