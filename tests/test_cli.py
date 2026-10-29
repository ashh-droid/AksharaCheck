"""CLI smoke checks that require no network, API credentials or browser launch."""
import subprocess
import sys
from aksharacheck import __version__


def run(*args):
    return subprocess.run([sys.executable,"-m","aksharacheck",*args],capture_output=True,text=True,check=False)


def test_cli_version():
    output=run("--version")
    assert output.returncode==0
    assert __version__ in output.stdout


def test_cli_help_advertises_scan_and_serve():
    output=run("--help")
    assert output.returncode==0
    assert "scan" in output.stdout
    assert "serve" in output.stdout


def test_cli_supports_machine_readable_output():
    output=run("scan","--help")
    assert output.returncode==0
    assert "--json" in output.stdout


def test_cli_bind_host_defaults_to_local():
    output=run("serve","--help")
    assert output.returncode==0
    assert "--host" in output.stdout
