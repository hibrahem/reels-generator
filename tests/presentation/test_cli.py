"""Feature tests for the CLI: bare `reels` launches Reels Studio; the pipeline
is not runnable from the command line."""

from typer.testing import CliRunner

from reels.presentation import cli

runner = CliRunner()


def test_bare_reels_launches_the_studio_server(monkeypatch, tmp_path):
    captured = {}

    def fake_uvicorn_run(asgi_app, host, port):
        captured["asgi_app"] = asgi_app
        captured["host"] = host
        captured["port"] = port

    def fake_create_app(config_path):
        captured["config"] = config_path
        return "asgi-app"

    monkeypatch.setattr("uvicorn.run", fake_uvicorn_run)
    monkeypatch.setattr("reels.presentation.api.app.create_app", fake_create_app)

    config = tmp_path / "config.yaml"
    config.write_text("paths: {}\n")

    result = runner.invoke(cli.app, ["--config", str(config), "--port", "9000"])

    assert result.exit_code == 0
    assert captured["asgi_app"] == "asgi-app"
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9000
    assert captured["config"] == config.resolve()


def test_pipeline_cannot_be_run_from_the_command_line():
    result = runner.invoke(cli.app, ["run"])
    assert result.exit_code != 0


def test_web_subcommand_is_gone_because_it_is_the_default():
    result = runner.invoke(cli.app, ["web"])
    assert result.exit_code != 0


def test_doctor_command_still_exists():
    result = runner.invoke(cli.app, ["doctor", "--help"])
    assert result.exit_code == 0
