from app.services.rbac import require_roles
import pytest


def test_require_roles_allows():
    require_roles(["admin"], ["admin"])  # no exception


def test_require_roles_denies():
    with pytest.raises(Exception):
        require_roles(["admin"], ["viewer"])
