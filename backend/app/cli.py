import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Backend management commands")
    parser.add_argument("command", choices=["seed-demo", "seed-demo-admin", "seed-demo-data", "import-pilot-current", "import-dataset", "sync-worker", "sync-once"])
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
    elif args.command == "seed-demo-admin":
        from app.db.seed import ensure_demo_admin
        from app.db.session import SessionLocal

        with SessionLocal() as db:
            result = ensure_demo_admin(db)
            db.commit()
            print(result)
    elif args.command == "seed-demo-data":
        from app.db.seed import seed_demo_data
        from app.db.session import SessionLocal

        with SessionLocal() as db:
            result = seed_demo_data(db)
            print(result)
    elif args.command == "import-pilot-current":
        from sqlalchemy import select

        from app.db.models import User
        from app.db.session import SessionLocal
        from app.db.seed import ensure_demo_admin
        from app.services.pilot_gps.client import HttpPilotGpsClient
        from app.services.pilot_gps.sync_service import PilotSyncService

        with SessionLocal() as db:
            ensure_demo_admin(db)
            admin = db.scalar(select(User).where(User.login == "admin@example.com"))
            if admin is None:
                parser.error("Demo admin user is not available")
            result = PilotSyncService(HttpPilotGpsClient()).import_live_current_snapshot(
                db,
                admin,
                replace_shared_fleet=args.replace_shared_fleet,
                anonymize=args.anonymize,
            )
            print(result)
    elif args.command == "import-dataset":
        if not args.path:
            parser.error("import-dataset requires --path <path>")
        from sqlalchemy import select

        from app.db.models import User
        from app.db.session import SessionLocal
        from app.db.seed import ensure_demo_admin
        from app.services.telemetry.dataset_importer import DatasetImporter

        with SessionLocal() as db:
            ensure_demo_admin(db)
            admin = db.scalar(select(User).where(User.login == "admin@example.com"))
            if admin is None:
                parser.error("Demo admin user is not available")
            result = DatasetImporter().import_path(db, args.path, admin)
            print(result)
    elif args.command in {"sync-worker", "sync-once"}:
        import time

        from app.db.session import SessionLocal
        from app.services.pilot_gps.sync_service import PilotSyncService

        if args.command == "sync-once":
            with SessionLocal() as db:
                print(PilotSyncService().run_due_account_syncs(db))
            return

        while True:
            with SessionLocal() as db:
                results = PilotSyncService().run_due_account_syncs(db)
                if results:
                    print(results)
            time.sleep(60)


if __name__ == "__main__":
    main()
