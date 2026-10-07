"""Decision 022: PostgreSQL logical backup envelope and empty-target restore."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

ROOT = Path(__file__).resolve().parents[1]
BASE_TABLES = {
    "portfolios",
    "investment_accounts",
    "instruments",
    "transactions",
    "alembic_version",
}
HEAD = "0002_market_prices"
MEMBERS = {"database.dump", "manifest.json", "SHA256SUMS"}
ENVIRONMENTS = {"local", "staging", "production"}


class BackupError(Exception):
    """Safe, credential-free operator failure."""


def pg(tool: str, args: list[str], env: dict[str, str] | None = None) -> str:
    try:
        result = subprocess.run([tool, *args], env=env, capture_output=True, check=True, text=True)
    except OSError, subprocess.SubprocessError:
        # PostgreSQL stderr may contain connection details or persisted data.
        raise BackupError(f"{tool} failed; no successful operation is claimed") from None
    return result.stdout


def private(path: Path) -> None:
    """Fail closed if owner-only storage cannot be established."""
    if os.name == "nt":
        env = dict(os.environ, IT_PRIVATE_PATH=str(path.resolve()))
        env.pop("PSModulePath", None)
        sid = pg(
            "pwsh",
            [
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "[Security.Principal.WindowsIdentity]::GetCurrent().User.Value",
            ],
            env,
        ).strip()
        if not re.fullmatch(r"S-[0-9-]+", sid):
            raise BackupError("Cannot establish filesystem owner")
        rights = "(OI)(CI)F" if path.is_dir() else "F"
        pg("icacls", [str(path), "/inheritance:r", "/grant:r", f"*{sid}:{rights}"])
        entries = pg(
            "pwsh",
            [
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "$ErrorActionPreference='Stop'; "
                "(Get-Acl -LiteralPath $env:IT_PRIVATE_PATH).Access | ForEach-Object {"
                "$_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value}",
            ],
            env,
        )
        for identity in set(entries.splitlines()):
            if not re.fullmatch(r"S-[0-9-]+", identity):
                raise BackupError("Cannot verify owner-only filesystem access")
            if identity != sid:
                pg("icacls", [str(path), "/remove", "*" + identity])
        pg("icacls", [str(path), "/remove:d", "*" + sid])
    else:
        path.chmod(0o700 if path.is_dir() else 0o600)


def connection(variable: str) -> tuple[str, dict[str, str]]:
    value = os.environ.get(variable, "")
    try:
        info = {key: str(val) for key, val in conninfo_to_dict(value).items() if val is not None}
    except psycopg.Error:
        raise BackupError(f"Invalid {variable}") from None
    if not value or not info.get("host") or not info.get("dbname"):
        raise BackupError(f"{variable} must explicitly identify host and database")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]*", info["dbname"]):
        raise BackupError("Use a simple explicit database name, never nested libpq conninfo")
    host = info["host"]
    if "," in host or "pooler" in host:
        raise BackupError("Use one direct/unpooled endpoint")
    if host not in {"localhost", "127.0.0.1", "::1"} and info.get("sslmode") not in {
        "require",
        "verify-ca",
        "verify-full",
    }:
        raise BackupError("Remote connections require TLS")
    # Do not inherit ambient PG service/connection overrides into the native tools.
    env = {key: val for key, val in os.environ.items() if not key.startswith("PG")}
    mapping = {
        "host": "PGHOST",
        "port": "PGPORT",
        "dbname": "PGDATABASE",
        "user": "PGUSER",
        "password": "PGPASSWORD",
        "sslmode": "PGSSLMODE",
        "sslrootcert": "PGSSLROOTCERT",
        "sslcert": "PGSSLCERT",
        "sslkey": "PGSSLKEY",
        "channel_binding": "PGCHANNELBINDING",
    }
    if set(info) - set(mapping):
        raise BackupError("Unsupported connection options; use explicit direct connection fields")
    env.update({mapping[key]: val for key, val in info.items()})
    return value, env


def lineage() -> list[str]:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    script = ScriptDirectory.from_config(config)
    if script.get_heads() != [HEAD]:
        raise BackupError("Approved migration head differs from tool contract")
    return [revision.revision for revision in script.walk_revisions()]


def environment_guard(value: str, environment: str, *, recovery: bool = False) -> None:
    """Bind operator environment labels to separately confirmed endpoint identities."""
    host = conninfo_to_dict(value)["host"]
    if environment == "local":
        if host not in {"localhost", "127.0.0.1", "::1"}:
            raise BackupError("Local operations require a loopback PostgreSQL endpoint")
        return
    staging = os.environ.get("STAGING_DATABASE_HOST")
    production = os.environ.get("PRODUCTION_DATABASE_HOST")
    if not staging or not production or staging == production:
        raise BackupError("Distinct verified Staging/Production host bindings are required")
    expected = staging if environment == "staging" else production
    if recovery and environment == "production":
        expected = os.environ.get("PRODUCTION_RECOVERY_HOST")
        if not expected or expected == staging:
            raise BackupError("A non-Staging Production recovery host must be designated")
    if host != expected:
        raise BackupError("Connection does not match the declared environment binding")


def tables(revision: str) -> set[str]:
    if revision not in lineage():
        raise BackupError("Unknown/newer or non-ancestor Alembic revision")
    return BASE_TABLES | ({"market_price_observations"} if revision == HEAD else set())


def manifest_check(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or type(value.get("backup_format_version")) is not int
        or value.get("backup_format_version") != 1
    ):
        raise BackupError("Unsupported backup format or invalid manifest")
    required = {
        "backup_format_version",
        "created_at_utc",
        "source_environment",
        "source_alembic_revision",
        "source_postgresql_version",
        "pg_dump_version",
        "application_git_revision",
        "row_counts",
    }
    if set(value) != required:
        raise BackupError("Invalid manifest fields")
    try:
        created = datetime.fromisoformat(value["created_at_utc"])
        offset = created.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError
        if value["source_environment"] not in ENVIRONMENTS:
            raise ValueError
        if not re.fullmatch(r"[0-9a-f]{40}", value["application_git_revision"]):
            raise ValueError
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", value["source_postgresql_version"]):
            raise ValueError
        if not re.fullmatch(
            r"pg_dump \(PostgreSQL\) [0-9]+(?:\.[0-9]+)*(?: \([A-Za-z0-9.+~ -]+\))?",
            value["pg_dump_version"],
        ):
            raise ValueError
        expected = tables(value["source_alembic_revision"])
        counts = value["row_counts"]
        if not isinstance(counts, dict) or set(counts) != expected:
            raise ValueError
        if any(type(count) is not int or count < 0 for count in counts.values()):
            raise ValueError
    except ValueError, TypeError, KeyError, AttributeError:
        raise BackupError("Invalid manifest metadata") from None
    return value


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_directory(directory: Path) -> dict[str, Any]:
    try:
        manifest = manifest_check(json.loads((directory / "manifest.json").read_text("utf-8")))
        expected = "".join(
            f"{sha(directory / name)}  {name}\n" for name in ("database.dump", "manifest.json")
        )
        if (directory / "SHA256SUMS").read_text("ascii") != expected:
            raise BackupError("Checksum mismatch")
        listing = pg("pg_restore", ["--list", str(directory / "database.dump")])
        # Read every archive payload block, not only the TOC/Alembic data block.
        pg(
            "pg_restore",
            ["--no-owner", "--no-acl", f"--file={os.devnull}", str(directory / "database.dump")],
        )
        archive_tables = set(re.findall(r" TABLE public (\w+) ", listing))
        if archive_tables != tables(manifest["source_alembic_revision"]):
            raise BackupError("Archive application schema does not match revision")
        # Verify the captured Alembic value, not just a potentially incorrect manifest label.
        revision_data = pg(
            "pg_restore",
            [
                "--data-only",
                "--table=alembic_version",
                "--file=-",
                str(directory / "database.dump"),
            ],
        )
        match = re.search(
            r"COPY public.alembic_version .*?FROM stdin;\n(.*?)\n\\\.", revision_data, re.S
        )
        if not match or match[1] != manifest["source_alembic_revision"]:
            raise BackupError("Archive Alembic state differs from manifest")
        return manifest
    except OSError, UnicodeError, json.JSONDecodeError:
        raise BackupError("Unreadable/incomplete artifact") from None


def unpack(artifact: Path, directory: Path) -> dict[str, Any]:
    if artifact.suffix != ".tar":
        raise BackupError("Incomplete or unsupported artifact name")
    try:
        with tarfile.open(artifact, "r:") as archive:
            members = archive.getmembers()
            if len(members) != 3 or {m.name for m in members} != MEMBERS:
                raise BackupError("Artifact must contain exactly the v1 members")
            if any(not m.isfile() for m in members):
                raise BackupError("Artifact links/special files are forbidden")
            archive.extractall(directory, filter="data")
    except tarfile.TarError, OSError:
        raise BackupError("Unreadable backup bundle") from None
    return validate_directory(directory)


def validate(artifact: Path) -> dict[str, Any]:
    if any(part.startswith(".incomplete-") for part in artifact.parts):
        raise BackupError("Incomplete backup cannot be validated")
    with tempfile.TemporaryDirectory(
        prefix=".incomplete-validate-", dir=artifact.resolve().parent
    ) as temporary:
        directory = Path(temporary)
        private(directory)
        return unpack(artifact, directory)


def backup(output: Path, environment: str, *, encrypted_storage: bool = False) -> Path:
    if environment not in ENVIRONMENTS:
        raise BackupError("Invalid source environment")
    if environment == "production" and not encrypted_storage:
        raise BackupError(
            "Production backup requires approved encrypted-at-rest storage acknowledgment"
        )
    value, env = connection("BACKUP_DATABASE_URL")
    environment_guard(value, environment)
    resolved = output.resolve()
    repository = ROOT.parents[1]
    if resolved.is_relative_to(repository) and not any(
        resolved.is_relative_to(repository / name) for name in ("tmp", "temp")
    ):
        raise BackupError("Store backups outside the checkout or in excluded tmp/temp storage")
    if resolved in {Path.home(), ROOT, *ROOT.parents}:
        raise BackupError("Use a dedicated backup output directory, not a broad existing directory")
    if output.exists() and any(
        not child.name.startswith(("investment-tracker-backup-v1_", ".incomplete-"))
        for child in output.iterdir()
    ):
        raise BackupError("Output must be a dedicated backup-only directory")
    output.mkdir(parents=True, exist_ok=True)
    private(output)
    with tempfile.TemporaryDirectory(prefix=".incomplete-", dir=output) as temporary:
        directory = Path(temporary)
        private(directory)
        try:
            with psycopg.connect(value) as source:
                source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                # Prevent Alembic version updates while the exported snapshot is in use.
                # Operators must still exclude concurrent migration/startup (including new DDL).
                source.execute("LOCK TABLE public.alembic_version IN SHARE MODE NOWAIT")
                revision = source.execute(
                    "SELECT version_num FROM public.alembic_version"
                ).fetchall()
                if len(revision) != 1:
                    raise BackupError("Expected one source Alembic revision")
                revision = revision[0][0]
                expected = tables(revision)
                actual = {
                    r[0]
                    for r in source.execute(
                        "SELECT tablename FROM pg_tables WHERE schemaname='public'"
                    )
                }
                if actual != expected:
                    raise BackupError("Source contains unexpected/missing public tables")
                for name in sorted(expected):
                    source.execute(
                        sql.SQL("LOCK TABLE public.{} IN ACCESS SHARE MODE NOWAIT").format(
                            sql.Identifier(name)
                        )
                    )
                snapshot = source.execute("SELECT pg_export_snapshot()").fetchall()[0][0]
                version = source.execute("SHOW server_version").fetchall()[0][0].split()[0]
                counts = {
                    name: source.execute(
                        sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(name))
                    ).fetchall()[0][0]
                    for name in sorted(expected)
                }
                git = pg("git", ["-C", str(ROOT), "rev-parse", "HEAD"]).strip()
                manifest = manifest_check(
                    {
                        "backup_format_version": 1,
                        "created_at_utc": datetime.now(UTC).isoformat(),
                        "source_environment": environment,
                        "source_alembic_revision": revision,
                        "source_postgresql_version": version,
                        "pg_dump_version": pg("pg_dump", ["--version"]).strip(),
                        "application_git_revision": git,
                        "row_counts": counts,
                    }
                )
                pg(
                    "pg_dump",
                    [
                        "--format=custom",
                        "--no-owner",
                        "--no-acl",
                        *[f"--table=public.{name}" for name in sorted(expected)],
                        f"--snapshot={snapshot}",
                        f"--file={directory / 'database.dump'}",
                    ],
                    env,
                )
            (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
            (directory / "SHA256SUMS").write_text(
                "".join(
                    f"{sha(directory / name)}  {name}\n"
                    for name in ("database.dump", "manifest.json")
                ),
                "ascii",
            )
            validate_directory(directory)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            name = f"investment-tracker-backup-v1_{environment}_{stamp}_{revision}_{git[:12]}.tar"
            candidate = directory / "bundle.tar"
            with tarfile.open(candidate, "w") as archive:
                for member in sorted(MEMBERS):
                    info = archive.gettarinfo(str(directory / member), arcname=member)
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mode = 0o600
                    with (directory / member).open("rb") as stream:
                        archive.addfile(info, stream)
            private(candidate)
            verified = directory / "verify"
            verified.mkdir()
            private(verified)
            unpack(candidate, verified)
            destination = output / name
            if destination.exists():
                raise BackupError("Backup destination already exists")
            candidate.rename(destination)
            return destination
        except psycopg.Error:
            raise BackupError("Source snapshot failed; exclude concurrent migrations") from None


def restore(
    artifact: Path,
    environment: str,
    *,
    production_recovery: bool = False,
    writes_stopped: bool = False,
) -> dict[str, Any]:
    if any(part.startswith(".incomplete-") for part in artifact.parts):
        raise BackupError("Incomplete backup cannot be restored")
    with tempfile.TemporaryDirectory(
        prefix=".incomplete-restore-", dir=artifact.resolve().parent
    ) as temporary:
        directory = Path(temporary)
        private(directory)
        manifest = unpack(artifact, directory)
        source = manifest["source_environment"]
        if environment not in ENVIRONMENTS:
            raise BackupError("Invalid target environment")
        if (source == "production") != (environment == "production"):
            raise BackupError("Production/non-production restore crossover forbidden")
        if source == "local" and environment != "local":
            raise BackupError("Local artifact may only restore into Local recovery")
        if environment == "production" and not (production_recovery and writes_stopped):
            raise BackupError(
                "Explicit Production recovery and stopped-writes acknowledgments required"
            )
        value, env = connection("RESTORE_DATABASE_URL")
        environment_guard(value, environment, recovery=True)
        try:
            with psycopg.connect(value) as target:
                # Reject ALL user objects, including objects outside public: this is an empty DB.
                if target.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n "
                    "ON n.oid=c.relnamespace WHERE n.nspname NOT LIKE 'pg_%' "
                    "AND n.nspname <> 'information_schema') "
                    "OR EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n "
                    "ON n.oid=p.pronamespace WHERE n.nspname NOT LIKE 'pg_%' "
                    "AND n.nspname <> 'information_schema')"
                ).fetchall()[0][0]:
                    raise BackupError("Restore target is non-empty; nothing was changed")
                major = int(target.execute("SHOW server_version_num").fetchall()[0][0]) // 10000
                if major < int(manifest["source_postgresql_version"].split(".")[0]):
                    raise BackupError("Target PostgreSQL major is older than source")
            pg(
                "pg_restore",
                [
                    "--no-owner",
                    "--no-acl",
                    "--exit-on-error",
                    "--single-transaction",
                    "--dbname=" + env["PGDATABASE"],
                    str(directory / "database.dump"),
                ],
                env,
            )
            with psycopg.connect(value) as target:
                actual_tables = {
                    row[0]
                    for row in target.execute(
                        "SELECT tablename FROM pg_tables WHERE schemaname='public'"
                    )
                }
                if actual_tables != tables(manifest["source_alembic_revision"]):
                    raise BackupError("Post-restore table verification failed")
                if target.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_constraint c JOIN pg_namespace n "
                    "ON n.oid=c.connamespace WHERE n.nspname='public' AND NOT c.convalidated)"
                ).fetchall()[0][0]:
                    raise BackupError("Post-restore constraint verification failed")
                revision = target.execute(
                    "SELECT version_num FROM public.alembic_version"
                ).fetchall()
                if revision != [(manifest["source_alembic_revision"],)]:
                    raise BackupError("Post-restore revision verification failed")
                for name, count in manifest["row_counts"].items():
                    actual = target.execute(
                        sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(name))
                    ).fetchall()[0][0]
                    if actual != count:
                        raise BackupError("Post-restore row-count verification failed")
            return manifest
        except psycopg.Error:
            raise BackupError("Restore database verification failed") from None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("backup")
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--environment", choices=sorted(ENVIRONMENTS), required=True)
    create.add_argument("--encrypted-storage", action="store_true")
    check = commands.add_parser("validate")
    check.add_argument("artifact", type=Path)
    recover = commands.add_parser("restore")
    recover.add_argument("artifact", type=Path)
    recover.add_argument("--environment", choices=sorted(ENVIRONMENTS), required=True)
    recover.add_argument("--production-recovery", action="store_true")
    recover.add_argument("--writes-stopped", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            result = backup(args.output, args.environment, encrypted_storage=args.encrypted_storage)
            print(f"Artifact-valid backup published: {result.name}")
        elif args.command == "validate":
            validate(args.artifact)
            print("Artifact-valid; recovery readiness requires an isolated restore drill")
        else:
            manifest = restore(
                args.artifact,
                args.environment,
                production_recovery=args.production_recovery,
                writes_stopped=args.writes_stopped,
            )
            print(
                "Captured schema restored and counts verified. "
                "Run post-restore application verification."
            )
            if manifest["source_alembic_revision"] != HEAD:
                print(
                    "Approved operator Alembic upgrade to current head "
                    "is required before application use."
                )
    except BackupError, OSError:
        parser.exit(1, "Backup/restore refused or failed; no recovery readiness claimed.\n")


if __name__ == "__main__":
    main()
