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

def test_render_reuses_saved_browser_data(tmp_path):
    import json
    report=tmp_path/"report.json"
    report.write_text(json.dumps({
        "target":"https://example.org",
        "summary":{"error":0,"warning":0,"info":0},
        "pages":[],"findings":[]
    }),encoding="utf-8")
    result=run("render",str(report))
    assert result.returncode==0,result.stderr
    assert (tmp_path/"report.html").is_file()
    assert (tmp_path/"report.md").is_file()
    html=(tmp_path/"report.html").read_text(encoding="utf-8")
    assert "Nothing broke in these checks." in html
    assert "example.org | AksharaCheck report" in html
