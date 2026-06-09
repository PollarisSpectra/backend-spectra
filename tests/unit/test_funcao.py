import pytest
from funcao import remove_bearer

def test_teste():
    assert remove_bearer("Bearer foobarbaz") == "foobarbaz"