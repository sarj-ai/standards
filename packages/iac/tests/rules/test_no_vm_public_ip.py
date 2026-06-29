from pathlib import Path

from sarj_iac_lint.rules.no_vm_public_ip import NoVmPublicIp


def _check(source: str, name: str = "main.tf") -> list:
    return NoVmPublicIp().check(Path(name), source)


def test_flags_empty_access_config():
    src = """
network_interface {
  network = var.network
  access_config {}
}
"""
    diags = _check(src)
    assert len(diags) == 1
    assert "external IP" in diags[0].message


def test_flags_access_config_block():
    src = """
network_interface {
  access_config {
    nat_ip = google_compute_address.x.address
  }
}
"""
    assert len(_check(src)) == 1


def test_allows_no_access_config():
    src = "network_interface {\n  network = var.network\n}\n"
    assert _check(src) == []


def test_ignores_commented_access_config():
    src = "network_interface {\n  # access_config {}\n}\n"
    assert _check(src) == []


def test_ignores_non_tf_file():
    assert _check("access_config {}\n", name="notes.txt") == []
