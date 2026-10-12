from typer.testing import CliRunner

from issuepilot.cli import app


def test_version_command() -> None:
    # Single-command Typer app: invoked without a subcommand name.
    # M2 adds `analyze`, which turns this into ["version"].
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 0
    assert result.stdout.strip() != ""
