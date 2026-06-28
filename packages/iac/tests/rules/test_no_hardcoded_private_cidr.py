from pathlib import Path

from sarj_iac_lint.rules.no_hardcoded_private_cidr import NoHardcodedPrivateCidr


def _check(source: str, name: str = "main.tf") -> list:
    return NoHardcodedPrivateCidr().check(Path(name), source)


def test_flags_private_cidr_literal():
    src = 'ip_cidr_range = "10.0.1.0/24"\n'
    diags = _check(src)
    assert len(diags) == 1
    assert "10.0.1.0/24" in diags[0].message


def test_flags_192_168_and_172_ranges():
    src = """
a = "192.168.0.5"
b = "172.16.4.0/22"
"""
    assert len(_check(src)) == 2


def test_allows_variable_reference():
    src = "ip_cidr_range = var.subnet_cidr\n"
    assert _check(src) == []


def test_ignores_public_and_special_addresses():
    src = """
open    = "0.0.0.0/0"
google  = "8.8.8.8"
loop    = "127.0.0.1"
docrange = "203.0.113.5"
"""
    assert _check(src) == []


def test_ignores_aggregate_rfc1918_ranges():
    # The whole /8, /12, /16 ranges are constants (NetworkPolicy allow-rules),
    # not env-specific subnets.
    src = """
a = "10.0.0.0/8"
b = "172.16.0.0/12"
c = "192.168.0.0/16"
"""
    assert _check(src) == []


def test_still_flags_specific_subnet_in_aggregate_space():
    src = 'cidr = "10.0.1.0/24"\n'
    assert len(_check(src)) == 1


def test_ignores_cidr_in_comment():
    src = "# legacy subnet was 10.0.1.0/24\nx = var.cidr\n"
    assert _check(src) == []


def test_ignores_non_tf_file():
    assert _check('x = "10.0.0.0/8"', name="readme.md") == []
