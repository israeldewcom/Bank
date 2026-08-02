from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from chronos_v5.config import Config
import asyncio
import tempfile  # <-- ADDED
import os

# Sync engine (for legacy sync code)
def create_sync_engine(db_url):
    return create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=Config.DB_POOL_SIZE,
        max_overflow=Config.DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=Config.DB_POOL_RECYCLE,
        echo=False,
        connect_args={'connect_timeout': 10, 'application_name': 'chronos'} if 'postgresql' in db_url else {}
    )

sync_engine = create_sync_engine(Config.DATABASE_URL)
SyncSessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=sync_engine))

# Async engine
async_engine = None
AsyncSessionLocal = None
async_database = None

if Config.ASYNC_DB:
    try:
        import asyncpg
        async_engine = create_async_engine(
            Config.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
            pool_size=Config.DB_POOL_SIZE,
            max_overflow=Config.DB_MAX_OVERFLOW,
            pool_pre_ping=True,
            pool_recycle=Config.DB_POOL_RECYCLE,
            echo=False,
        )
        AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)
        from databases import Database
        async_database = Database(Config.DATABASE_URL, min_size=5, max_size=20)
    except ImportError as e:
        from chronos_v5.logger_setup import logger
        logger.warning(f"Async DB not available: {e}. Falling back to sync.")

# Replica
read_engine = None
if Config.DB_READ_REPLICA_URL:
    read_engine = create_sync_engine(Config.DB_READ_REPLICA_URL)

def run_migrations():
    import os, time
    from chronos_v5.logger_setup import logger
    # BUG FIX: this previously used a lock *file* on local disk
    # (tempfile.gettempdir()/chronos_migration.lock). That only prevents
    # two processes on the SAME machine from migrating concurrently. Under
    # the project's own Kubernetes/Helm deployment (replicaCount: 3 in
    # values-bank.yaml / values-advanced.yaml), every pod has its own
    # filesystem, so this lock gave zero protection against concurrent
    # migrations across pods — exactly the topology it needed to guard
    # against. Reworked to use a Redis SETNX-based distributed lock (the
    # same pattern advanced_main.py already uses correctly for its
    # "advanced services" singleton lock), which is shared across every
    # process and every pod since they all point at the same Redis.
    try:
        import redis
        r = redis.from_url(Config.REDIS_URL, socket_timeout=5, socket_connect_timeout=5)
        lock_key = "chronos:migration:lock"
        lock_ttl = 120  # seconds; generous upper bound for a migration run
        acquired = r.set(lock_key, os.getpid(), nx=True, ex=lock_ttl)
        if not acquired:
            logger.info("Migration lock held by another instance, waiting...")
            for _ in range(30):
                time.sleep(1)
                if not r.exists(lock_key):
                    break
            return
        try:
            _run_migrations_locked()
        finally:
            try:
                r.delete(lock_key)
            except Exception as e:
                logger.warning(f"Failed to release Redis migration lock (will expire via TTL): {e}")
    except Exception as e:
        logger.warning(f"Redis migration lock unavailable ({e}); falling back to local lock file. "
                        f"This is NOT safe across multiple pods/hosts — ensure only one instance "
                        f"runs migrations in that case (e.g. a dedicated pre-install Job).")
        _run_migrations_with_local_lock()

def _run_migrations_with_local_lock():
    """Fallback used only if Redis is unreachable. Single-host only."""
    import os, time
    from chronos_v5.logger_setup import logger
    lock_dir = tempfile.gettempdir()
    lock_file = os.path.join(lock_dir, "chronos_migration.lock")
    if os.path.exists(lock_file):
        logger.info("Migration lock file exists, waiting...")
        for _ in range(30):
            time.sleep(1)
            if not os.path.exists(lock_file):
                break
        return
    try:
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
        _run_migrations_locked()
    finally:
        if os.path.exists(lock_file):
            os.remove(lock_file)

def _run_migrations_locked():
    from chronos_v5.logger_setup import logger
    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command
        from alembic.script import ScriptDirectory
        alembic_cfg = AlembicConfig()
        alembic_cfg.set_main_option("script_location", "alembic")
        alembic_cfg.set_main_option("sqlalchemy.url", Config.DATABASE_URL)
        script = ScriptDirectory.from_config(alembic_cfg)
        if not script.get_current_head():
            command.stamp(alembic_cfg, "head")
        else:
            command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations applied")
    except Exception as e:
        logger.warning(f"Alembic migration skipped: {e}. Creating tables directly.")
        from chronos_v5.models import Base
        Base.metadata.create_all(sync_engine)
