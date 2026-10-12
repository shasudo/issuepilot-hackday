import typer

app = typer.Typer(
    name="issuepilot",
    help="Universal GitHub contribution assistant.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the installed IssuePilot version."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as dist_version

    try:
        print(dist_version("issuepilot-hackday"))
    except PackageNotFoundError:
        print("0.0.0-dev")


if __name__ == "__main__":
    app()
